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
