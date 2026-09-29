"""GET /predictions/{id} (paged, filtered) and GET /predictions/{id}/csv (the same filter)."""

import csv
import io
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Any, Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app import sessions
from app.api.contract import HTTPErrorOut, PredictionsResponse
from app.stats.common import jsonable

router = APIRouter(tags=["predictions"])

PAGE_SIZE = 50
MAX_QUERY = 100
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")

Band = Annotated[Literal["High", "Medium", "Low"] | None, Query()]
Search = Annotated[str | None, Query(max_length=MAX_QUERY,
                                     description="Case-insensitive part of a customer ID")]


def _predictions_path(session_id: str, request: Request) -> Path:
    try:
        sessions.read_meta(session_id)
    except sessions.SessionNotFound:
        raise HTTPException(410, "Session expired, please re-upload.") from None
    graph = request.app.state.runs.graph
    values = graph.get_state({"configurable": {"thread_id": session_id}}).values or {}
    path = values.get("predictions_path")
    if not path or not Path(path).exists():
        raise HTTPException(409, "Risk predictions are not available for this session yet.")
    return Path(path)


def filtered(path: Path, band: str | None, q: str | None) -> pd.DataFrame:
    """Rows stay in the stored order (highest churn probability first)."""
    table = pd.read_parquet(path)
    if band:
        table = table[table["risk_band"] == band]
    if q and q.strip():
        ids = table["customer_id"].astype(str)
        table = table[ids.str.contains(q.strip(), case=False, regex=False)]
    return table


def csv_safe(value: Any) -> Any:
    """Stop spreadsheets running uploaded text as a formula (CSV injection)."""
    if isinstance(value, str) and value.startswith(FORMULA_START):
        return "'" + value
    return value


@router.get("/predictions/{session_id}", response_model=PredictionsResponse,
            responses={409: {"model": HTTPErrorOut}, 410: {"model": HTTPErrorOut}})
def predictions(
    session_id: str,
    request: Request,
    page: Annotated[int, Query(ge=1)] = 1,
    band: Band = None,
    q: Search = None,
) -> PredictionsResponse:
    table = filtered(_predictions_path(session_id, request), band, q)
    total = len(table)
    pages = max(1, -(-total // PAGE_SIZE))
    start = (page - 1) * PAGE_SIZE
    items = jsonable(table.iloc[start:start + PAGE_SIZE].to_dict(orient="records"))
    return PredictionsResponse(page=page, page_size=PAGE_SIZE, total=total, pages=pages,
                               band=band, q=q.strip() if q else None, items=items)


@router.get("/predictions/{session_id}/csv", response_class=StreamingResponse,
            responses={200: {"content": {"text/csv": {}}, "description": "Filtered predictions"},
                       409: {"model": HTTPErrorOut}, 410: {"model": HTTPErrorOut}})
def predictions_csv(session_id: str, request: Request, band: Band = None,
                    q: Search = None) -> StreamingResponse:
    table = filtered(_predictions_path(session_id, request), band, q)

    def rows() -> Iterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(table.columns)
        for record in table.itertuples(index=False):
            writer.writerow([csv_safe(v) if not pd.isna(v) else "" for v in record])
            if buffer.tell() > 64_000:
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate()
        yield buffer.getvalue()

    name = "churn_predictions" + (f"_{band.lower()}" if band else "") + ".csv"
    return StreamingResponse(rows(), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})
