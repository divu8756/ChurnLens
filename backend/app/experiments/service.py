"""Experiment use cases: create / edit a draft, approve, assign, export (runbook T5c.2).
Raises ServiceError with an HTTP status; the router turns it into a response."""

import hashlib
import io
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.experiments.assignment import assign_groups, balance_check, snapshot_hash
from app.experiments.data import NotAnalysed, cached_messages, session_customers
from app.experiments.lifecycle import audit, change_status
from app.experiments.models import Assignment, AuditLog, Experiment, OfferEvidence, Outcome
from app.experiments.results import (
    ResultsInvalid,
    early_look_warning,
    outcome_rows,
    parse_results,
)
from app.experiments.schemas import (
    AnalysisAssumptions,
    ApproveRequest,
    DecideRequest,
    DesignInputs,
    ExperimentCreate,
    ExperimentDesignFields,
    ExperimentUpdate,
)
from app.experiments.segments import SegmentError, apply_segment
from app.experiments.simulate import simulate_results
from app.experiments.summary import generate as generate_summary
from app.stats.common import jsonable
from app.stats.experiment_analysis import analyse
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


def build_design(fields: DesignInputs, load: ValuesLoader) -> dict[str, Any]:
    """Sample size for the design, measured against the session's customers if given."""
    n_available: int | None = None
    measured: float | None = None
    if fields.session_id:
        values = load(fields.session_id)
        segment = _segment(_customers(values)[0], fields.segment_definition)
        if segment.empty:
            raise ServiceError(422, "No customers match this segment.")
        n_available = len(segment)
        for named in fields.preregistered_segments:
            _segment(segment, {"filters": [f.model_dump() for f in named.filters]})
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
    exp.preregistered_segments = [seg.model_dump() for seg in fields.preregistered_segments]
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
        "preregistered_segments": exp.preregistered_segments or [],
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
        .where(Experiment.status.in_(ACTIVE), Experiment.id != experiment_id,
               Experiment.demo.is_(False)))
    return set(rows)


def _memberships(frame: pd.DataFrame, segments: list[dict[str, Any]]) -> list[list[str]]:
    member_ids = {seg["name"]: set(_segment(frame, seg)["customer_id"]) for seg in segments}
    return [[name for name, ids in member_ids.items() if cid in ids]
            for cid in frame["customer_id"]]


def _customer_value(values: dict[str, Any], frame: pd.DataFrame) -> float | None:
    """Mean monthly revenue of the assigned customers x the NBO horizon (Phase 5b)."""
    col = (values.get("confirmed_schema") or {}).get("revenue_column")
    if not col or col not in frame.columns:
        return None
    revenue = pd.to_numeric(frame[col], errors="coerce").dropna()
    return float(revenue.mean() * get_settings().NBO_HORIZON_MONTHS) if len(revenue) else None


def assign(db: Session, exp: Experiment, session_id: str, actor: str, load: ValuesLoader
           ) -> Experiment:
    if exp.status != "approved":
        raise ServiceError(409, f"Only approved experiments can be assigned; this one is "
                                f"{exp.status}.")
    values = load(session_id)
    customers, covariates = _customers(values)
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
    memberships = _memberships(eligible, exp.preregistered_segments or [])

    now = datetime.now(UTC)
    rows = [{"experiment_id": exp.id, "customer_id": cid, "arm": arm,
             "offer": exp.offer if arm == "treatment" else None,
             "message": messages.get(cid) if arm == "treatment" else None,
             "segments": member, "assigned_at": now}
            for cid, arm, member in zip(ids, arms, memberships, strict=True)]
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
        "customer_value_estimate": _customer_value(values, eligible),
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


def _design_inputs(exp: Experiment) -> dict[str, Any]:
    return {"control_share": exp.control_share, "alpha": exp.alpha, "power": exp.power,
            "baseline_rate": exp.baseline_rate, "mde": exp.mde, "mde_type": exp.mde_type,
            "guardrail_metrics": exp.guardrail_metrics}


def _analysis_assumptions(exp: Experiment, given: AnalysisAssumptions) -> dict[str, Any]:
    estimate = (exp.assignment_summary or {}).get("customer_value_estimate")
    user_value = given.customer_value is not None
    return {
        "customer_value": given.customer_value if user_value else estimate,
        "customer_value_source": "user" if user_value else "data",
        "offer_cost": given.offer_cost, "offer_cost_source": "user",
        "arpu_tolerance": given.arpu_tolerance,
        "arpu_tolerance_source": "user" if "arpu_tolerance" in given.model_fields_set
        else "default",
    }


