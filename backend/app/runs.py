"""Runs the analysis graph in background threads and records events for SSE.

One Run per session (thread_id = session_id). Events are kept in memory in
order, with increasing ids, so an SSE client can reconnect with
Last-Event-ID and continue where it left off.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.graph.state import ErrorEntry, ProgressEntry
from app.run_history import save_run

logger = logging.getLogger("churnlens.runs")

RunStatus = Literal["running", "awaiting_confirmation", "done", "failed"]


class RunConflict(RuntimeError):
    """The requested action does not fit the run's current status."""


@dataclass
class Event:
    id: int
    event: str
    data: dict[str, Any]


@dataclass
class Run:
    session_id: str
    status: RunStatus = "running"
    events: list[Event] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def emit(self, event: str, data: dict[str, Any]) -> None:
        with self._lock:
            self.events.append(Event(len(self.events) + 1, event, data))

    def events_after(self, last_id: int) -> list[Event]:
        with self._lock:
            return self.events[last_id:]


def _dump(value: Any) -> Any:
    if isinstance(value, ErrorEntry | ProgressEntry):
        return value.model_dump()
    return value


class RunManager:
    def __init__(self, graph_factory: Callable[[], CompiledStateGraph]) -> None:
        self._graph_factory = graph_factory
        self._graph: CompiledStateGraph | None = None
        self._runs: dict[str, Run] = {}
        self._lock = threading.Lock()

    @property
    def graph(self) -> CompiledStateGraph:
        with self._lock:
            if self._graph is None:
                self._graph = self._graph_factory()
            return self._graph

    def get(self, session_id: str) -> Run | None:
        with self._lock:
            return self._runs.get(session_id)

    def start(self, session_id: str) -> Run:
        """Start the run once; later calls return the existing run."""
        graph = self.graph
        with self._lock:
            existing = self._runs.get(session_id)
            if existing is not None:
                return existing
            run = Run(session_id)
            self._runs[session_id] = run
        self._spawn(graph, run, {"session_id": session_id})
        return run

    def resume(self, session_id: str, answer: dict[str, Any]) -> Run:
        graph = self.graph
        with self._lock:
            run = self._runs.get(session_id)
            if run is None:
                raise LookupError(session_id)
            if run.status != "awaiting_confirmation":
                raise RunConflict(f"The run is {run.status}, not waiting for confirmation.")
            run.status = "running"
        run.emit("resumed", {})
        self._spawn(graph, run, Command(resume=answer))
        return run

    def pending_interrupt(self, session_id: str) -> Any | None:
        snapshot = self.graph.get_state(self._config(session_id))
        return snapshot.interrupts[0].value if snapshot.interrupts else None

    # ------------------------------------------------------------ internals

    @staticmethod
    def _config(session_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": session_id}}

    def _spawn(self, graph: CompiledStateGraph, run: Run, graph_input: Any) -> None:
        thread = threading.Thread(target=self._drive, args=(graph, run, graph_input),
                                  name=f"run-{run.session_id[:8]}", daemon=True)
        thread.start()

    def _drive(self, graph: CompiledStateGraph, run: Run, graph_input: Any) -> None:
        config = self._config(run.session_id)
        try:
            for mode, chunk in graph.stream(graph_input, config,
                                            stream_mode=["tasks", "updates"]):
                if mode == "tasks":
                    self._on_task(run, chunk)
            snapshot = graph.get_state(config)
            if snapshot.interrupts:
                value = snapshot.interrupts[0].value
                run.status = "awaiting_confirmation"
                run.emit("awaiting_confirmation", value if isinstance(value, dict) else {})
                return
            final_error = snapshot.values.get("final_error")
            save_run(run.session_id, snapshot.values)
            run.status = "failed" if final_error else "done"
            run.emit("done", {"ok": not final_error, "final_error": final_error})
        except Exception as exc:  # the graph itself broke; tell the client and stop
            logger.exception("run %s crashed", run.session_id)
            run.status = "failed"
            run.emit("error", {"node": None, "message": f"{type(exc).__name__}: {exc}",
                               "fatal": True})
            run.emit("done", {"ok": False, "final_error": "The analysis crashed unexpectedly."})

    @staticmethod
    def _on_task(run: Run, chunk: dict[str, Any]) -> None:
        node = chunk.get("name")
        if "input" in chunk:
            run.emit("node_start", {"node": node})
            return
        if chunk.get("interrupts"):
            return  # reported as awaiting_confirmation once the stream stops
        result = chunk.get("result") or {}
        status = "done"
        progress = result.get("progress") or []
        if progress:
            status = _dump(progress[-1])["status"]
        for error in result.get("errors") or []:
            run.emit("error", _dump(error))
        detail = _dump(progress[-1]).get("detail") if progress else None
        run.emit("node_finish", {"node": node, "status": status, "detail": detail})
