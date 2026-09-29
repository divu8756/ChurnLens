"""Experiment use cases: create / edit a draft, approve, assign, export (runbook T5c.2).
Raises ServiceError with an HTTP status; the router turns it into a response."""

import io
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pandas as pd
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.experiments.assignment import assign_groups, balance_check, snapshot_hash
from app.experiments.data import NotAnalysed, cached_messages, session_customers
from app.experiments.lifecycle import audit, change_status
from app.experiments.models import Assignment, AuditLog, Experiment
from app.experiments.schemas import (
    ApproveRequest,
    ExperimentCreate,
    ExperimentDesignFields,
    ExperimentUpdate,
)
from app.experiments.segments import SegmentError, apply_segment
from app.stats.experiment_design import DesignError, sample_size

# Loads the analysed graph state of a session; raises ServiceError(410) when it expired.
ValuesLoader = Callable[[str], dict[str, Any]]
ACTIVE = ("running", "results_uploaded")
DESIGN_DEFAULTS = {"alpha": 0.05, "power": 0.8, "control_share": 0.5}


class ServiceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def get_experiment(db: Session, experiment_id: int) -> Experiment:
    exp = db.get(Experiment, experiment_id)
    if exp is None:
        raise ServiceError(404, f"Experiment {experiment_id} not found.")
    return exp


def audit_trail(db: Session, experiment_id: int) -> list[AuditLog]:
    return list(db.scalars(select(AuditLog).where(AuditLog.experiment_id == experiment_id)
                           .order_by(AuditLog.id)))


def _customers(values: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, str]]:
    try:
        return session_customers(values)
    except NotAnalysed as exc:
        raise ServiceError(409, str(exc)) from None


def _segment(customers: pd.DataFrame, segment: Any) -> pd.DataFrame:
    try:
        return apply_segment(customers, segment)
    except SegmentError as exc:
        raise ServiceError(422, str(exc)) from None


def build_design(fields: ExperimentDesignFields, load: ValuesLoader) -> dict[str, Any]:
    """Sample size for the design, measured against the session's customers if given."""
    n_available: int | None = None
    measured: float | None = None
    if fields.session_id:
        values = load(fields.session_id)
        segment = _segment(_customers(values)[0], fields.segment_definition)
        if segment.empty:
            raise ServiceError(422, "No customers match this segment.")
        n_available = len(segment)
        measured = float(segment["actual_churn"].mean())
        rec_id = fields.source_recommendation_id
        if rec_id and rec_id not in {r.get("id") for r in values.get("final_recommendations")
                                     or []}:
            raise ServiceError(422, f"Recommendation '{rec_id}' is not in this session.")
    baseline = fields.baseline_rate if fields.baseline_rate is not None else measured
    if baseline is None or not 0 < baseline < 1:
        raise ServiceError(422, "The segment's measured churn rate is 0% or 100%; enter a "
                                "baseline_rate instead.")
    try:
        design = sample_size(baseline, fields.mde, alpha=fields.alpha, power=fields.power,
                             control_share=fields.control_share, mde_type=fields.mde_type,
                             n_available=n_available, monthly_volume=fields.monthly_volume)
    except DesignError as exc:
        raise ServiceError(422, str(exc)) from None
    user_set = fields.model_fields_set
    design["measured_segment_churn"] = measured
    design["assumptions"] = [
        {"name": "baseline_rate", "value": baseline,
         "source": "user" if fields.baseline_rate is not None else "data"},
        *({"name": key, "value": getattr(fields, key),
           "source": "user" if key in user_set else "default"} for key in DESIGN_DEFAULTS),
    ]
    return design


def _apply_design(exp: Experiment, fields: ExperimentDesignFields, design: dict[str, Any]
                  ) -> None:
    exp.name, exp.hypothesis, exp.offer = fields.name, fields.hypothesis, fields.offer
    exp.source_recommendation_id = fields.source_recommendation_id
    exp.source_session_id = fields.session_id
    exp.segment_definition = fields.segment_definition.model_dump()
    exp.outcome_window_days = fields.outcome_window_days
    exp.guardrail_metrics = list(fields.guardrail_metrics)
    exp.baseline_rate = design["inputs"]["baseline_rate"]
    exp.mde, exp.mde_type = fields.mde, fields.mde_type
    exp.alpha, exp.power, exp.control_share = fields.alpha, fields.power, fields.control_share
    exp.n_required_treatment = design["n_treatment"]
    exp.n_required_control = design["n_control"]
    exp.planned_start, exp.planned_end = fields.planned_start, fields.planned_end
    exp.design = design


def create(db: Session, payload: ExperimentCreate, load: ValuesLoader) -> Experiment:
    design = build_design(payload, load)
    exp = Experiment(created_by=payload.created_by, status="draft", primary_metric="churn")
    _apply_design(exp, payload, design)
    db.add(exp)
    db.flush()
    audit(db, exp, payload.created_by, "created", to_status="draft",
          details={"n_required_treatment": exp.n_required_treatment,
                   "n_required_control": exp.n_required_control})
    return exp


def _current_fields(exp: Experiment) -> dict[str, Any]:
    design = exp.design or {}
    baseline_from_data = any(a["name"] == "baseline_rate" and a["source"] == "data"
                             for a in design.get("assumptions", []))
    return {
        "name": exp.name, "hypothesis": exp.hypothesis,
        "source_recommendation_id": exp.source_recommendation_id,
        "session_id": exp.source_session_id, "segment_definition": exp.segment_definition,
        "offer": exp.offer, "outcome_window_days": exp.outcome_window_days,
        "guardrail_metrics": exp.guardrail_metrics,
        # A measured baseline is measured again (the segment may have changed).
        "baseline_rate": None if baseline_from_data else exp.baseline_rate,
        "mde": exp.mde, "mde_type": exp.mde_type, "alpha": exp.alpha, "power": exp.power,
        "control_share": exp.control_share,
        "monthly_volume": (design.get("inputs") or {}).get("monthly_volume"),
        "planned_start": exp.planned_start, "planned_end": exp.planned_end,
    }


