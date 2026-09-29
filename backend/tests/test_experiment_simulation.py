"""T5c.5: the app finds a KNOWN effect, stays cautious without one, and blocks on SRM."""

import io
import json

import pandas as pd
import pytest
from test_experiments_api import SID, _approve, _draft, _upload, api  # noqa: F401 (fixture)

from app import sessions
from app.experiments.simulate import SCENARIOS, acceptor_churn, simulate_results

TRUE_DIFFERENCE = 0.21 - 0.26


def _assignment(n=20_000) -> pd.DataFrame:
    return pd.DataFrame({"customer_id": [f"c{i}" for i in range(n)],
                         "group": ["treatment" if i % 2 else "control" for i in range(n)]})


def test_simulated_rates_match_the_scenario():
    out = simulate_results(_assignment(), "real_effect")
    treat, ctrl = out[out.group == "treatment"], out[out.group == "control"]
    assert abs(ctrl.churned.mean() - 0.26) < 0.015
    assert abs(treat.churned.mean() - 0.21) < 0.015
    assert abs((treat.offer_accepted == "1").mean() - 0.45) < 0.015
    assert (ctrl.offer_accepted == "").all()
    assert acceptor_churn(SCENARIOS["real_effect"]) == pytest.approx((0.21 - 0.55 * 0.26) / 0.45)
    assert acceptor_churn(SCENARIOS["no_effect"]) == pytest.approx(0.26)
    # Same seed, same file.
    pd.testing.assert_frame_equal(out, simulate_results(_assignment(), "real_effect"))


def test_broken_delivery_splits_60_40():
    out = simulate_results(_assignment(), "broken_delivery")
    share = (out.group == "control").mean()
    assert abs(share - 0.4) < 0.001


def _run(client, scenario: str) -> dict:
    exp = _draft(client, segment_definition={"filters": []}, baseline_rate=0.26,
                 name=f"Known answer: {scenario}", planned_start="2020-01-01",
                 planned_end="2020-04-01")
    _approve(client, exp["id"])
    client.post(f"/experiments/{exp['id']}/assign", json={"session_id": SID, "actor": "ops"})
    csv = client.get(f"/experiments/{exp['id']}/assignment.csv").text
    assignment = pd.read_csv(io.StringIO(csv), dtype=str, keep_default_na=False)
    results = simulate_results(assignment, scenario)
    res = _upload(client, exp["id"], results, offer_cost="20")
    assert res.status_code == 200, res.text
    return res.json()["analysis"]


def test_scenario_1_real_effect_is_found(api):  # noqa: F811
    client, _ = api
    analysis = _run(client, "real_effect")
    d = analysis["itt"]["difference"]
    assert d["ci_low"] <= TRUE_DIFFERENCE <= d["ci_high"]
    assert not analysis["srm"]["failed"]


def test_scenario_2_no_effect_is_not_shipped(api):  # noqa: F811
    client, _ = api
    analysis = _run(client, "no_effect")
    assert analysis["decision_helper"]["verdict"] in ("inconclusive", "dont_ship")


def test_scenario_3_broken_delivery_blocks_on_srm(api):  # noqa: F811
    client, _ = api
    analysis = _run(client, "broken_delivery")
    assert analysis["srm"]["failed"]
    assert analysis["decision_helper"]["verdict"] == "untrustworthy"


def _mark_sample(session_id: str, sample: bool) -> None:
    folder = sessions.session_dir(session_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / sessions.META_FILE).write_text(json.dumps({"sample": sample}))


def test_demo_experiment_on_the_sample_data(api):  # noqa: F811
    client, _ = api
    _mark_sample(SID, False)
    res = client.post("/experiments/demo", json={"session_id": SID})
    assert res.status_code == 409 and "sample data" in res.json()["detail"]

    _mark_sample(SID, True)
    res = client.post("/experiments/demo", json={"session_id": SID})
    assert res.status_code == 201, res.text
    demo = res.json()
    assert demo["demo"] is True and demo["status"] == "results_uploaded"
    analysis = demo["analysis"]
    assert analysis["upload"]["early_look"] is False
    assert [a["action"] for a in demo["audit"]] == [
        "created", "approved", "assigned", "results_uploaded"]

    # A real experiment on the same customers is not blocked by the demo.
    real = _draft(client, name="Real test")
    _approve(client, real["id"])
    body = client.post(f"/experiments/{real['id']}/assign",
                       json={"session_id": SID, "actor": "ops"}).json()
    assert body["assignment_summary"]["excluded_other_experiments"] == 0

    # Deciding the demo never creates offer evidence.
    decided = client.post(f"/experiments/{demo['id']}/decide", json={
        "decision": "dont_ship", "decider": "me", "note": "demo"})
    assert decided.status_code == 200
    assert client.get("/experiments/offer-evidence").json() == []
