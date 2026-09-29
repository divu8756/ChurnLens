"""Build a full analysed state for the Telco sample by running the real nodes in order."""

from functools import lru_cache
from pathlib import Path
from tempfile import mkdtemp
from typing import Any

import pandas as pd

from app.agents.analysis import eda_node, hypothesis_node, segmentation_node, survival_node
from app.agents.cleaning import cleaning_node
from app.agents.impact import impact_node
from app.agents.modelling import modelling_node
from app.config import BACKEND_DIR
from app.graph.state import ChurnState
from app.stats import profiling

TELCO = BACKEND_DIR / "sample_data" / "telco_churn.csv"


def _merge(state: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(state)
    for key, value in update.items():
        if key in ("errors", "progress", "telemetry_events"):
            merged[key] = list(merged.get(key, [])) + list(value)
        else:
            merged[key] = value
    return merged


@lru_cache
def telco_state() -> dict[str, Any]:
    """State after impact_node, as plain JSON-like dicts (paths point to a temp dir)."""
    raw = pd.read_csv(TELCO)
    folder = Path(mkdtemp(prefix="churnlens-telco-"))
    raw_path = folder / "raw.parquet"
    raw.to_parquet(raw_path, index=False)
    heur = profiling.heuristic_schema(raw)
    schema = {**heur, "columns": [{"name": c["name"], "semantic_type": c["semantic_type"]}
                                  for c in heur["columns"]]}
    state: dict[str, Any] = {"session_id": "telco", "raw_path": str(raw_path),
                             "confirmed_schema": schema, "target_column": schema["target_column"],
                             "positive_label": schema["positive_label"],
                             "time_column": schema["time_column"],
                             "id_columns": schema["id_columns"], "target_confirmed": True}
    for node in (cleaning_node, eda_node, segmentation_node, survival_node, hypothesis_node,
                 modelling_node, impact_node):
        state = _merge(state, node(ChurnState(**state)))
    return state
