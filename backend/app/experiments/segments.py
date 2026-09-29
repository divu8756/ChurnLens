"""Experiment segment definitions: a flat list of column filters, ANDed together.
Evaluated with plain pandas comparisons (no query strings, no eval)."""

from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, Field

Op = Literal["eq", "ne", "in", "not_in", "gt", "gte", "lt", "lte"]
Scalar = str | float | int | bool


class SegmentFilter(BaseModel):
    column: str = Field(min_length=1, max_length=200)
    op: Op
    value: Scalar | list[Scalar]


class SegmentDefinition(BaseModel):
    description: str = Field(default="", max_length=500)
    filters: list[SegmentFilter] = Field(default_factory=list, max_length=20)


class SegmentError(ValueError):
    """A filter refers to a missing column or has an unusable value."""


def _mask(series: pd.Series, f: SegmentFilter) -> pd.Series:
    value = f.value
    if f.op in ("in", "not_in"):
        values = value if isinstance(value, list) else [value]
        # Compare as text so "1" matches 1 regardless of the column's parsed dtype.
        hit = series.astype(str).isin([str(v) for v in values])
        return hit if f.op == "in" else ~hit & series.notna()
    if isinstance(value, list):
        raise SegmentError(f"Filter on '{f.column}' with '{f.op}' needs a single value.")
    if f.op in ("eq", "ne"):
        hit = series.astype(str) == str(value)
        return hit if f.op == "eq" else ~hit & series.notna()
    numeric = pd.to_numeric(series, errors="coerce")
    try:
        threshold = float(value)
    except (TypeError, ValueError):
        raise SegmentError(f"Filter on '{f.column}' with '{f.op}' needs a number.") from None
    if numeric.notna().sum() == 0:
        raise SegmentError(f"Column '{f.column}' is not numeric, so '{f.op}' cannot be used.")
    compare = {"gt": numeric.gt, "gte": numeric.ge, "lt": numeric.lt, "lte": numeric.le}[f.op]
    return compare(threshold).fillna(False)


def apply_segment(frame: pd.DataFrame, segment: SegmentDefinition | dict[str, Any]
                  ) -> pd.DataFrame:
    """Rows of frame that match every filter (all rows when there are no filters)."""
    segment = SegmentDefinition.model_validate(segment)
    mask = pd.Series(True, index=frame.index)
    for f in segment.filters:
        if f.column not in frame.columns:
            raise SegmentError(f"Segment column '{f.column}' is not in the data.")
        mask &= _mask(frame[f.column], f).astype(bool)
    return frame[mask]
