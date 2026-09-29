"""T5c.4: validated summary, decision gate and the feedback loop into next best offer."""

import pytest
from test_experiments_api import _results, _running, _upload, api  # noqa: F401 (fixture)
from test_nbo import data, run

from app import llm
from app.experiments import summary as sm
from app.llm_fake import FakeLLM
from app.stats.experiment_analysis import analyse
from app.stats.nbo import EXPERIMENT_PROVEN, OBSERVATIONAL


@pytest.fixture
def fake(monkeypatch):
    def install(*answers):
        fake_llm = FakeLLM(fixtures={"ExperimentSummary": list(answers)})
        llm.set_model_factory(fake_llm)
        monkeypatch.setattr(llm, "_sleep", lambda s: None)
        llm.reset_throttle()
        return fake_llm
    yield install
    llm.set_model_factory(None)


def _analysis(verdict_ship=True):
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(42)
    n = 3000
    arm = np.array(["treatment"] * n + ["control"] * n)
    frame = pd.DataFrame({
        "customer_id": [f"c{i}" for i in range(2 * n)], "arm": arm,
        "offer_accepted": np.where(arm == "treatment", (rng.random(2 * n) < 0.45), 0)
        .astype(int),
        "churned": (rng.random(2 * n) < np.where(arm == "treatment", 0.21, 0.26)).astype(int),
        "revenue": np.nan, "complaints": np.nan, "segments": [[]] * (2 * n)})
    design = {"control_share": 0.5, "alpha": 0.05, "power": 0.8, "baseline_rate": 0.26,
              "mde": 0.05, "mde_type": "absolute", "guardrail_metrics": []}
    money = {"customer_value": 800.0, "offer_cost": 50.0} if verdict_ship else {}
    result = analyse(frame, design, money)
    result["warnings"] = []
    return result


def _good_summary(a):
    t, c = a["itt"]["arms"]["treatment"]["rate"], a["itt"]["arms"]["control"]["rate"]
    return {"sentences": [
        f"Churn was {t * 100:.1f}% with the offer and {c * 100:.1f}% without it.",
        "The confidence interval of the difference excludes zero.",
        "The offer saved customers and its net value is positive.",
        "No guardrail was breached.",
        "No warnings."],
        "figures": [
            {"source_key": "itt.arms.treatment.rate", "value": t, "display": f"{t * 100:.1f}%"},
            {"source_key": "itt.arms.control.rate", "value": c, "display": f"{c * 100:.1f}%"}]}


def test_valid_summary_is_accepted(fake):
    a = _analysis()
    fake_llm = fake(_good_summary(a))
    out = sm.generate(a, "Annual discount")
    assert out["source"] == "ai" and out["problems"] == [] and len(out["sentences"]) == 5
    assert len(fake_llm.calls) == 1


def test_a_drop_may_be_written_as_its_size():
    a = _analysis()
    d = a["itt"]["difference"]["value"]
    assert d < 0
    summary = _good_summary(a)
    summary["sentences"][1] = f"Churn fell by {abs(d) * 100:.1f} percentage points."
    summary["figures"].append({"source_key": "itt.difference.value", "value": d,
                               "display": f"{abs(d) * 100:.1f}%"})
    assert sm.validate_summary(summary, a) == []
    # A wrong size is still caught.
    summary["figures"][-1]["display"] = "9.9%"
    assert sm.validate_summary(summary, a)


def test_the_confidence_level_is_a_declarable_figure():
    a = _analysis()
    summary = _good_summary(a)
    summary["sentences"][1] = "The 95% confidence interval of the difference excludes zero."
    assert sm.validate_summary(summary, a)  # undeclared
    summary["figures"].append({"source_key": "itt.difference.ci_level", "value": 0.95,
                               "display": "95%"})
    assert sm.validate_summary(summary, a) == []


def test_numbers_in_the_offer_name_are_allowed():
    a = _analysis()
    summary = _good_summary(a)
    summary["sentences"][0] += " The offer was 1 month free on annual plan."
    assert sm.validate_summary(summary, a, "1 month free on annual plan") == []
    assert sm.validate_summary(summary, a, "Annual discount")


def test_invented_number_is_retried_then_template(fake):
    a = _analysis()
    bad = _good_summary(a)
    bad["sentences"][2] = "The offer saved 999 customers."
    fake_llm = fake(bad)
    out = sm.generate(a, "Annual discount")
    assert out["source"] == "template" and len(fake_llm.calls) == 2
    assert any("999" in p for p in out["problems"])
    assert len(out["sentences"]) == 5


