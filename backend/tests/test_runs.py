import json
import threading
import time

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from app import llm
from app.api import runs as runs_api
from app.graph.builder import build_graph
from app.graph.checkpointer import make_serde
from app.graph.nodes import default_nodes
from app.llm_fake import FakeLLM
from app.main import create_app
from app.runs import RunManager


def telco_like(rows=150) -> pd.DataFrame:
    rng = np.random.default_rng(2)
    return pd.DataFrame({
        "customerID": [f"C{i:05d}" for i in range(rows)],
        "tenure": rng.integers(0, 72, rows),
        "MonthlyCharges": rng.normal(60, 20, rows).round(2),
        "Contract": rng.choice(["Month-to-month", "One year", "Two year"], rows),
        "Churn": rng.choice(["Yes", "No"], rows),
    })


def valid_schema() -> dict:
    return {
        "columns": [{"name": "customerID", "semantic_type": "id"},
                    {"name": "tenure", "semantic_type": "numeric"},
                    {"name": "MonthlyCharges", "semantic_type": "numeric"},
                    {"name": "Contract", "semantic_type": "categorical"},
                    {"name": "Churn", "semantic_type": "binary"}],
        "target_column": "Churn", "positive_label": "Yes",
        "id_columns": ["customerID"], "time_column": "tenure",
    }


@pytest.fixture
def client(monkeypatch):
    fake = FakeLLM(fixtures={"SchemaProposal": [TimeoutError("no llm in tests")]})
    llm.set_model_factory(fake)
    monkeypatch.setattr(llm, "_sleep", lambda s: None)
    llm.reset_throttle()
    app = create_app()
    app.state.runs = RunManager(
        lambda: build_graph(nodes=default_nodes(), checkpointer=InMemorySaver(serde=make_serde()))
    )
    with TestClient(app) as test_client:
        yield test_client
        _wait_for_background_runs(app.state.runs)
    llm.set_model_factory(None)


def _wait_for_background_runs(manager: RunManager, timeout: float = 30.0) -> None:
    """A run left going would call the LLM later, inside another test's fake."""
    deadline = time.monotonic() + timeout
    while any(r.status == "running" for r in manager._runs.values()):
        if time.monotonic() > deadline:
            raise AssertionError("a background run did not finish")
        time.sleep(0.02)


def upload(client) -> str:
    data = telco_like().to_csv(index=False).encode()
    response = client.post("/upload", files={"file": ("c.csv", data)})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def wait_for(client, session_id, status, timeout=10.0):
    run = client.app.state.runs.get(session_id)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if run.status == status:
            return run
        time.sleep(0.02)
    raise AssertionError(f"run is {run.status}, expected {status}")


