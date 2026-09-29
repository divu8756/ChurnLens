"""ingest_node: confirm the uploaded data is in place and record its shape.

Parsing and validation happen at upload time (app/ingest.py) so the user gets
an immediate 4xx; this node re-checks the saved file before analysis starts.
"""

from typing import Any

import pyarrow.parquet as pq

from app import sessions
from app.config import get_settings
from app.graph.errors import FatalNodeError
from app.graph.state import ChurnState, ProgressEntry


def ingest_node(state: ChurnState) -> dict[str, Any]:
    try:
        meta = sessions.read_meta(state.session_id)
    except sessions.SessionNotFound:
        raise FatalNodeError("Session expired, please re-upload.") from None
    if meta.get("status") != "ready":
        raise FatalNodeError("Choose a sheet before starting the analysis.")
    raw_path = sessions.session_dir(state.session_id) / sessions.RAW_FILE
    if not raw_path.exists():
        raise FatalNodeError("The uploaded data is missing, please re-upload.")

    parquet = pq.ParquetFile(raw_path).metadata
    rows, cols = parquet.num_rows, parquet.num_columns
    settings = get_settings()
    if rows < settings.MIN_ROWS:
        raise FatalNodeError(f"The data has {rows} rows; at least {settings.MIN_ROWS} are needed.")
    if rows > settings.MAX_ROWS:
        raise FatalNodeError(f"The data has {rows} rows; the limit is {settings.MAX_ROWS}.")

    return {
        "raw_path": str(raw_path),
        "sheet_name": meta.get("sheet_name"),
        "progress": [ProgressEntry(node="ingest", status="done",
                                   detail=f"{rows:,} rows, {cols} columns")],
    }