def _outcomes_frame(db: Session, exp: Experiment) -> pd.DataFrame:
    rows = db.execute(
        select(Outcome.customer_id, Outcome.arm, Outcome.offer_accepted, Outcome.churned,
               Outcome.revenue, Outcome.complaints, Assignment.segments)
        .join(Assignment, (Assignment.experiment_id == Outcome.experiment_id)
              & (Assignment.customer_id == Outcome.customer_id))
        .where(Outcome.experiment_id == exp.id)).all()
    frame = pd.DataFrame(rows, columns=["customer_id", "arm", "offer_accepted", "churned",
                                        "revenue", "complaints", "segments"])
    for col in ("revenue", "complaints"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def _run_analysis(db: Session, exp: Experiment, assumptions: AnalysisAssumptions,
                  upload: dict[str, Any]) -> dict[str, Any]:
    names = [seg["name"] for seg in exp.preregistered_segments or []]
    result = analyse(_outcomes_frame(db, exp), _design_inputs(exp),
                     _analysis_assumptions(exp, assumptions), names)
    result["upload"] = upload
    result["warnings"] = list(upload.get("warnings", []))
    if result["srm"]["failed"]:
        result["warnings"].insert(0, "Sample ratio mismatch: results not trustworthy.")
    result["assumption_inputs"] = assumptions.model_dump()
    return jsonable(result)


def upload_results(db: Session, exp: Experiment, content: bytes, uploaded_by: str,
                   assumptions: AnalysisAssumptions) -> Experiment:
    if exp.status not in ACTIVE:
        raise ServiceError(409, f"Results can be uploaded only for a running experiment; "
                                f"this one is {exp.status}.")
    if len(content) > get_settings().MAX_UPLOAD_MB * 1024 * 1024:
        raise ServiceError(413, f"The file is larger than {get_settings().MAX_UPLOAD_MB} MB.")
    assignment = dict(db.execute(select(Assignment.customer_id, Assignment.arm)
                                 .where(Assignment.experiment_id == exp.id)).all())
    try:
        outcomes, warnings = parse_results(content, assignment, planned_start=exp.planned_start,
                                           window_days=exp.outcome_window_days)
    except ResultsInvalid as exc:
        raise ServiceError(422, "Results do not match the assignment: " + str(exc)) from None
    early = early_look_warning(datetime.now(UTC).date(), exp.planned_start, exp.planned_end,
                               exp.outcome_window_days)
    if early:
        warnings.insert(0, early)

    db.execute(delete(Outcome).where(Outcome.experiment_id == exp.id))
    db.execute(insert(Outcome), outcome_rows(exp.id, outcomes))
    db.flush()
    upload = {"rows": len(outcomes), "file_sha256": hashlib.sha256(content).hexdigest(),
              "uploaded_by": uploaded_by, "early_look": early is not None,
              "warnings": warnings}
    exp.analysis = _run_analysis(db, exp, assumptions, upload)
    exp.results_uploaded_at = datetime.now(UTC)
    change_status(db, exp, "results_uploaded", uploaded_by, action="results_uploaded",
                  details={"rows": len(outcomes), "file_sha256": upload["file_sha256"],
                           "early_look": upload["early_look"],
                           "srm_failed": exp.analysis["srm"]["failed"],
                           "verdict": exp.analysis["decision_helper"]["verdict"]})
    return exp


def reanalyse(db: Session, exp: Experiment, assumptions: AnalysisAssumptions, actor: str
              ) -> Experiment:
    """Recompute the analysis with new money / guardrail assumptions (same outcomes)."""
    if exp.status != "results_uploaded" or not exp.analysis:
        raise ServiceError(409, "Upload results before changing the analysis assumptions.")
    exp.analysis = _run_analysis(db, exp, assumptions, exp.analysis.get("upload", {}))
    audit(db, exp, actor, "reanalysed", details={"assumptions": assumptions.model_dump(),
                                                 "verdict": exp.analysis["decision_helper"]
                                                 ["verdict"]})
    return exp


def _evidence(exp: Experiment) -> OfferEvidence:
    itt = exp.analysis["itt"]
    t, c = itt["arms"]["treatment"], itt["arms"]["control"]
    accept = exp.analysis["impact"].get("acceptance_rate")
    reduction = c["rate"] - t["rate"]
    lift = (min(1.0, max(0.0, reduction / accept)) if accept else None)
    return OfferEvidence(
        experiment_id=exp.id, offer=exp.offer,
        segment_description=(exp.segment_definition or {}).get("description") or None,
        decision=exp.decision or "", decided_at=datetime.now(UTC),
        n_treatment=t["n"], n_control=c["n"], treatment_churn=t["rate"],
        control_churn=c["rate"], itt_difference=itt["difference"]["value"],
        ci_low=itt["difference"]["ci_low"], ci_high=itt["difference"]["ci_high"],
        acceptance_rate=accept, retention_lift_per_acceptor=lift)


def decide(db: Session, exp: Experiment, request: DecideRequest) -> Experiment:
    if exp.status != "results_uploaded" or not exp.analysis:
        raise ServiceError(409, f"Upload results before deciding; this experiment is "
                                f"{exp.status}.")
    if request.decision == "ship" and exp.analysis["srm"]["failed"]:
        raise ServiceError(409, "Shipping is blocked: the sample ratio mismatch check failed, "
                                "so the results are not trustworthy.")
    exp.decision, exp.decision_note = request.decision, request.note
    details = {"verdict": exp.analysis["decision_helper"]["verdict"]}
    if request.decision == "extend":
        if request.new_planned_end:
            details["new_planned_end"] = request.new_planned_end.isoformat()
            exp.planned_end = request.new_planned_end
        change_status(db, exp, "running", request.decider, action="decided_extend",
                      note=request.note, details=details)
        return exp
    change_status(db, exp, "decided", request.decider, action=f"decided_{request.decision}",
                  note=request.note, details=details)
    # Feedback loop: a measured effect beats an observational one in next best offer.
    # SRM-failed results never become evidence.
    if not exp.analysis["srm"]["failed"] and not exp.demo:
        db.add(_evidence(exp))
    return exp


def offer_evidence(db: Session) -> list[OfferEvidence]:
    return list(db.scalars(select(OfferEvidence).order_by(OfferEvidence.decided_at.desc(),
                                                          OfferEvidence.id.desc())))


def summary(db: Session, exp: Experiment) -> dict[str, Any]:
    """The validated plain-English summary, generated once per analysis (cached in it)."""
    if not exp.analysis:
        raise ServiceError(409, "Upload results before asking for a summary.")
    cached = exp.analysis.get("summary")
    if cached:
        return cached
    result = generate_summary(exp.analysis, exp.offer)
    # Reassign so SQLAlchemy sees the JSON change.
    exp.analysis = {**exp.analysis, "summary": result}
    audit(db, exp, "system", "summary_generated", details={"source": result["source"]})
    return result


MAX_LEVELS = 30
SKIP_COLUMNS = ("customer_id", "actual_churn")


def segment_options(values: dict[str, Any]) -> list[dict[str, Any]]:
    """Columns a segment filter can use, with levels / ranges for the filter builder."""
    customers, _ = _customers(values)
    schema = values.get("confirmed_schema") or {}
    hidden = {*SKIP_COLUMNS, schema.get("target_column"), *schema.get("id_columns", [])}
    options: list[dict[str, Any]] = []
    for col in customers.columns:
        if col in hidden:
            continue
        series = customers[col]
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series) \
                and series.nunique(dropna=True) > 2:
            options.append({"column": str(col), "kind": "numeric",
                            "min": _finite(series.min()), "max": _finite(series.max())})
        else:
            levels = series.dropna().astype(str).value_counts().index[:MAX_LEVELS].tolist()
            options.append({"column": str(col), "kind": "categorical", "levels": levels})
    return options


