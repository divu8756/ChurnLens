"""GET /results/{id}: all computed results, with paginated predictions."""

import logging
from pathlib import Path
from typing import Annotated, Any, Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import ValidationError

from app import sessions
from app.api.contract import HTTPErrorOut, PredictionsPage, ResultsPayload, ResultsResponse
from app.graph.state import ErrorEntry, ProgressEntry
from app.stats.common import jsonable

router = APIRouter(tags=["results"])
logger = logging.getLogger("churnlens.results")

PAGE_SIZE = 100
RESULT_KEYS = (
    "target_column", "positive_label", "id_columns", "time_column", "confirmed_schema",
    "cleaning_log", "data_health", "eda_results", "segments", "survival_results",
    "hypothesis_results", "model_metrics", "feature_importance", "shap_summary",
    "odds_ratios", "impact_estimates", "offer_effectiveness", "insights", "recommendations",
    "final_insights", "final_recommendations", "validation_report", "final_error",
)


def _strip_paths(value: Any) -> Any:
    """Server file paths are internal; never send them to the browser."""
    if isinstance(value, dict):
        return {k: _strip_paths(v) for k, v in value.items() if not k.endswith("_path")}
    if isinstance(value, list):
        return [_strip_paths(v) for v in value]
    return value


def _dump(value: Any) -> Any:
    if isinstance(value, ErrorEntry | ProgressEntry):
        return value.model_dump()
    if isinstance(value, list):
        return [_dump(v) for v in value]
    return value


def predictions_page(path: str | None, page: int, band: str | None) -> dict[str, Any]:
    if not path or not Path(path).exists():
        return {"available": False, "page": page, "page_size": PAGE_SIZE, "total": 0,
                "pages": 0, "items": []}
    table = pd.read_parquet(path)
    if band:
        table = table[table["risk_band"] == band]
    total = len(table)
    pages = max(1, -(-total // PAGE_SIZE))
    start = (page - 1) * PAGE_SIZE
    items = table.iloc[start:start + PAGE_SIZE]
    return {"available": True, "page": page, "page_size": PAGE_SIZE, "total": total,
            "pages": pages, "band": band,
            "items": jsonable(items.to_dict(orient="records"))}


def validated_payload(payload: dict[str, Any]) -> ResultsPayload:
    """Validate against the contract; a key with an unexpected shape becomes null (with an
    error entry) instead of failing the whole response, so the other tabs still load."""
    try:
        return ResultsPayload(**payload)
    except ValidationError as exc:
        bad = sorted({str(err["loc"][0]) for err in exc.errors() if err["loc"]} - {"errors"})
        if not bad:
            raise
        logger.error("results keys failed the contract and were omitted: %s", bad)
        cleaned = {**payload, **dict.fromkeys(bad)}
        cleaned["errors"] = [*payload.get("errors", []), *(
            {"node": "results", "message": f"'{key}' had an unexpected shape and was omitted.",
             "fatal": False} for key in bad)]
        return ResultsPayload(**cleaned)


@router.get("/results/{session_id}", response_model=ResultsResponse,
            responses={409: {"model": HTTPErrorOut}, 410: {"model": HTTPErrorOut}})
def results(
    session_id: str,
    request: Request,
    page: Annotated[int, Query(ge=1)] = 1,
    band: Annotated[Literal["High", "Medium", "Low"] | None, Query()] = None,
) -> ResultsResponse:
    try:
        sessions.read_meta(session_id)
    except sessions.SessionNotFound:
        raise HTTPException(410, "Session expired, please re-upload.") from None
    manager = request.app.state.runs
    snapshot = manager.graph.get_state({"configurable": {"thread_id": session_id}})
    values = snapshot.values or {}
    if not values:
        raise HTTPException(409, "The analysis has not been started for this session.")
    run = manager.get(session_id)
    status = run.status if run else ("done" if not snapshot.next else "interrupted")

    payload = {key: _strip_paths(values.get(key)) for key in RESULT_KEYS}
    payload["errors"] = _dump(values.get("errors", []))
    return ResultsResponse(
        session_id=session_id,
        status=status,
        results=validated_payload(payload),
        predictions=PredictionsPage(**predictions_page(values.get("predictions_path"), page,
                                                       band)),
    )
