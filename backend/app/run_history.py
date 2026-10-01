"""Persist and list run telemetry summaries (the `runs` table, experiments database)."""

import logging
from typing import Any

from sqlalchemy import select

from app import sessions
from app.catalog import load_pricing
from app.experiments.db import session_scope
from app.experiments.models import RunSummary
from app.graph.telemetry import summarise_run

logger = logging.getLogger("churnlens")


def workspace_of(session_id: str) -> str | None:
    try:
        return sessions.read_meta(session_id).get("workspace_hash")
    except sessions.SessionNotFound:
        return None


def save_run(session_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
    """Summarise a finished run and store it. Never raises: telemetry must not break a run."""
    try:
        summary = summarise_run(values, load_pricing())
        with session_scope() as db:
            db.add(RunSummary(session_id=session_id, workspace_hash=workspace_of(session_id),
                              status=summary["status"], summary=summary))
        return summary
    except Exception:
        logger.exception("could not save the run summary for %s", session_id)
        return None


def list_runs(workspace: str | None, limit: int = 50) -> list[dict[str, Any]]:
    """Newest first; only runs uploaded from this workspace."""
    if not workspace:
        return []
    with session_scope() as db:
        rows = db.scalars(select(RunSummary).where(RunSummary.workspace_hash == workspace)
                          .order_by(RunSummary.id.desc()).limit(limit))
        return [{**r.summary, "created_at": r.created_at.isoformat()} for r in rows]
