"""POST /upload, POST /upload/{id}/sheet and POST /sample."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app import sessions
from app.api.contract import HTTPErrorOut
from app.config import BACKEND_DIR, get_settings
from app.experiments.workspace import optional_workspace
from app.ingest import (
    ParsedUpload,
    UploadRejected,
    check_size,
    extension_of,
    list_sheets,
    parse_upload,
)

router = APIRouter(tags=["upload"])

SAMPLE_FILE = BACKEND_DIR / "sample_data" / "telco_churn.csv"
PENDING_XLSX = "upload.xlsx"
ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": HTTPErrorOut} for code in (400, 409, 410, 413, 415, 422, 503)
}


class UploadResponse(BaseModel):
    session_id: str
    status: Literal["ready", "choose_sheet"]
    filename: str
    sheets: list[str] = []
    sheet_name: str | None = None
    rows: int | None = None
    columns: list[str] = []
    warnings: list[str] = []


def _reject(exc: UploadRejected) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


async def _read_limited(file: UploadFile, max_mb: int) -> bytes:
    limit = max_mb * 1024 * 1024
    data = await file.read(limit + 1)
    check_size(len(data), max_mb)
    return data


def _finish(session_id: str, path: Path, filename: str, parsed: ParsedUpload,
            sample: bool = False, workspace: str | None = None) -> UploadResponse:
    sessions.save_raw(path, parsed.frame)
    columns = [str(c) for c in parsed.frame.columns]
    sessions.write_meta(path, {
        "session_id": session_id,
        "status": "ready",
        "filename": filename,
        "sheet_name": parsed.sheet_name,
        "encoding": parsed.encoding,
        "rows": len(parsed.frame),
        "columns": columns,
        "warnings": parsed.warnings,
        "created_at": datetime.now(UTC).isoformat(),
        # The built-in sample (unlocks the demo experiment); never set for uploads.
        "sample": sample,
        # Scopes experiment evidence for this session's next best offer (hash, not key).
        "workspace_hash": workspace,
    })
    (path / PENDING_XLSX).unlink(missing_ok=True)
    return UploadResponse(
        session_id=session_id, status="ready", filename=filename,
        sheet_name=parsed.sheet_name, rows=len(parsed.frame), columns=columns,
        warnings=parsed.warnings,
    )


@router.post("/upload", response_model=UploadResponse, responses=ERRORS)
async def upload(
    file: Annotated[UploadFile, File()],
    workspace: Annotated[str | None, Depends(optional_workspace)],
    sheet_name: Annotated[str | None, Form()] = None,
) -> UploadResponse:
    settings = get_settings()
    filename = Path(file.filename or "upload").name
    try:
        ext = extension_of(filename)
        data = await _read_limited(file, settings.MAX_UPLOAD_MB)
        if ext == ".xlsx" and sheet_name is None:
            sheets = list_sheets(data)
            if len(sheets) > 1:
                session_id, path = sessions.create_session()
                (path / PENDING_XLSX).write_bytes(data)
                sessions.write_meta(path, {
                    "session_id": session_id, "status": "choose_sheet",
                    "filename": filename, "sheets": sheets, "workspace_hash": workspace,
                    "created_at": datetime.now(UTC).isoformat(),
                })
                return UploadResponse(session_id=session_id, status="choose_sheet",
                                      filename=filename, sheets=sheets)
        parsed = parse_upload(data, filename, sheet_name=sheet_name,
                              min_rows=settings.MIN_ROWS, max_rows=settings.MAX_ROWS)
    except UploadRejected as exc:
        raise _reject(exc) from None
    session_id, path = sessions.create_session()
    return _finish(session_id, path, filename, parsed, workspace=workspace)


@router.post("/upload/{session_id}/sheet", response_model=UploadResponse, responses=ERRORS)
def choose_sheet(session_id: str, sheet_name: Annotated[str, Form()]) -> UploadResponse:
    settings = get_settings()
    try:
        meta = sessions.read_meta(session_id)
    except sessions.SessionNotFound:
        raise HTTPException(410, "Session expired, please re-upload.") from None
    path = sessions.session_dir(session_id)
    pending = path / PENDING_XLSX
    if meta.get("status") != "choose_sheet" or not pending.exists():
        raise HTTPException(409, "This upload is not waiting for a sheet choice.")
    try:
        parsed = parse_upload(pending.read_bytes(), meta["filename"], sheet_name=sheet_name,
                              min_rows=settings.MIN_ROWS, max_rows=settings.MAX_ROWS)
    except UploadRejected as exc:
        raise _reject(exc) from None
    return _finish(session_id, path, meta["filename"], parsed,
                   workspace=meta.get("workspace_hash"))


@router.post("/sample", response_model=UploadResponse, responses=ERRORS)
def load_sample(
    workspace: Annotated[str | None, Depends(optional_workspace)],
) -> UploadResponse:
    settings = get_settings()
    if not SAMPLE_FILE.exists():
        raise HTTPException(503, "The sample dataset is not available on this server.")
    try:
        parsed = parse_upload(SAMPLE_FILE.read_bytes(), SAMPLE_FILE.name, sheet_name=None,
                              min_rows=settings.MIN_ROWS, max_rows=settings.MAX_ROWS)
    except UploadRejected as exc:
        raise _reject(exc) from None
    session_id, path = sessions.create_session()
    return _finish(session_id, path, SAMPLE_FILE.name, parsed, sample=True,
                   workspace=workspace)
