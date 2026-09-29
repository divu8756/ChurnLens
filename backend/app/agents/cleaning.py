"""cleaning_node: thin wrapper around app/stats/cleaning.py."""

from pathlib import Path
from typing import Any

import pandas as pd

from app.config import get_settings
from app.graph.errors import FatalNodeError
from app.graph.state import ChurnState, ProgressEntry
from app.stats.cleaning import CleaningFatal, clean

CLEAN_FILE = "clean.parquet"


def cleaning_node(state: ChurnState) -> dict[str, Any]:
    if not state.raw_path or not state.confirmed_schema:
        raise FatalNodeError("Cleaning needs the uploaded data and a confirmed schema.")
    frame = pd.read_parquet(state.raw_path)
    try:
        result = clean(frame, state.confirmed_schema, get_settings().MIN_ROWS)
    except CleaningFatal as exc:
        raise FatalNodeError(str(exc)) from None

    clean_path = Path(state.raw_path).with_name(CLEAN_FILE)
    result.frame.to_parquet(clean_path, index=False)
    health = result.health
    return {
        "clean_path": str(clean_path),
        "cleaning_log": result.log,
        "data_health": health,
        "progress": [ProgressEntry(
            node="cleaning", status="done",
            detail=f"{health['rows_after']:,} rows, health score {health['health_score']}",
        )],
    }
