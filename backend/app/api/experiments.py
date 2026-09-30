"""A/B experiments: design, approval gate, assignment and export (T5c.2)."""

from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app import sessions
from app.api.contract import HTTPErrorOut
from app.config import get_settings
from app.experiments import service
from app.experiments.db import session_scope
from app.experiments.models import Experiment
from app.experiments.schemas import (
    AnalysisAssumptions,
    ApproveRequest,
    AssignRequest,
    AuditEntryOut,
    DecideRequest,
    DemoRequest,
    DesignInputs,
    DesignOut,
    ExperimentCreate,
    ExperimentOut,
    ExperimentSummary,
    ExperimentSummaryOut,
    ExperimentUpdate,
    OfferEvidenceOut,
    ReanalyseRequest,
    SegmentColumn,
)
from app.experiments.workspace import required_workspace
from app.ratelimit import enforce

router = APIRouter(prefix="/experiments", tags=["experiments"])
ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": HTTPErrorOut} for code in (404, 409, 410, 413)}


def get_db() -> Iterator[Session]:
    with session_scope() as db:
        yield db


DB = Annotated[Session, Depends(get_db)]
Workspace = Annotated[str, Depends(required_workspace)]


def values_loader(request: Request) -> service.ValuesLoader:
    def load(session_id: str) -> dict[str, Any]:
        try:
            sessions.read_meta(session_id)
        except sessions.SessionNotFound:
            raise service.ServiceError(410, "Session expired, please re-upload.") from None
        graph = request.app.state.runs.graph
        return graph.get_state({"configurable": {"thread_id": session_id}}).values or {}
    return load


def _out(db: Session, exp: Experiment) -> ExperimentOut:
    db.commit()
    out = ExperimentOut.model_validate(exp, from_attributes=True)
    out.audit = [AuditEntryOut.model_validate(a) for a in service.audit_trail(db, exp.id)]
    return out


def _call(fn: Any, *args: Any) -> Any:
    try:
        return fn(*args)
    except service.ServiceError as exc:
        raise HTTPException(exc.status_code, exc.detail) from None


@router.post("", response_model=ExperimentOut, status_code=201, responses=ERRORS)
def create_experiment(payload: ExperimentCreate, request: Request, db: DB,
                      ws: Workspace) -> ExperimentOut:
    exp = _call(service.create, db, payload, values_loader(request), ws)
    return _out(db, exp)


@router.get("", response_model=list[ExperimentSummary])
def list_experiments(db: DB, ws: Workspace) -> list[ExperimentSummary]:
    return [ExperimentSummary.model_validate(e) for e in service.list_experiments(db, ws)]


@router.post("/demo", response_model=ExperimentOut, status_code=201, responses=ERRORS)
def create_demo(body: DemoRequest, request: Request, db: DB, ws: Workspace) -> ExperimentOut:
    """Sample data only: a worked example with a simulated, known-effect results file."""
    load = values_loader(request)
    _call(load, body.session_id)  # 410 when the session expired
    is_sample = bool(sessions.read_meta(body.session_id).get("sample"))
    exp = _call(lambda: service.create_demo(db, body.session_id, load, ws, is_sample=is_sample))
    return _out(db, exp)


@router.post("/design", response_model=DesignOut, responses=ERRORS)
def preview_design(body: DesignInputs, request: Request) -> DesignOut:
    """Sample size for a design without saving it (live feedback in the wizard)."""
    return DesignOut(**_call(service.build_design, body, values_loader(request)))


@router.get("/segment-options/{session_id}", response_model=list[SegmentColumn],
            responses=ERRORS)
def segment_options(session_id: str, request: Request) -> list[SegmentColumn]:
    values = _call(values_loader(request), session_id)
    return [SegmentColumn(**o) for o in _call(service.segment_options, values)]


@router.get("/offer-evidence", response_model=list[OfferEvidenceOut])
def list_offer_evidence(db: DB, ws: Workspace) -> list[OfferEvidenceOut]:
    """Measured offer effects from decided experiments (used by next best offer)."""
    return [OfferEvidenceOut.model_validate(e) for e in service.offer_evidence(db, ws)]


