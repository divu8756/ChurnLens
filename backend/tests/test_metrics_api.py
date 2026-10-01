import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pipeline import telco_state

from app import llm, sessions
from app.experiments.workspace import hash_key
from app.llm_fake import FakeLLM
from app.main import create_app
from app.run_history import save_run

KEY = "metrics-test-workspace-01"


class FakeGraph:
    def __init__(self, store):
        self.store = store

    def get_state(self, config):
        return SimpleNamespace(values=self.store.get(config["configurable"]["thread_id"], {}))


def _session(values=None, workspace=None) -> str:
    sid = sessions.new_session_id()
    folder = sessions.session_dir(sid)
    folder.mkdir(parents=True)
    (folder / sessions.META_FILE).write_text(json.dumps({"workspace_hash": workspace}))
    return sid


@pytest.fixture
def api():
    app = create_app()
    store = {}
    app.state.runs = SimpleNamespace(graph=FakeGraph(store))
    with TestClient(app, headers={"X-Workspace-Key": KEY}) as client:
        yield client, store


@pytest.fixture
def telco(api):
    client, store = api
    sid = _session(workspace=hash_key(KEY))
    store[sid] = {**telco_state(), "session_id": sid}
    return client, sid


def test_model_metrics(telco, api):
    client, sid = telco
    res = client.get(f"/metrics/model/{sid}")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["calibration_method"] == "isotonic"
    assert body["calibrated"]["brier"] <= body["raw"]["brier"]
    assert len(body["calibrated"]["deciles"]) == 10 and body["chosen_model_name"]
    assert client.get(f"/metrics/model/{'f' * 32}").status_code == 410
    _, store = api
    empty = _session()
    store[empty] = {"session_id": empty}
    assert client.get(f"/metrics/model/{empty}").status_code == 409


def test_business_metrics_defaults_and_recompute(telco):
    client, sid = telco
    base = client.get(f"/metrics/business/{sid}").json()
    assert base["enabled"] and base["defaults_only"] is True
    assert base["ab_plan"]["available"] and base["ab_plan"]["n_per_arm"] > 0
    assert any(a["source"] == "default" for a in base["assumptions"])

    start = time.perf_counter()
    res = client.post(f"/metrics/business/{sid}", json={"months_remaining": 24,
                                                        "relative_lift": 0.3})
    elapsed = time.perf_counter() - start
    assert res.status_code == 200, res.text
    edited = res.json()
    assert edited["defaults_only"] is False
    assert edited["kpis"]["revenue_at_risk"] == pytest.approx(
        2 * base["kpis"]["revenue_at_risk"])
    assert edited["ab_plan"]["n_per_arm"] < base["ab_plan"]["n_per_arm"]  # larger lift
    assert elapsed < 1.5  # SPEC target < 1 s on 10k rows; 7,000 here, with test overhead


@pytest.mark.parametrize("body", [
    {"months_remaining": 0}, {"months_remaining": 61}, {"relative_lift": 0.95},
    {"relative_lift": 0}, {"power": 1.0}, {"alpha": 0.5}, {"unknown": 1},
    {"offers": {"Free 10GB data booster": {"acceptance": 1.5}}},
])
def test_invalid_assumptions_are_422(telco, body):
    client, sid = telco
    assert client.post(f"/metrics/business/{sid}", json=body).status_code == 422


def test_business_disabled_without_arpu(api):
    client, store = api
    sid = _session()
    state = dict(telco_state())
    state["confirmed_schema"] = {**state["confirmed_schema"], "revenue_column": None}
    store[sid] = state
    body = client.get(f"/metrics/business/{sid}").json()
    assert body["enabled"] is False and "revenue" in body["reason"]
    assert client.post(f"/metrics/business/{sid}/explain", json={}).status_code == 409


@pytest.fixture
def fake_llm(monkeypatch):
    def install(*answers):
        fake = FakeLLM(fixtures={"Explanation": list(answers)})
        llm.set_model_factory(fake)
        monkeypatch.setattr(llm, "_sleep", lambda s: None)
        llm.reset_throttle()
        return fake
    yield install
    llm.set_model_factory(None)


def test_explanation_is_validated_and_cached(telco, fake_llm):
    client, sid = telco
    metrics = client.get(f"/metrics/business/{sid}").json()
    risk = metrics["kpis"]["revenue_at_risk"]
    good = {"sentences": [f"About {risk:,.0f} of revenue is estimated to be at risk.",
                          "The offers are assumed to help.", "A test is advised."],
            "figures": [{"source_key": "kpis.revenue_at_risk", "value": risk,
                         "display": f"{risk:,.0f}"}]}
    fake = fake_llm(good)
    first = client.post(f"/metrics/business/{sid}/explain", json={}).json()
    assert first["source"] == "ai" and first["cached"] is False
    again = client.post(f"/metrics/business/{sid}/explain", json={}).json()
    assert again["cached"] is True and len(fake.calls) == 1
    # New assumptions -> new numbers -> a new explanation (the old one would be stale).
    edited = client.post(f"/metrics/business/{sid}/explain",
                         json={"months_remaining": 24}).json()
    assert edited["assumptions_hash"] != first["assumptions_hash"]
    # The same text now cites the old revenue at risk: rejected, so the template is used.
    assert edited["source"] == "template" and edited["problems"]


def test_telemetry_summary_and_runs(telco, api):
    client, sid = telco
    res = client.get(f"/telemetry/{sid}")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["cost"]["label"] == "ESTIMATE"
    assert body["validator"]["checked"] >= 0
    assert client.get(f"/telemetry/{'e' * 32}").status_code == 410

    _, store = api
    save_run(sid, store[sid])
    other = _session(workspace=hash_key("someone-else-key-99"))
    save_run(other, {"session_id": other, "telemetry_events": []})
    runs = client.get("/telemetry/runs?limit=50").json()
    assert [r["session_id"] for r in runs] == [sid]
    assert client.get("/telemetry/runs?limit=0").status_code == 422
    bare = TestClient(client.app)
    assert bare.get("/telemetry/runs").json() == []