def update(db: Session, exp: Experiment, patch: ExperimentUpdate, load: ValuesLoader
           ) -> Experiment:
    if exp.status != "draft":
        raise ServiceError(409, f"Only drafts can be edited; this experiment is {exp.status}.")
    changes = patch.model_dump(exclude_unset=True, exclude={"actor"})
    current = _current_fields(exp)
    merged = {**current, **changes}
    try:
        fields = ExperimentDesignFields.model_validate(merged)
    except ValueError as exc:
        raise ServiceError(422, str(exc)) from None
    # Keep "user" vs "default" sources: only fields the user ever set count as set.
    previous_sources = {a["name"]: a["source"] for a in (exp.design or {}).get("assumptions", [])}
    fields.model_fields_set.difference_update(
        {k for k in DESIGN_DEFAULTS if previous_sources.get(k) == "default"
         and k not in changes})
    design = build_design(fields, load)
    _apply_design(exp, fields, design)
    audit(db, exp, patch.actor, "edited", note=", ".join(sorted(changes)) or None,
          details={"changed": sorted(changes)})
    return exp


def approve(db: Session, exp: Experiment, request: ApproveRequest) -> Experiment:
    if not request.cost_and_eligibility_reviewed:
        raise ServiceError(422, "Confirm that the offer cost and eligibility were reviewed.")
    if exp.status != "draft":
        raise ServiceError(409, f"Only drafts can be approved; this experiment is {exp.status}.")
    exp.approved_by = request.approver
    exp.approved_at = datetime.now(UTC)
    change_status(db, exp, "approved", request.approver, note=request.note,
                  details={"cost_and_eligibility_reviewed": True})
    return exp


def busy_customers(db: Session, experiment_id: int) -> set[str]:
    """Customers already assigned to another experiment that is still running."""
    rows = db.scalars(
        select(Assignment.customer_id).join(Experiment, Experiment.id == Assignment.experiment_id)
        .where(Experiment.status.in_(ACTIVE), Experiment.id != experiment_id))
    return set(rows)


def assign(db: Session, exp: Experiment, session_id: str, actor: str, load: ValuesLoader
           ) -> Experiment:
    if exp.status != "approved":
        raise ServiceError(409, f"Only approved experiments can be assigned; this one is "
                                f"{exp.status}.")
    customers, covariates = _customers(load(session_id))
    segment = _segment(customers, exp.segment_definition)
    busy = busy_customers(db, exp.id)
    eligible = segment[~segment["customer_id"].isin(busy)].reset_index(drop=True)
    excluded = len(segment) - len(eligible)
    if eligible.empty:
        raise ServiceError(409, "No customers left to assign: the segment is empty or every "
                                "customer is already in another running experiment.")

    ids = eligible["customer_id"].astype(str).tolist()
    arms = assign_groups(exp.id, ids, exp.control_share)
    eligible = eligible.assign(group=arms)
    balance = balance_check(eligible, covariates)
    snapshot = snapshot_hash(eligible[["customer_id", *covariates]])
    messages = cached_messages(session_id, exp.offer)

    rows = [{"experiment_id": exp.id, "customer_id": cid, "arm": arm,
             "offer": exp.offer if arm == "treatment" else None,
             "message": messages.get(cid) if arm == "treatment" else None,
             "assigned_at": datetime.now(UTC)} for cid, arm in zip(ids, arms, strict=True)]
    db.execute(insert(Assignment), rows)

    n_treat, n_ctrl = arms.count("treatment"), arms.count("control")
    warnings: list[str] = []
    if n_treat < exp.n_required_treatment or n_ctrl < exp.n_required_control:
        warnings.append(
            f"Under-powered: {n_treat:,} treatment / {n_ctrl:,} control assigned, but the "
            f"design needs {exp.n_required_treatment:,} / {exp.n_required_control:,}.")
    if excluded:
        warnings.append(f"{excluded:,} segment customers were left out because they are "
                        "already in another running experiment.")
    if not balance["balanced"]:
        warnings.append("Groups differ on " + ", ".join(balance["flagged"]) + " (|SMD| > 0.1). "
                        "Treat the results with caution.")
    summary = {
        "segment_customers": len(segment), "excluded_other_experiments": excluded,
        "assigned": len(ids), "n_treatment": n_treat, "n_control": n_ctrl,
        "required_treatment": exp.n_required_treatment,
        "required_control": exp.n_required_control,
        "messages_attached": sum(1 for r in rows if r["message"]),
        "data_snapshot_hash": snapshot, "balance": balance, "warnings": warnings,
    }
    exp.data_snapshot_hash = snapshot
    exp.assignment_summary = summary
    change_status(db, exp, "running", actor, action="assigned",
                  details={"session_id": session_id, "assigned": len(ids),
                           "n_treatment": n_treat, "n_control": n_ctrl,
                           "data_snapshot_hash": snapshot, "imbalanced": balance["flagged"]})
    return exp


def assignment_csv(db: Session, exp: Experiment) -> str:
    if exp.status not in (*ACTIVE, "decided"):
        raise ServiceError(409, "This experiment has not been assigned yet.")
    rows = db.execute(select(Assignment.customer_id, Assignment.arm, Assignment.offer,
                             Assignment.message)
                      .where(Assignment.experiment_id == exp.id).order_by(Assignment.id)).all()
    frame = pd.DataFrame(rows, columns=["customer_id", "group", "offer", "message"])
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False)
    return buffer.getvalue()