def _finite(value: Any) -> float | None:
    number = float(value) if pd.notna(value) else None
    return number if number is not None and abs(number) != float("inf") else None


DEMO_OFFER_FALLBACK = "Retention offer"
DEMO_ACTOR = "demo"
DEMO_ASSUMPTIONS = AnalysisAssumptions(offer_cost=20.0)


def create_demo(db: Session, session_id: str, load: ValuesLoader, *, is_sample: bool
                ) -> Experiment:
    """A worked example on the sample data: designed, approved, assigned and given a
    simulated results file with a known effect (control 26% vs treatment 21% churn).
    Left at "results uploaded" so the user makes the decision. Not real evidence: demo
    experiments never feed next best offer and never block real experiments."""
    if not is_sample:
        raise ServiceError(409, "Demo experiments are only available for the sample data.")
    values = load(session_id)
    catalog = [o.get("offer") for o in
               ((values.get("offer_effectiveness") or {}).get("offers") or [])]
    offer = next((o for o in catalog if o), DEMO_OFFER_FALLBACK)
    today = datetime.now(UTC).date()
    fields = ExperimentDesignFields(
        name=f"Demo: {offer} for month-to-month customers",
        hypothesis=f"Offering {offer} lowers 90-day churn among month-to-month customers. "
                   "(Demo: the results file is simulated with a known effect.)",
        session_id=session_id,
        segment_definition={"description": "Contract = Month-to-month", "filters": [
            {"column": "Contract", "op": "eq", "value": "Month-to-month"}]},
        offer=offer, mde=0.05, outcome_window_days=90,
        planned_start=today - timedelta(days=120), planned_end=today - timedelta(days=30),
        preregistered_segments=[{"name": "New customers (tenure <= 12)", "filters": [
            {"column": "tenure", "op": "lte", "value": 12}]}],
    )
    try:
        design = build_design(fields, load)
    except ServiceError as exc:
        raise ServiceError(409, f"The demo needs the sample data's columns: {exc.detail}"
                           ) from None
    exp = Experiment(created_by=DEMO_ACTOR, status="draft", primary_metric="churn", demo=True)
    _apply_design(exp, fields, design)
    db.add(exp)
    db.flush()
    audit(db, exp, DEMO_ACTOR, "created", to_status="draft", note="demo experiment")
    approve(db, exp, ApproveRequest(approver=DEMO_ACTOR, cost_and_eligibility_reviewed=True,
                                    note="demo"))
    assign(db, exp, session_id, DEMO_ACTOR, lambda _: values)
    rows = db.execute(select(Assignment.customer_id, Assignment.arm)
                      .where(Assignment.experiment_id == exp.id)).all()
    assignment = pd.DataFrame(rows, columns=["customer_id", "group"])
    results = simulate_results(assignment, "real_effect")
    upload_results(db, exp, results.to_csv(index=False).encode(), DEMO_ACTOR, DEMO_ASSUMPTIONS)
    return exp
