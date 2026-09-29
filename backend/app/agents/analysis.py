"""Thin graph nodes for the parallel analysis step (EDA, segmentation, survival,
hypothesis tests). Each reads the cleaned data and writes only its own key."""

from typing import Any

import pandas as pd

from app.graph.errors import FatalNodeError
from app.graph.state import ChurnState, ProgressEntry
from app.stats.eda import run_eda


def _load(state: ChurnState) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not state.clean_path or not state.confirmed_schema:
        raise FatalNodeError("Analysis needs cleaned data and a confirmed schema.")
    return pd.read_parquet(state.clean_path), state.confirmed_schema


def eda_node(state: ChurnState) -> dict[str, Any]:
    frame, schema = _load(state)
    result = run_eda(frame, schema)
    detail = (f"{len(result['numeric'])} numeric, {len(result['categorical'])} categorical "
              "columns")
    return {"eda_results": result,
            "progress": [ProgressEntry(node="eda", status="done", detail=detail)]}