def read_events(client, session_id, headers=None, stop=("done",),
                params=None) -> list[tuple[str, dict]]:
    events, current = [], {}
    with client.stream("GET", f"/stream/{session_id}", headers=headers or {},
                       params=params or {}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        for line in response.iter_lines():
            if line.startswith("event: "):
                current["event"] = line[7:]
            elif line.startswith("id: "):
                current["id"] = int(line[4:])
            elif line.startswith("data: "):
                current["data"] = json.loads(line[6:])
            elif line == "" and current:
                events.append((current["event"], current.get("data", {}), current.get("id")))
                if current["event"] in stop:
                    break
                current = {}
    return events


def started(session_id, client):
    response = client.post(f"/analyze/{session_id}")
    assert response.status_code == 200, response.text
    return response


# ---------------------------------------------------------------- tests


def test_graph_pauses_at_human_review_with_proposal(client):
    session_id = upload(client)
    started(session_id, client)
    run = wait_for(client, session_id, "awaiting_confirmation")
    pending = client.app.state.runs.pending_interrupt(session_id)
    assert pending["proposal"]["target_column"] == "Churn"
    assert pending["proposal"]["source"] == "rules"  # LLM failed -> heuristics
    assert [e.event for e in run.events][-1] == "awaiting_confirmation"


def test_analyze_is_idempotent(client):
    session_id = upload(client)
    first = started(session_id, client)
    wait_for(client, session_id, "awaiting_confirmation")
    second = started(session_id, client)
    assert second.json()["status"] == "awaiting_confirmation"
    assert first.json()["session_id"] == second.json()["session_id"]


def test_resume_with_valid_schema_continues_to_cleaning(client):
    session_id = upload(client)
    started(session_id, client)
    wait_for(client, session_id, "awaiting_confirmation")
    response = client.post(f"/confirm-schema/{session_id}", json=valid_schema())
    assert response.status_code == 200, response.text
    wait_for(client, session_id, "done")
    state = client.app.state.runs.graph.get_state(
        {"configurable": {"thread_id": session_id}}).values
    assert state["target_column"] == "Churn" and state["target_confirmed"] is True
    assert state["time_column"] == "tenure"
    nodes = [p.node for p in state["progress"]]
    assert "cleaning" in nodes and "survival" in nodes and nodes[-1] == "report"


@pytest.mark.parametrize("change, message", [
    ({"target_column": "Contract"}, "exactly two values"),
    ({"target_column": "Nope"}, "does not exist"),
    ({"positive_label": "Maybe"}, "not a value"),
    ({"id_columns": ["ghost"]}, "ID columns not found"),
    ({"time_column": "Contract"}, "must be numeric"),
])
def test_invalid_schema_returns_422_and_stays_paused(client, change, message):
    session_id = upload(client)
    started(session_id, client)
    wait_for(client, session_id, "awaiting_confirmation")
    response = client.post(f"/confirm-schema/{session_id}", json={**valid_schema(), **change})
    assert response.status_code == 422
    assert any(message in p for p in response.json()["detail"]["problems"])
    assert client.app.state.runs.get(session_id).status == "awaiting_confirmation"


def test_resuming_twice_is_rejected(client):
    session_id = upload(client)
    started(session_id, client)
    wait_for(client, session_id, "awaiting_confirmation")
    assert client.post(f"/confirm-schema/{session_id}", json=valid_schema()).status_code == 200
    again = client.post(f"/confirm-schema/{session_id}", json=valid_schema())
    assert again.status_code == 409


def test_confirm_before_start_or_unknown_session(client):
    session_id = upload(client)
    assert client.post(f"/confirm-schema/{session_id}", json=valid_schema()).status_code == 410
    assert client.post(f"/confirm-schema/{'a' * 32}", json=valid_schema()).status_code == 410


def test_sse_emits_events_in_order(client):
    session_id = upload(client)
    started(session_id, client)
    wait_for(client, session_id, "awaiting_confirmation")
    client.post(f"/confirm-schema/{session_id}", json=valid_schema())
    wait_for(client, session_id, "done")

    events = read_events(client, session_id)
    names = [(e, d.get("node")) for e, d, _ in events]
    assert names[:5] == [("node_start", "ingest"), ("node_finish", "ingest"),
                         ("node_start", "schema_agent"), ("error", "schema_agent"),
                         ("node_finish", "schema_agent")]
    kinds = [e for e, _, _ in events]
    assert kinds.index("awaiting_confirmation") < kinds.index("resumed")
    assert kinds[-1] == "done" and events[-1][1]["ok"] is True
    ids = [i for _, _, i in events]
    assert ids == sorted(ids) and len(set(ids)) == len(ids)
    finishes = [d["node"] for e, d, _ in events if e == "node_finish"]
    assert finishes.index("cleaning") < finishes.index("modelling") < finishes.index("report")


def test_sse_reconnect_with_last_event_id_skips_seen_events(client):
    session_id = upload(client)
    started(session_id, client)
    wait_for(client, session_id, "awaiting_confirmation")
    client.post(f"/confirm-schema/{session_id}", json=valid_schema())
    wait_for(client, session_id, "done")
    all_events = read_events(client, session_id)
    resumed = read_events(client, session_id, headers={"Last-Event-ID": "4"})
    assert [i for _, _, i in resumed] == [i for _, _, i in all_events][4:]


def test_sse_after_query_param_resumes_and_header_wins(client):
    session_id = upload(client)
    started(session_id, client)
    wait_for(client, session_id, "awaiting_confirmation")
    client.post(f"/confirm-schema/{session_id}", json=valid_schema())
    wait_for(client, session_id, "done")
    ids = [i for _, _, i in read_events(client, session_id)]
    by_query = read_events(client, session_id, params={"after": 3})
    assert [i for _, _, i in by_query] == ids[3:]
    both = read_events(client, session_id, params={"after": 1},
                       headers={"Last-Event-ID": "6"})
    assert [i for _, _, i in both] == ids[6:]

def test_sse_sends_heartbeat_while_paused(client, monkeypatch):
    # TestClient buffers a streamed body until it ends, so resume after a
    # moment to let the stream finish, then check a heartbeat came while paused.
    monkeypatch.setattr(runs_api, "HEARTBEAT_S", 0.1)
    session_id = upload(client)
    started(session_id, client)
    wait_for(client, session_id, "awaiting_confirmation")
    timer = threading.Timer(
        0.6, lambda: client.app.state.runs.resume(session_id, valid_schema()))
    timer.start()
    events = read_events(client, session_id)
    timer.join()
    kinds = [e for e, _, _ in events]
    paused_at, resumed_at = kinds.index("awaiting_confirmation"), kinds.index("resumed")
    assert "heartbeat" in kinds[paused_at:resumed_at]
    assert kinds[-1] == "done"


def test_stream_for_unknown_or_unstarted_session_is_410(client):
    assert client.get(f"/stream/{'b' * 32}").status_code == 410
    session_id = upload(client)
    assert client.get(f"/stream/{session_id}").status_code == 410


def test_revenue_column_is_validated(client):
    session_id = upload(client)
    started(session_id, client)
    wait_for(client, session_id, "awaiting_confirmation")
    bad = client.post(f"/confirm-schema/{session_id}",
                      json={**valid_schema(), "revenue_column": "Contract"})
    assert bad.status_code == 422
    assert any("must be numeric" in p for p in bad.json()["detail"]["problems"])
    good = client.post(f"/confirm-schema/{session_id}",
                       json={**valid_schema(), "revenue_column": "MonthlyCharges"})
    assert good.status_code == 200
