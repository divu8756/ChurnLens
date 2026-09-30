"""Next best offer per customer: GET the inputs, POST an on-demand message (T5b.4)."""

from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Request

from app import sessions
from app.agents.offer_message import cached_message
from app.api.contract import HTTPErrorOut, NextBestOffer, OfferMessageResponse
from app.ratelimit import enforce
from app.stats.common import jsonable
from app.stats.nbo import NO_OFFER

router = APIRouter(tags=["offers"])
ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": HTTPErrorOut} for code in (404, 409, 410)}


def _state(session_id: str, request: Request) -> dict[str, Any]:
    try:
        sessions.read_meta(session_id)
    except sessions.SessionNotFound:
        raise HTTPException(410, "Session expired, please re-upload.") from None
    graph = request.app.state.runs.graph
    return graph.get_state({"configurable": {"thread_id": session_id}}).values or {}


def offer_detail(values: dict[str, Any], customer_id: str) -> dict[str, Any]:
    nbo_path, pred_path = values.get("offer_recommendations_path"), values.get("predictions_path")
    if not nbo_path or not Path(nbo_path).exists() or not pred_path:
        raise HTTPException(409, "No next-best-offer analysis for this session.")
    nbo = pd.read_parquet(nbo_path)
    row = nbo[nbo["customer_id"] == customer_id]
    if row.empty:
        raise HTTPException(404, "This customer was not scored for an offer (Low risk or "
                                 "unknown ID).")
    preds = pd.read_parquet(pred_path)
    pred = preds[preds["customer_id"] == customer_id].iloc[0]
    summary = (values.get("offer_effectiveness") or {}).get("next_best_offer") or {}
    detail = jsonable(row.iloc[0].to_dict())
    detail.update({
        "risk_band": pred["risk_band"],
        "reasons": [r for r in (pred.get("reason_1"), pred.get("reason_2"), pred.get("reason_3"))
                    if isinstance(r, str) and r],
        "value_unit": summary.get("value_unit", "customers"),
        "formula": summary.get("formula", ""),
        "assumptions": summary.get("assumptions", []),
    })
    return detail


@router.get("/predictions/{session_id}/offer/{customer_id}", response_model=NextBestOffer,
            responses=ERRORS)
def next_best_offer(session_id: str, customer_id: str, request: Request) -> NextBestOffer:
    return NextBestOffer(**offer_detail(_state(session_id, request), customer_id))


@router.post("/predictions/{session_id}/offer/{customer_id}/message",
             response_model=OfferMessageResponse, responses=ERRORS)
def offer_message(session_id: str, customer_id: str, request: Request) -> OfferMessageResponse:
    enforce(request.app.state.ai_limiter, request, "AI")
    detail = offer_detail(_state(session_id, request), customer_id)
    if detail["best_offer"] == NO_OFFER:
        raise HTTPException(409, "No offer is recommended for this customer, so there is no "
                                 "message to write.")
    result, cached = cached_message(sessions.session_dir(session_id), customer_id,
                                    detail["best_offer"], detail["reasons"])
    return OfferMessageResponse(customer_id=customer_id, offer=detail["best_offer"],
                                message=result["message"], sms=result["sms"],
                                source=result["source"], cached=cached,
                                problems=result.get("problems", []))
