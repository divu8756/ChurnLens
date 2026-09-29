"""Thin graph nodes for the parallel analysis step (EDA, segmentation, survival,
hypothesis tests). Each reads the cleaned data and writes only its own key."""

from pathlib import Path
from typing import Any

import pandas as pd

from app.graph.errors import FatalNodeError
from app.graph.state import ChurnState, ProgressEntry
from app.stats.eda import run_eda
from app.stats.segmentation import run_segmentation

SEGMENTS_FILE = "segments.parquet"


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


def segmentation_node(state: ChurnState) -> dict[str, Any]:
    frame, schema = _load(state)
    result, labels = run_segmentation(frame, schema)
    if labels is None:
        return {"segments": result,
                "progress": [ProgressEntry(node="segmentation", status="skipped",
                                           detail=result["reason"])]}
    path = Path(state.clean_path or "").with_name(SEGMENTS_FILE)
    pd.DataFrame({"segment": labels}).to_parquet(path, index=False)
    result["assignments_path"] = str(path)
    return {"segments": result,
            "progress": [ProgressEntry(node="segmentation", status="done",
                                       detail=f"{result['k']} segments")]}
