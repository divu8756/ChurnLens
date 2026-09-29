"""Helpers shared by the stats modules."""

import math
from typing import Any

import numpy as np
import pandas as pd

from app.schema_validation import offer_column_names
from app.stats.cleaning import column_types


def jsonable(value: Any) -> Any:
    """Convert numpy/pandas values to plain JSON types; NaN and inf become None."""
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return [jsonable(v) for v in value.tolist()]
    if isinstance(value, np.bool_ | bool):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating | float):
        f = float(value)
        return None if math.isnan(f) or math.isinf(f) else f
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def feature_columns(frame: pd.DataFrame, schema: dict[str, Any]) -> dict[str, list[str]]:
    """Analysis columns by kind, excluding ids, the target, free text and offer/campaign
    columns (treatments, analysed separately in stats/offers.py)."""
    target = schema["target_column"]
    ids = set(schema.get("id_columns", [])) | set(offer_column_names(schema.get("offer_columns")))
    types = column_types(frame, schema)
    groups: dict[str, list[str]] = {"numeric": [], "categorical": [], "datetime": []}
    for col, kind in types.items():
        if col == target or col in ids or kind == "id":
            continue
        if kind == "numeric":
            groups["numeric"].append(col)
        elif kind in ("categorical", "binary"):
            groups["categorical"].append(col)
        elif kind == "datetime":
            groups["datetime"].append(col)
    return groups
