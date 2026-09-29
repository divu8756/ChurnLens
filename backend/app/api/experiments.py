"""A/B experiments: design, approval gate, assignment and export (T5c.2)."""

from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy import select
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
    ExperimentCreate,
    ExperimentOut,
    ExperimentSummary,
    ExperimentUpdate,
    ReanalyseRequest,
)

router = APIRouter(prefix="/experiments", tags=["experiments"])
ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": HTTPErrorOut} for code in (404, 409, 410, 413)}


def get_db() -> Iterator[Session]:
    with session_scope() as db:
        yield db


DB = Annotated[Session, Depends(get_db)]


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
def create_experiment(payload: ExperimentCreate, request: Request,
                      db: DB) -> ExperimentOut:
    exp = _call(service.create, db, payload, values_loader(request))
    return _out(db, exp)


@router.get("", response_model=list[ExperimentSummary])
def list_experiments(db: DB) -> list[ExperimentSummary]:
    rows = db.scalars(select(Experiment).order_by(Experiment.id.desc()))
    return [ExperimentSummary.model_validate(e) for e in rows]


@router.get("/{experiment_id}", response_model=ExperimentOut, responses=ERRORS)
def get_experiment(experiment_id: int, db: DB) -> ExperimentOut:
    return _out(db, _call(service.get_experiment, db, experiment_id))


@router.patch("/{experiment_id}", response_model=ExperimentOut, responses=ERRORS)
def update_experiment(experiment_id: int, patch: ExperimentUpdate, request: Request,
                      db: DB) -> ExperimentOut:
    exp = _call(service.get_experiment, db, experiment_id)
    return _out(db, _call(service.update, db, exp, patch, values_loader(request)))


@router.post("/{experiment_id}/approve", response_model=ExperimentOut, responses=ERRORS)
def approve_experiment(experiment_id: int, body: ApproveRequest,
                       db: DB) -> ExperimentOut:
    exp = _call(service.get_experiment, db, experiment_id)
    return _out(db, _call(service.approve, db, exp, body))


@router.post("/{experiment_id}/assign", response_model=ExperimentOut, responses=ERRORS)
def assign_experiment(experiment_id: int, body: AssignRequest, request: Request,
                      db: DB) -> ExperimentOut:
    exp = _call(service.get_experiment, db, experiment_id)
    exp = _call(service.assign, db, exp, body.session_id, body.actor, values_loader(request))
    return _out(db, exp)


@router.get("/{experiment_id}/assignment.csv", responses={
    200: {"content": {"text/csv": {}}}, **ERRORS})
def export_assignment(experiment_id: int, db: DB) -> Response:
    exp = _call(service.get_experiment, db, experiment_id)
    csv = _call(service.assignment_csv, db, exp)
    return Response(csv, media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="experiment_{exp.id}_assignment.csv"'})


@router.post("/{experiment_id}/results", response_model=ExperimentOut, responses=ERRORS)
async def upload_results(
    experiment_id: int, db: DB,
    file: Annotated[UploadFile, File(description="Results CSV")],
    uploaded_by: Annotated[str, Form(min_length=1, max_length=100)],
    customer_value: Annotated[float | None, Form(ge=0)] = None,
    offer_cost: Annotated[float | None, Form(ge=0)] = None,
    arpu_tolerance: Annotated[float | None, Form(ge=0, le=1)] = None,
) -> ExperimentOut:
    limit = get_settings().MAX_UPLOAD_MB * 1024 * 1024
    content = await file.read(limit + 1)
    given = {"customer_value": customer_value, "offer_cost": offer_cost}
    if arpu_tolerance is not None:
        given["arpu_tolerance"] = arpu_tolerance
    assumptions = AnalysisAssumptions(**given)
    exp = _call(service.get_experiment, db, experiment_id)
    return _out(db, _call(service.upload_results, db, exp, content, uploaded_by, assumptions))


@router.post("/{experiment_id}/analysis", response_model=ExperimentOut, responses=ERRORS)
def reanalyse(experiment_id: int, body: ReanalyseRequest, db: DB) -> ExperimentOut:
    exp = _call(service.get_experiment, db, experiment_id)
    return _out(db, _call(service.reanalyse, db, exp, body.assumptions, body.actor))
