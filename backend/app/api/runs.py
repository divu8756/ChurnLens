"""POST /analyze/{id}, POST /confirm-schema/{id} and GET /stream/{id} (SSE)."""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app import sessions
from app.runs import Event, RunConflict, RunManager
from app.schema_validation import ConfirmedSchema, validate_schema

router = APIRouter(tags=["runs"])

HEARTBEAT_S = 15.0
POLL_S = 0.2
EXPIRED = "Session expired, please re-upload."


class RunStatusResponse(BaseModel):
    session_id: str
    status: str


def _manager(request: Request) -> RunManager:
    return request.app.state.runs


def _require_session(session_id: str) -> None:
    try:
        meta = sessions.read_meta(session_id)
    except sessions.SessionNotFound:
        raise HTTPException(410, EXPIRED) from None
    if meta.get("status") != "ready":
        raise HTTPException(409, "Choose a sheet before starting the analysis.")


@router.post("/analyze/{session_id}", response_model=RunStatusResponse)
def analyze(session_id: str, request: Request) -> RunStatusResponse:
    _require_session(session_id)
    run = _manager(request).start(session_id)
    return RunStatusResponse(session_id=session_id, status=run.status)


@router.post("/confirm-schema/{session_id}", response_model=RunStatusResponse)
def confirm_schema(session_id: str, schema: ConfirmedSchema,
                   request: Request) -> RunStatusResponse:
    _require_session(session_id)
    manager = _manager(request)
    run = manager.get(session_id)
    if run is None:
        raise HTTPException(410, EXPIRED)
    if run.status != "awaiting_confirmation":
        raise HTTPException(409, f"The analysis is {run.status}, not waiting for confirmation.")

    raw = sessions.session_dir(session_id) / sessions.RAW_FILE
    problems = validate_schema(schema, pd.read_parquet(raw))
    if problems:
        raise HTTPException(422, {"message": "The schema needs changes.", "problems": problems})
    try:
        run = manager.resume(session_id, schema.model_dump())
    except RunConflict as exc:
        raise HTTPException(409, str(exc)) from None
    return RunStatusResponse(session_id=session_id, status=run.status)


def _format(event: Event) -> str:
    return f"id: {event.id}\nevent: {event.event}\ndata: {json.dumps(event.data, default=str)}\n\n"


@router.get("/stream/{session_id}")
async def stream(
    session_id: str,
    request: Request,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    try:
        sessions.read_meta(session_id)
    except sessions.SessionNotFound:
        raise HTTPException(410, EXPIRED) from None
    run = _manager(request).get(session_id)
    if run is None:
        # Unknown run: never started, or the server restarted and lost it.
        raise HTTPException(410, EXPIRED)
    start_after = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0

    async def events() -> AsyncIterator[str]:
        last_id, last_sent = start_after, time.monotonic()
        while True:
            for event in run.events_after(last_id):
                last_id = event.id
                last_sent = time.monotonic()
                yield _format(event)
                if event.event == "done":
                    return
            if await request.is_disconnected():
                return
            if time.monotonic() - last_sent >= HEARTBEAT_S:
                last_sent = time.monotonic()
                yield "event: heartbeat\ndata: {}\n\n"
            await asyncio.sleep(POLL_S)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
