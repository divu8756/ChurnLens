"""impact_node: Python-only impact estimates (app/stats/impact.py)."""

from pathlib import Path
from typing import Any

import pandas as pd

from app.graph.errors import FatalNodeError
from app.graph.state import ChurnState, ProgressEntry
from app.stats.impact import run_impact


def impact_node(state: ChurnState) -> dict[str, Any]:
    if not state.clean_path or not state.confirmed_schema:
        raise FatalNodeError("Impact estimates need cleaned data and a confirmed schema.")
    frame = pd.read_parquet(state.clean_path)
    labels = None
    assignments = (state.segments or {}).get("assignments_path")
    if assignments and Path(assignments).exists():
        labels = pd.read_parquet(assignments)["segment"].to_numpy()
    result = run_impact(frame, state.confirmed_schema, state.segments, labels,
                        state.hypothesis_results)
    return {"impact_estimates": result,
            "progress": [ProgressEntry(node="impact", status="done",
                                       detail=f"{len(result['items'])} groups estimated")]}
