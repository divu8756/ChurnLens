import io
import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import sessions
from app.api import experiments as experiments_api
from app.experiments import service
from app.experiments.assignment import assign_groups
from app.main import create_app

SID = "a" * 32
SID2 = "b" * 32
OFFER = "10% off annual contract"


def _write_session(tmp_path, sid: str, n: int = 3000, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame({
        "customerID": [f"c{i}" for i in range(n)],
        "tenure": rng.integers(1, 72, n),
        "MonthlyCharges": rng.normal(65, 20, n).round(2),
        "Contract": rng.choice(["Month-to-month", "One year"], n),
        "Churn": (rng.random(n) < 0.3).astype(int),
    })
    folder = tmp_path / sid
    folder.mkdir()
    frame.to_parquet(folder / "clean.parquet", index=False)
    prob = rng.random(n).round(3)
    pd.DataFrame({"customer_id": frame.customerID, "churn_probability": prob,
                  "risk_band": np.where(prob >= 0.6, "High", np.where(prob >= 0.3, "Medium",
                                                                       "Low")),
                  "actual_churn": frame.Churn}).to_parquet(folder / "pred.parquet", index=False)
    return {
        "confirmed_schema": {"target_column": "Churn", "positive_label": "1",
                             "id_columns": ["customerID"], "time_column": "tenure",
                             "revenue_column": "MonthlyCharges",
                             "columns": [{"name": "Contract", "semantic_type": "categorical"}]},
        "clean_path": str(folder / "clean.parquet"),
        "predictions_path": str(folder / "pred.parquet"),
        "final_recommendations": [{"id": "R1", "action": "Offer annual contracts"}],
        "_frame": frame,
    }


@pytest.fixture
def api(tmp_path, monkeypatch):
    store = {SID: _write_session(tmp_path, SID), SID2: _write_session(tmp_path, SID2, seed=7)}

    def fake_loader(request):
        def load(session_id):
            if session_id not in store:
                raise service.ServiceError(410, "Session expired, please re-upload.")
            return store[session_id]
        return load

    monkeypatch.setattr(experiments_api, "values_loader", fake_loader)
    with TestClient(create_app()) as client:
        yield client, store


MTM = {"description": "Month-to-month", "filters": [
    {"column": "Contract", "op": "eq", "value": "Month-to-month"}]}


def _draft(client, **overrides) -> dict:
    body = {"name": "Annual offer test", "hypothesis": "An annual discount lowers churn",
            "session_id": SID, "source_recommendation_id": "R1", "segment_definition": MTM,
            "offer": OFFER, "mde": 0.05, "created_by": "analyst"}
    body.update(overrides)
    res = client.post("/experiments", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _approve(client, exp_id, **overrides):
    body = {"approver": "manager", "cost_and_eligibility_reviewed": True, **overrides}
    return client.post(f"/experiments/{exp_id}/approve", json=body)


def test_create_draft_measures_baseline_from_segment(api):
    client, store = api
    exp = _draft(client)
    frame = store[SID]["_frame"]
    segment = frame[frame.Contract == "Month-to-month"]
    assert exp["status"] == "draft"
    assert abs(exp["baseline_rate"] - segment.Churn.mean()) < 1e-12
    design = exp["design"]
    assert design["inputs"]["n_available"] == len(segment)
    sources = {a["name"]: a["source"] for a in design["assumptions"]}
    assert sources == {"baseline_rate": "data", "alpha": "default", "power": "default",
                       "control_share": "default"}
    assert exp["n_required_treatment"] == design["n_treatment"]
    assert [a["action"] for a in exp["audit"]] == ["created"]
    assert client.get("/experiments").json()[0]["id"] == exp["id"]


def test_create_validation_errors(api):
    client, _ = api
    body = {"name": "x", "hypothesis": "y", "offer": OFFER, "mde": 0.05, "created_by": "a"}
    assert client.post("/experiments", json=body).status_code == 422  # no baseline, no session
    assert client.post("/experiments", json={**body, "baseline_rate": 0.3}).status_code == 201
    bad = [{"session_id": SID, "source_recommendation_id": "R9"},
           {"session_id": SID, "segment_definition": {"filters": [
               {"column": "Nope", "op": "eq", "value": 1}]}},
           {"baseline_rate": 0.3, "alpha": 0.5},
           {"baseline_rate": 0.3, "mde": 0.4}]
    for extra in bad:
        res = client.post("/experiments", json={**body, **extra})
        assert res.status_code == 422, (extra, res.text)
    assert client.post("/experiments", json={**body, "session_id": "c" * 32}).status_code == 410


def test_edit_only_while_draft(api):
    client, _ = api
    exp = _draft(client)
    res = client.patch(f"/experiments/{exp['id']}", json={"actor": "analyst", "mde": 0.08,
                                                          "power": 0.9})
    assert res.status_code == 200, res.text
    edited = res.json()
    assert edited["mde"] == 0.08 and edited["n_required_treatment"] < exp["n_required_treatment"]
    sources = {a["name"]: a["source"] for a in edited["design"]["assumptions"]}
    assert sources["power"] == "user" and sources["alpha"] == "default"

    assert _approve(client, exp["id"], cost_and_eligibility_reviewed=False).status_code == 422
    approved = _approve(client, exp["id"])
    assert approved.status_code == 200 and approved.json()["approved_by"] == "manager"
    res = client.patch(f"/experiments/{exp['id']}", json={"actor": "analyst", "mde": 0.1})
    assert res.status_code == 409
    assert _approve(client, exp["id"]).status_code == 409
    actions = [a["action"] for a in client.get(f"/experiments/{exp['id']}").json()["audit"]]
    assert actions == ["created", "edited", "approved"]


def test_assign_export_and_reproducibility(api, tmp_path):
    client, store = api
    exp = _draft(client)
    # A Phase 5b message cached for one treatment customer is attached to the export.
    frame = store[SID]["_frame"]
    ids = frame[frame.Contract == "Month-to-month"].customerID.tolist()
    expected = assign_groups(exp["id"], ids, 0.5)
    treated = ids[expected.index("treatment")]
    folder = sessions.session_dir(SID)
    folder.mkdir(parents=True)
    (folder / "offer_messages.json").write_text(json.dumps(
        {f"{treated}␟{OFFER}": {"message": "Stay with us", "sms": "Stay"}}))

    assert client.post(f"/experiments/{exp['id']}/assign",
                       json={"session_id": SID, "actor": "ops"}).status_code == 409  # draft
    _approve(client, exp["id"])
    res = client.post(f"/experiments/{exp['id']}/assign", json={"session_id": SID,
                                                                "actor": "ops"})
    assert res.status_code == 200, res.text
    body = res.json()
    summary = body["assignment_summary"]
    assert body["status"] == "running" and body["data_snapshot_hash"]
    assert summary["assigned"] == len(ids) and summary["messages_attached"] == 1
    assert summary["n_control"] == expected.count("control")
    assert {r["covariate"] for r in summary["balance"]["covariates"]} == {
        "churn_probability", "tenure", "MonthlyCharges", "Contract"}

    csv = client.get(f"/experiments/{exp['id']}/assignment.csv")
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
    out = pd.read_csv(io.StringIO(csv.text), dtype=str, keep_default_na=False)
    assert list(out.columns) == ["customer_id", "group", "offer", "message"]
    assert out.customer_id.tolist() == ids and out.group.tolist() == expected
    assert (out[out.group == "control"].offer == "").all()
    assert (out[out.group == "treatment"].offer == OFFER).all()
    assert out.set_index("customer_id").loc[treated, "message"] == "Stay with us"

    # Assigning again is rejected: the design and the groups are locked.
    again = client.post(f"/experiments/{exp['id']}/assign", json={"session_id": SID,
                                                                  "actor": "ops"})
    assert again.status_code == 409


def test_overlapping_experiments_are_prevented(api):
    client, _ = api
    first = _draft(client)
    _approve(client, first["id"])
    client.post(f"/experiments/{first['id']}/assign", json={"session_id": SID, "actor": "ops"})

    same = _draft(client, name="Same segment")
    _approve(client, same["id"])
    res = client.post(f"/experiments/{same['id']}/assign", json={"session_id": SID,
                                                                 "actor": "ops"})
    assert res.status_code == 409 and "another running experiment" in res.json()["detail"]

    wider = _draft(client, name="Everyone", segment_definition={"filters": []})
    _approve(client, wider["id"])
    body = client.post(f"/experiments/{wider['id']}/assign",
                       json={"session_id": SID, "actor": "ops"}).json()
    summary = body["assignment_summary"]
    assert summary["excluded_other_experiments"] == first["design"]["inputs"]["n_available"]
    assert summary["assigned"] == 3000 - summary["excluded_other_experiments"]
    assert any("another running experiment" in w for w in summary["warnings"])


def test_under_powered_warning_and_expired_session(api):
    client, _ = api
    exp = _draft(client, mde=0.01)
    assert exp["design"]["feasible"] is False and exp["design"]["warnings"]
    _approve(client, exp["id"])
    res = client.post(f"/experiments/{exp['id']}/assign", json={"session_id": "d" * 32,
                                                                "actor": "ops"})
    assert res.status_code == 410
    body = client.post(f"/experiments/{exp['id']}/assign",
                       json={"session_id": SID2, "actor": "ops"}).json()
    assert any(w.startswith("Under-powered") for w in body["assignment_summary"]["warnings"])


def test_unknown_experiment_is_404(api):
    client, _ = api
    assert client.get("/experiments/999").status_code == 404
    assert client.get("/experiments/999/assignment.csv").status_code == 404


# ---------------------------------------------------------------- results (T5c.3)


def _running(client, **overrides) -> tuple[dict, pd.DataFrame]:
    exp = _draft(client, **overrides)
    _approve(client, exp["id"])
    res = client.post(f"/experiments/{exp['id']}/assign", json={"session_id": SID,
                                                                "actor": "ops"})
    assert res.status_code == 200, res.text
    csv = client.get(f"/experiments/{exp['id']}/assignment.csv").text
    return res.json(), pd.read_csv(io.StringIO(csv), dtype=str, keep_default_na=False)


def _results(assignment: pd.DataFrame, p_t=0.10, p_c=0.40, seed=42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    treat = assignment.group == "treatment"
    return pd.DataFrame({
        "customer_id": assignment.customer_id, "group": assignment.group,
        "offer_accepted": np.where(treat, (rng.random(len(assignment)) < 0.5).astype(int), ""),
        "churned": (rng.random(len(assignment)) < np.where(treat, p_t, p_c)).astype(int),
        "revenue": rng.normal(60, 10, len(assignment)).round(2),
        # Same complaint pattern in both arms, so the guardrail is never breached by chance.
        "complaints": (np.arange(len(assignment)) % 10 == 0).astype(int),
    })


def _upload(client, exp_id, frame, **form):
    data = {"uploaded_by": "analyst", **form}
    return client.post(f"/experiments/{exp_id}/results", data=data,
                       files={"file": ("results.csv", frame.to_csv(index=False), "text/csv")})


PREREG = [{"name": "New customers", "filters": [{"column": "tenure", "op": "lte", "value": 12}]}]


def test_results_upload_analyses_and_audits(api):
    client, _ = api
    exp, assignment = _running(client, preregistered_segments=PREREG,
                               planned_start="2020-01-01", planned_end="2020-04-01")
    assert exp["assignment_summary"]["customer_value_estimate"] > 0
    res = _upload(client, exp["id"], _results(assignment), offer_cost="20")
    assert res.status_code == 200, res.text
    body = res.json()
    analysis = body["analysis"]
    assert body["status"] == "results_uploaded"
    assert not analysis["srm"]["failed"]
    assert analysis["itt"]["difference"]["ci_high"] < 0
    assert analysis["impact"]["assumptions"][0]["source"] == "data"
    assert analysis["segments"]["items"]["New customers"]["n"] > 0
    assert analysis["decision_helper"]["verdict"] == "ship", analysis["decision_helper"]
    assert analysis["upload"]["early_look"] is False
    assert body["audit"][-1]["action"] == "results_uploaded"

    # Assumption edits are recomputed in Python (never in the browser).
    res = client.post(f"/experiments/{exp['id']}/analysis", json={
        "actor": "analyst", "assumptions": {"customer_value": 1.0, "offer_cost": 500.0}})
    assert res.status_code == 200
    again = res.json()["analysis"]
    assert again["impact"]["net_value"] < 0
    assert again["decision_helper"]["verdict"] == "dont_ship"
    assert again["impact"]["assumptions"][0]["source"] == "user"


def test_mismatched_results_are_reported(api):
    client, _ = api
    exp, assignment = _running(client)
    results = _results(assignment)
    results.loc[0, "customer_id"] = "stranger"
    results.loc[1, "group"] = "control" if results.loc[1, "group"] == "treatment" \
        else "treatment"
    res = _upload(client, exp["id"], results)
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert "never assigned: stranger" in detail
    assert "different group" in detail

    dupes = pd.concat([_results(assignment), _results(assignment).head(1)])
    assert "duplicate" in _upload(client, exp["id"], dupes).json()["detail"]
    bad = _results(assignment)
    bad["churned"] = bad["churned"].astype(str)
    bad.loc[3, "churned"] = "maybe"
    assert "churned must be 0 or 1" in _upload(client, exp["id"], bad).json()["detail"]
    missing = _results(assignment).drop(columns="churned")
    assert "Missing required columns" in _upload(client, exp["id"], missing).json()["detail"]
    assert client.get(f"/experiments/{exp['id']}").json()["status"] == "running"


def test_early_look_and_status_checks(api):
    client, _ = api
    draft = _draft(client)
    assert _upload(client, draft["id"], pd.DataFrame({"customer_id": ["x"], "group": ["control"],
                                                      "churned": [0]})).status_code == 409
    exp, assignment = _running(client, name="Early", planned_start="2020-01-01",
                               planned_end="2999-01-01", segment_definition={"filters": [
                                   {"column": "Contract", "op": "eq", "value": "One year"}]})
    body = _upload(client, exp["id"], _results(assignment)).json()
    assert body["analysis"]["upload"]["early_look"] is True
    assert body["analysis"]["warnings"][0].startswith("Early look")
    # Net value unknown without an offer cost, so the helper cannot say "ship".
    assert body["analysis"]["decision_helper"]["verdict"] == "inconclusive"


def test_churn_dates_outside_window_rejected(api):
    client, _ = api
    exp, assignment = _running(client, planned_start="2020-01-01", outcome_window_days=30)
    results = _results(assignment)
    results["churn_date"] = np.where(results.churned == 1, "2020-01-15", "")
    assert _upload(client, exp["id"], results).status_code == 200
    first_churner = results.index[results.churned == 1][0]
    results.loc[first_churner, "churn_date"] = "2020-06-01"
    res = _upload(client, exp["id"], results)
    assert res.status_code == 422 and "outside the outcome window" in res.json()["detail"]


def test_srm_is_flagged_on_upload(api):
    client, _ = api
    exp, assignment = _running(client, segment_definition={"filters": []})
    # Broken delivery: a third of the control group was lost, so the file splits ~60/40.
    results = _results(assignment)
    control = results.index[results.group == "control"]
    results = results.drop(control[: len(control) // 3])
    body = _upload(client, exp["id"], results, offer_cost="5").json()
    analysis = body["analysis"]
    assert analysis["srm"]["failed"] is True
    assert analysis["decision_helper"]["verdict"] == "untrustworthy"
    assert analysis["warnings"][0].startswith("Sample ratio mismatch")
    assert any("missing from the file" in w for w in analysis["warnings"])
