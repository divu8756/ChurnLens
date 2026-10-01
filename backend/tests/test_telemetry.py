import json

import pytest
from pydantic import BaseModel

from app import llm, sessions
from app.catalog import ModelPrice, Pricing
from app.graph import builder as b
from app.graph.state import ProgressEntry
from app.graph.telemetry import busy_ms, estimate_cost, schema_corrections, summarise_run
from app.llm_fake import FakeLLM, FakeResponse
from app.run_history import list_runs, save_run


class Ping(BaseModel):
    answer: str


@pytest.fixture
def fake(monkeypatch):
    fake_llm = FakeLLM(fixtures={"Ping": FakeResponse(parsed=Ping(answer="ok"),
                                                      input_tokens=100, output_tokens=7)})
    llm.set_model_factory(fake_llm)
    monkeypatch.setattr(llm, "_sleep", lambda s: None)
    llm.reset_throttle()
    yield fake_llm
    llm.set_model_factory(None)


def _ask(times: int):
    def node(state):
        for _ in range(times):
            llm.structured_call("fast", 0, "ping", Ping)
        return {"progress": [ProgressEntry(node="x", status="done")]}
    return node


def _run(nodes, **initial):
    graph = b.build_graph(nodes=nodes)
    return graph.invoke({"session_id": "a" * 32, **initial})


def test_every_node_run_gets_one_event_under_the_parallel_fan_out(fake):
    # The four analysis branches run in parallel; two of them call the LLM.
    values = _run({b.EDA: _ask(2), b.HYPOTHESIS: _ask(1)}, time_column="tenure")
    events = values["telemetry_events"]
    nodes = [e["node"] for e in events]
    expected = [n for n in b.ALL_NODES if n not in (b.OFFER, b.ERROR_NODE)]
    assert sorted(nodes) == sorted(expected)
    assert all(e["latency_ms"] >= 0 and e["started_at"] for e in events)
    by_node = {e["node"]: e for e in events}
    assert by_node[b.EDA]["input_tokens"] == 200 and by_node[b.EDA]["output_tokens"] == 14
    assert by_node[b.HYPOTHESIS]["input_tokens"] == 100 and by_node[b.HYPOTHESIS]["llm_calls"] == 1
    assert by_node[b.SEGMENTATION]["input_tokens"] == 0  # no LLM call, nothing leaked in
    assert by_node[b.EDA]["model"] == fake.calls[0]["model"]


def test_skipped_and_failed_runs_are_timed():
    def skipped(state):
        return {"progress": [ProgressEntry(node=b.OFFER, status="skipped")]}

    def broken(state):
        raise RuntimeError("boom")

    values = _run({b.OFFER: skipped, b.SEGMENTATION: broken}, offer_columns={"shown": "x"})
    by_node = {e["node"]: e for e in values["telemetry_events"]}
    assert by_node[b.OFFER]["status"] == "skipped" and by_node[b.OFFER]["latency_ms"] >= 0
    assert by_node[b.SEGMENTATION]["status"] == "failed"


def test_summary_tokens_and_cost_by_hand(fake):
    values = _run({b.EDA: _ask(2), b.HYPOTHESIS: _ask(1)})
    model = fake.calls[0]["model"]
    pricing = Pricing(note="test", models={model: ModelPrice(input_per_1m=0.5,
                                                              output_per_1m=2.0)})
    summary = summarise_run(values, pricing)
    assert summary["tokens"]["by_model"][model] == {"input_tokens": 300, "output_tokens": 21}
    assert summary["cost"]["total"] == pytest.approx((300 * 0.5 + 21 * 2.0) / 1e6)
    assert summary["cost"]["label"] == "ESTIMATE"
    nodes = {r["node"] for r in summary["latency_ms"]["by_node"]}
    assert b.EDA in nodes and summary["latency_ms"]["total_node_time"] >= 0
    free = estimate_cost({model: {"input_tokens": 300, "output_tokens": 21}}, Pricing())
    assert free["total"] == 0


def test_schema_corrections_fixture():
    proposal = {"target_column": "Churn", "positive_label": "Yes", "time_column": "tenure",
                "revenue_column": None, "id_columns": ["customerID"],
                "columns": [{"name": "SeniorCitizen", "semantic_type": "numeric"},
                            {"name": "Contract", "semantic_type": "categorical"}]}
    confirmed = {**proposal, "revenue_column": "MonthlyCharges",
                 "id_columns": ["customerID", "AccountNo"],
                 "columns": [{"name": "SeniorCitizen", "semantic_type": "binary"},
                             {"name": "Contract", "semantic_type": "categorical"}]}
    out = schema_corrections(proposal, confirmed)
    assert out["count"] == 3
    assert {f["field"] for f in out["fields"]} == {"revenue_column", "id_columns",
                                                   "columns.SeniorCitizen"}
    assert schema_corrections(proposal, proposal)["count"] == 0
    assert schema_corrections(None, confirmed)["available"] is False


def test_validator_counts_in_summary():
    values = {"session_id": "s", "telemetry_events": [], "retry_counts": {"insight_agent": 1},
              "validation_report": {"checked": 5, "passed": 4, "failed": 1, "dropped": 1,
                                    "details": [{"problems": ["a", "b"]}, {"problems": []}]}}
    summary = summarise_run(values, Pricing())
    assert summary["validator"] == {"checked": 5, "passed": 4, "failed": 1, "dropped": 1,
                                    "figures_caught": 2, "pass_rate": 0.8}
    assert summary["retries"]["validator"] == {"insight_agent": 1}


def _session(workspace: str | None) -> str:
    sid = sessions.new_session_id()
    folder = sessions.session_dir(sid)
    folder.mkdir(parents=True)
    (folder / sessions.META_FILE).write_text(json.dumps({"workspace_hash": workspace}))
    return sid


def test_summaries_persist_and_list_per_workspace():
    mine, other = _session("w" * 64), _session("x" * 64)
    for sid in (mine, mine, other):
        assert save_run(sid, {"session_id": sid, "telemetry_events": []}) is not None
    runs = list_runs("w" * 64)
    assert len(runs) == 2 and all(r["session_id"] == mine for r in runs)
    assert "created_at" in runs[0]
    assert len(list_runs("w" * 64, limit=1)) == 1
    assert list_runs(None) == []



def test_busy_time_skips_idle_gaps_and_overlaps():
    # Two parallel steps (0-2 s and 1-3 s), then a long wait for the human, then 10-11 s.
    assert busy_ms([(0, 2), (1, 3), (10, 11)]) == pytest.approx(4000)
    assert busy_ms([]) == 0
    values = {"session_id": "s", "telemetry_events": [
        {"node": "schema_agent", "started_at": "2026-01-01T00:00:00+00:00", "latency_ms": 1000,
         "status": "done"},
        {"node": "human_review", "started_at": "2026-01-01T00:10:00+00:00", "latency_ms": 500,
         "status": "done"}]}
    assert summarise_run(values, Pricing())["latency_ms"]["wall_clock"] == pytest.approx(1500)
