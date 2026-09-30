"""GET /export/{id}/excel and /pdf: built on first request, cached in the session folder
per analysis checkpoint (a re-run produces fresh files)."""

import re
import threading
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app import sessions
from app.api.contract import HTTPErrorOut
from app.exports.excel import write_excel
from app.exports.pdf import write_pdf

router = APIRouter(prefix="/export", tags=["exports"])
ERRORS: dict[int | str, dict[str, Any]] = {code: {"model": HTTPErrorOut} for code in (409, 410)}
KINDS = {
    "excel": (write_excel, "xlsx",
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "pdf": (write_pdf, "pdf", "application/pdf"),
}
_lock = threading.Lock()


def _finished(session_id: str, request: Request) -> tuple[dict[str, Any], str]:
    try:
        sessions.read_meta(session_id)
    except sessions.SessionNotFound:
        raise HTTPException(410, "Session expired, please re-upload.") from None
    graph = request.app.state.runs.graph
    snapshot = graph.get_state({"configurable": {"thread_id": session_id}})
    values = snapshot.values or {}
    if snapshot.next or not values.get("predictions_path") or values.get("final_error"):
        raise HTTPException(409, "Exports are available once the analysis has finished.")
    checkpoint = (snapshot.config or {}).get("configurable", {}).get("checkpoint_id") or "run"
    return values, re.sub(r"[^A-Za-z0-9_-]", "", str(checkpoint))[:64] or "run"


def _export(kind: str, session_id: str, request: Request) -> FileResponse:
    values, checkpoint = _finished(session_id, request)
    writer, ext, media = KINDS[kind]
    folder = sessions.session_dir(session_id)
    path = folder / f"export_{checkpoint}.{ext}"
    with _lock:  # one build per file, even with double clicks
        if not path.exists():
            tmp = path.with_suffix(f".tmp.{ext}")
            writer(values, tmp)
            tmp.replace(path)
    return FileResponse(path, media_type=media, filename=f"churnlens_report.{ext}")


@router.get("/{session_id}/excel", response_class=FileResponse, responses={
    200: {"content": {KINDS["excel"][2]: {}}}, **ERRORS})
def export_excel(session_id: str, request: Request) -> FileResponse:
    return _export("excel", session_id, request)


@router.get("/{session_id}/pdf", response_class=FileResponse, responses={
    200: {"content": {"application/pdf": {}}}, **ERRORS})
def export_pdf(session_id: str, request: Request) -> FileResponse:
    return _export("pdf", session_id, request)