@router.get("/{experiment_id}", response_model=ExperimentOut, responses=ERRORS)
def get_experiment(experiment_id: int, db: DB, ws: Workspace) -> ExperimentOut:
    return _out(db, _call(service.get_experiment, db, experiment_id, ws))


@router.patch("/{experiment_id}", response_model=ExperimentOut, responses=ERRORS)
def update_experiment(experiment_id: int, patch: ExperimentUpdate, request: Request,
                      db: DB, ws: Workspace) -> ExperimentOut:
    exp = _call(service.get_experiment, db, experiment_id, ws)
    return _out(db, _call(service.update, db, exp, patch, values_loader(request)))


@router.post("/{experiment_id}/approve", response_model=ExperimentOut, responses=ERRORS)
def approve_experiment(experiment_id: int, body: ApproveRequest,
                       db: DB, ws: Workspace) -> ExperimentOut:
    exp = _call(service.get_experiment, db, experiment_id, ws)
    return _out(db, _call(service.approve, db, exp, body))


@router.post("/{experiment_id}/assign", response_model=ExperimentOut, responses=ERRORS)
def assign_experiment(experiment_id: int, body: AssignRequest, request: Request,
                      db: DB, ws: Workspace) -> ExperimentOut:
    exp = _call(service.get_experiment, db, experiment_id, ws)
    exp = _call(service.assign, db, exp, body.session_id, body.actor, values_loader(request))
    return _out(db, exp)


@router.get("/{experiment_id}/assignment.csv", responses={
    200: {"content": {"text/csv": {}}}, **ERRORS})
def export_assignment(experiment_id: int, db: DB, ws: Workspace) -> Response:
    exp = _call(service.get_experiment, db, experiment_id, ws)
    csv = _call(service.assignment_csv, db, exp)
    return Response(csv, media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="experiment_{exp.id}_assignment.csv"'})


@router.post("/{experiment_id}/results", response_model=ExperimentOut, responses=ERRORS)
def upload_results(
    experiment_id: int, db: DB, ws: Workspace,
    file: Annotated[UploadFile, File(description="Results CSV")],
    uploaded_by: Annotated[str, Form(min_length=1, max_length=100)],
    customer_value: Annotated[float | None, Form(ge=0)] = None,
    offer_cost: Annotated[float | None, Form(ge=0)] = None,
    arpu_tolerance: Annotated[float | None, Form(ge=0, le=1)] = None,
) -> ExperimentOut:
    limit = get_settings().MAX_UPLOAD_MB * 1024 * 1024
    # Sync handler (runs in the threadpool): parsing and the statistics are CPU work.
    content = file.file.read(limit + 1)
    given = {"customer_value": customer_value, "offer_cost": offer_cost}
    if arpu_tolerance is not None:
        given["arpu_tolerance"] = arpu_tolerance
    assumptions = AnalysisAssumptions(**given)
    exp = _call(service.get_experiment, db, experiment_id, ws)
    return _out(db, _call(service.upload_results, db, exp, content, uploaded_by, assumptions))


@router.post("/{experiment_id}/analysis", response_model=ExperimentOut, responses=ERRORS)
def reanalyse(experiment_id: int, body: ReanalyseRequest, db: DB, ws: Workspace) -> ExperimentOut:
    exp = _call(service.get_experiment, db, experiment_id, ws)
    return _out(db, _call(service.reanalyse, db, exp, body.assumptions, body.actor))


@router.post("/{experiment_id}/decide", response_model=ExperimentOut, responses=ERRORS)
def decide(experiment_id: int, body: DecideRequest, db: DB, ws: Workspace) -> ExperimentOut:
    exp = _call(service.get_experiment, db, experiment_id, ws)
    return _out(db, _call(service.decide, db, exp, body))


@router.post("/{experiment_id}/summary", response_model=ExperimentSummaryOut, responses=ERRORS)
def experiment_summary(experiment_id: int, request: Request, db: DB, ws: Workspace
                       ) -> ExperimentSummaryOut:
    enforce(request.app.state.ai_limiter, request, "AI")
    exp = _call(service.get_experiment, db, experiment_id, ws)
    result = _call(service.summary, db, exp)
    db.commit()
    return ExperimentSummaryOut(**result)
