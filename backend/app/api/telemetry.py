"""Run telemetry (Phase 5d): the current run's summary and the workspace's run history."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app import sessions
from app.api.contract import HTTPErrorOut
from app.api.metrics_contract import RunSummaryOut
from app.catalog import load_pricing
from app.experiments.workspace import optional_workspace
from app.graph.telemetry import summarise_run
from app.run_history import list_runs

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
ERRORS: dict[int | str, dict[str, Any]] = {code: {"model": HTTPErrorOut} for code in (409, 410)}


@router.get("/runs", response_model=list[RunSummaryOut])
def runs(workspace: Annotated[str | None, Depends(optional_workspace)],
         limit: Annotated[int, Query(ge=1, le=200)] = 50) -> list[RunSummaryOut]:
    """Finished runs uploaded from this browser (X-Workspace-Key), newest first."""
    return [RunSummaryOut(**r) for r in list_runs(workspace, limit)]


@router.get("/{session_id}", response_model=RunSummaryOut, responses=ERRORS)
def run_summary(session_id: str, request: Request) -> RunSummaryOut:
    """Live summary of this session's run (also while it is still running)."""
    try:
        sessions.read_meta(session_id)
    except sessions.SessionNotFound:
        raise HTTPException(410, "Session expired, please re-upload.") from None
    graph = request.app.state.runs.graph
    values = graph.get_state({"configurable": {"thread_id": session_id}}).values or {}
    if not values:
        raise HTTPException(409, "The analysis has not been started for this session.")
    return RunSummaryOut(**summarise_run(values, load_pricing()))