def test_summary_may_not_go_beyond_the_verdict(fake):
    a = _analysis(verdict_ship=False)
    assert a["decision_helper"]["verdict"] == "inconclusive"
    bad = _good_summary(a)
    bad["sentences"][4] = "We should roll out the offer to everyone."
    problems = sm.validate_summary(bad, a)
    assert any("beyond the verdict" in p for p in problems)
    fake(bad)
    assert sm.generate(a, "Annual discount")["source"] == "template"


def test_llm_unavailable_uses_template(fake):
    fake(TimeoutError("down"))
    out = sm.generate(_analysis(), "Annual discount")
    assert out["source"] == "template" and out["problems"][0].startswith("AI unavailable")


# ------------------------------------------------------------ decision gate (API)


def _decide(client, exp_id, decision, **extra):
    body = {"decision": decision, "decider": "head of retention", "note": "reviewed", **extra}
    return client.post(f"/experiments/{exp_id}/decide", json=body)


def test_deciding_before_results_is_rejected(api):  # noqa: F811
    client, _ = api
    exp, _ = _running(client)
    assert _decide(client, exp["id"], "ship").status_code == 409
    res = client.post(f"/experiments/{exp['id']}/decide",
                      json={"decision": "ship", "decider": "x", "note": ""})
    assert res.status_code == 422  # a note is required


def test_srm_blocks_ship_but_not_dont_ship(api):  # noqa: F811
    client, _ = api
    exp, assignment = _running(client, segment_definition={"filters": []})
    results = _results(assignment)
    control = results.index[results.group == "control"]
    _upload(client, exp["id"], results.drop(control[: len(control) // 3]), offer_cost="5")
    res = _decide(client, exp["id"], "ship")
    assert res.status_code == 409 and "sample ratio mismatch" in res.json()["detail"]
    body = _decide(client, exp["id"], "dont_ship").json()
    assert body["status"] == "decided" and body["decision"] == "dont_ship"
    # Untrustworthy results never become offer evidence.
    assert client.get("/experiments/offer-evidence").json() == []


def test_extend_returns_to_running(api):  # noqa: F811
    client, _ = api
    exp, assignment = _running(client)
    _upload(client, exp["id"], _results(assignment))
    body = _decide(client, exp["id"], "extend", new_planned_end="2030-01-01").json()
    assert body["status"] == "running" and body["planned_end"] == "2030-01-01"
    assert body["audit"][-1]["action"] == "decided_extend"
    assert _upload(client, exp["id"], _results(assignment, seed=7)).status_code == 200


def test_ship_writes_evidence_and_summary_is_cached(api, fake):  # noqa: F811
    client, _ = api
    exp, assignment = _running(client)
    _upload(client, exp["id"], _results(assignment), offer_cost="20")
    fake_llm = fake(TimeoutError("down"))
    first = client.post(f"/experiments/{exp['id']}/summary").json()
    second = client.post(f"/experiments/{exp['id']}/summary").json()
    assert first == second and first["source"] == "template"
    assert len(fake_llm.calls) >= 1
    calls = len(fake_llm.calls)
    client.post(f"/experiments/{exp['id']}/summary")
    assert len(fake_llm.calls) == calls  # cached in the analysis

    body = _decide(client, exp["id"], "ship").json()
    assert body["status"] == "decided"
    evidence = client.get("/experiments/offer-evidence").json()
    assert len(evidence) == 1 and evidence[0]["offer"] == exp["offer"]
    a = body["analysis"]
    reduction = a["itt"]["arms"]["control"]["rate"] - a["itt"]["arms"]["treatment"]["rate"]
    assert evidence[0]["retention_lift_per_acceptor"] == pytest.approx(
        min(1.0, reduction / a["impact"]["acceptance_rate"]))
    assert _decide(client, exp["id"], "ship").status_code == 409  # decided is final


# ------------------------------------------------------------ feedback loop (NBO)


def test_experiment_evidence_changes_next_best_offer_inputs():
    frame, schema, predictions = data()
    base_table, base_summary = run(frame, schema, predictions)
    assert set(base_table["evidence"].dropna()) == {OBSERVATIONAL}
    assert base_summary["offer_evidence"]["Cashback"]["label"] == OBSERVATIONAL

    evidence = {"cashback": {"experiment_id": 1, "retention_lift_per_acceptor": 0.9,
                             "itt_difference": -0.05, "ci_low": -0.08, "ci_high": -0.02,
                             "decision": "ship"}}
    table, summary = run(frame, schema, predictions, evidence=evidence)
    assert summary["offer_evidence"]["Cashback"]["label"] == EXPERIMENT_PROVEN
    assert summary["offer_evidence"]["Data pack"]["label"] == OBSERVATIONAL
    cashback = table[table.best_offer == "Cashback"]
    assert len(cashback) > (base_table.best_offer == "Cashback").sum()
    assert (cashback["retention_lift"] == 0.9).all()
    assert (cashback["evidence"] == EXPERIMENT_PROVEN).all()
