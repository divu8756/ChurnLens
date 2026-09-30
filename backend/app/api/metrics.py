"""Model and business metrics (Phase 5d). Recomputed in Python on request; the browser
only displays them (CLAUDE.md rule 21)."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app import sessions
from app.agents.business_explanation import assumptions_hash, cached_explanation
from app.agents.offer import offer_evidence
from app.api.contract import HTTPErrorOut
from app.api.metrics_contract import BusinessExplanation, BusinessMetrics, ModelMetricsV2
from app.business import BusinessAssumptions, compute
from app.catalog import CatalogueError

router = APIRouter(prefix="/metrics", tags=["metrics"])
ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": HTTPErrorOut} for code in (409, 410, 500)}


def _values(session_id: str, request: Request) -> dict[str, Any]:
    try:
        sessions.read_meta(session_id)
    except sessions.SessionNotFound:
        raise HTTPException(410, "Session expired, please re-upload.") from None
    graph = request.app.state.runs.graph
    values = graph.get_state({"configurable": {"thread_id": session_id}}).values or {}
    if not values.get("predictions_path"):
        raise HTTPException(409, "The analysis has not produced risk scores yet.")
    return values


def _business(session_id: str, request: Request, assumptions: BusinessAssumptions
              ) -> dict[str, Any]:
    values = _values(session_id, request)
    try:
        result = compute(values, offer_evidence(session_id), assumptions)
    except CatalogueError as exc:
        raise HTTPException(500, f"The offer catalogue is invalid: {exc}") from None
    result["defaults_only"] = not assumptions.model_dump(exclude_none=True, exclude={"offers"}) \
        and not assumptions.offers
    return result


@router.get("/model/{session_id}", response_model=ModelMetricsV2, responses=ERRORS)
def model_metrics(session_id: str, request: Request) -> ModelMetricsV2:
    values = _values(session_id, request)
    v2 = values.get("model_metrics_v2")
    if not v2:
        raise HTTPException(409, "Model metrics are not available for this run "
                                 "(calibration failed or the model did not train).")
    name = (values.get("model_metrics") or {}).get("chosen_model_name")
    return ModelMetricsV2(**v2, chosen_model_name=name)


@router.get("/business/{session_id}", response_model=BusinessMetrics, responses=ERRORS)
def business_metrics(session_id: str, request: Request) -> BusinessMetrics:
    return BusinessMetrics(**_business(session_id, request, BusinessAssumptions()))


@router.post("/business/{session_id}", response_model=BusinessMetrics, responses=ERRORS)
def recompute_business_metrics(session_id: str, body: BusinessAssumptions,
                               request: Request) -> BusinessMetrics:
    """Recompute with edited assumptions (no LLM)."""
    return BusinessMetrics(**_business(session_id, request, body))


@router.post("/business/{session_id}/explain", response_model=BusinessExplanation,
             responses=ERRORS)
def explain_business_metrics(session_id: str, body: BusinessAssumptions,
                             request: Request) -> BusinessExplanation:
    """A validated plain-English explanation of the numbers for these assumptions."""
    metrics = _business(session_id, request, body)
    if not metrics.get("enabled"):
        raise HTTPException(409, metrics.get("reason") or "Business metrics are disabled.")
    key = assumptions_hash(body.model_dump(exclude_none=True))
    result, cached = cached_explanation(sessions.session_dir(session_id), key, metrics)
    return BusinessExplanation(**result, assumptions_hash=key, cached=cached)
