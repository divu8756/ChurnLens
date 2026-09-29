from collections import Counter

import pytest

from app.config import get_settings
from app.graph import builder as b
from app.graph.checkpointer import create_checkpointer
from app.graph.state import ChurnState, ProgressEntry


def run(nodes=None, checkpointer=None, thread="t1", **initial):
    graph = b.build_graph(nodes=nodes, checkpointer=checkpointer)
    config = {"configurable": {"thread_id": thread}} if checkpointer else None
    return graph.invoke({"session_id": "s1", **initial}, config)


def ran(result) -> Counter:
    return Counter(p.node for p in result["progress"] if p.status == "done")


def done(name, **updates):
    def node(state: ChurnState):
        return {**updates, "progress": [ProgressEntry(node=name, status="done")]}

    return node


def test_stub_graph_runs_start_to_end():
    result = run()
    nodes = ran(result)
    expected = {b.INGEST, b.SCHEMA_AGENT, b.HUMAN_REVIEW, b.CLEANING, *b.PARALLEL_ANALYSIS,
                b.MODELLING, b.IMPACT, b.INSIGHT_AGENT, b.RECOMMENDATION_AGENT,
                b.VALIDATOR, b.REPORT}
    assert set(nodes) == expected
    assert result["errors"] == []
    assert result.get("final_error") is None


def test_fan_out_nodes_all_run_and_merge_once():
    result = run(nodes={b.HUMAN_REVIEW: done(b.HUMAN_REVIEW, time_column="tenure")})
    nodes = ran(result)
    for branch in (*b.PARALLEL_ANALYSIS, b.SURVIVAL):
        assert nodes[branch] == 1
    assert nodes[b.MODELLING] == 1  # fan-in waits for the whole superstep


def test_survival_skipped_without_time_column():
    assert b.SURVIVAL not in ran(run())


def test_offer_runs_only_with_offer_columns():
    assert b.OFFER not in ran(run())
    with_offers = run(nodes={b.HUMAN_REVIEW: done(b.HUMAN_REVIEW,
                                                  offer_columns={"offer_shown": "OfferShown"})})
    assert ran(with_offers)[b.OFFER] == 1


def test_fatal_error_routes_to_error_node():
    def failing_cleaning(state):
        raise b.FatalNodeError("Target has one class only.")

    result = run(nodes={b.CLEANING: failing_cleaning})
    nodes = ran(result)
    assert nodes[b.ERROR_NODE] == 1
    assert b.MODELLING not in nodes and b.EDA not in nodes
    assert result["final_error"] == "Target has one class only."
    assert result["errors"][0].fatal is True


def test_non_fatal_node_error_does_not_crash_graph():
    def broken_eda(state):
        raise ValueError("bad column")

    result = run(nodes={b.EDA: broken_eda})
    assert ran(result)[b.REPORT] == 1
    assert [(e.node, e.fatal) for e in result["errors"]] == [(b.EDA, False)]
    assert "bad column" in result["errors"][0].message


def test_validator_routes_back_to_failing_agent():
    calls = {"n": 0}

    def validator(state):
        calls["n"] += 1
        retry = [b.INSIGHT_AGENT] if calls["n"] == 1 else []
        return {"validation_report": {"retry_agents": retry},
                "progress": [ProgressEntry(node=b.VALIDATOR, status="done")]}

    result = run(nodes={b.VALIDATOR: validator})
    nodes = ran(result)
    assert nodes[b.INSIGHT_AGENT] == 2
    assert nodes[b.VALIDATOR] == 2
    assert nodes[b.REPORT] == 1


def test_sqlite_checkpointer_persists_state(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    saver = create_checkpointer()
    assert (tmp_path / "checkpoints.db").exists()
    run(checkpointer=saver, thread="session-abc")
    graph = b.build_graph(checkpointer=saver)
    snapshot = graph.get_state({"configurable": {"thread_id": "session-abc"}})
    assert snapshot.values["session_id"] == "s1"
    assert snapshot.next == ()  # finished


def test_postgres_without_driver_gives_clear_error(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user@localhost/db")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="langgraph-checkpoint-postgres"):
        create_checkpointer()
