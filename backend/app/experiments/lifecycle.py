"""Experiment lifecycle: draft -> approved -> running -> results_uploaded -> decided.
Every status change goes through change_status(), which writes an audit row."""

from typing import Any

from sqlalchemy.orm import Session

from app.experiments.models import AuditLog, Experiment

TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft": ("approved",),
    "approved": ("running",),
    "running": ("results_uploaded",),
    # A newer results file may replace the previous one before the decision.
    "results_uploaded": ("results_uploaded", "decided"),
    "decided": (),
}


class TransitionError(ValueError):
    """The requested status change is not allowed from the current status."""


def audit(session: Session, experiment: Experiment, actor: str, action: str, *,
          from_status: str | None = None, to_status: str | None = None,
          note: str | None = None, details: dict[str, Any] | None = None) -> AuditLog:
    entry = AuditLog(experiment_id=experiment.id, actor=actor, action=action,
                     from_status=from_status, to_status=to_status, note=note, details=details)
    session.add(entry)
    return entry


def change_status(session: Session, experiment: Experiment, to_status: str, actor: str, *,
                  action: str | None = None, note: str | None = None,
                  details: dict[str, Any] | None = None) -> AuditLog:
    current = experiment.status
    if to_status not in TRANSITIONS.get(current, ()):
        raise TransitionError(f"Cannot move an experiment from '{current}' to '{to_status}'.")
    experiment.status = to_status
    session.flush()
    return audit(session, experiment, actor, action or to_status, from_status=current,
                 to_status=to_status, note=note, details=details)
