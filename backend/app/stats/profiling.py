"""Column profiles and deterministic schema heuristics (no LLM)."""

import re
from typing import Any

import pandas as pd

SAMPLE_VALUES = 5
MAX_SAMPLE_CHARS = 60
ID_UNIQUE_RATIO = 0.95
TARGET_NAME = re.compile(r"churn|exited|attrition|\bleft\b|cancel", re.I)
REVENUE_NAME = re.compile(r"monthly_?charges?|arpu|monthly_?(revenue|fee|bill|spend)|"
                          r"mrr|monthly_?amount", re.I)
TIME_NAME = re.compile(r"tenure|months?_?(as|with)?_?customer|lifetime|duration", re.I)
ID_NAME = re.compile(r"(^|_|\b)(id|uuid|guid|key|row_?number|index)$", re.I)
POSITIVE_WORDS = ("yes", "true", "1", "churned", "churn", "exited", "left", "cancelled", "y")


def _numeric_share(series: pd.Series) -> float:
    values = series.dropna().astype(str).str.strip()
    values = values[values != ""]
    if values.empty:
        return 0.0
    return float(pd.to_numeric(values, errors="coerce").notna().mean())


def profile_columns(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """What the LLM may see: name, dtype, <= 5 sample values, null %, unique count."""
    profile = []
    for col in frame.columns:
        series = frame[col]
        samples = []
        for value in series.dropna().unique():
            text = str(value).strip()
            if text:
                samples.append(text[:MAX_SAMPLE_CHARS])
            if len(samples) == SAMPLE_VALUES:
                break
        profile.append({
            "name": str(col),
            "dtype": str(series.dtype),
            "samples": samples,
            "null_pct": round(float(series.isna().mean() * 100), 2),
            "unique_count": int(series.nunique(dropna=True)),
        })
    return profile


def likely_ids(frame: pd.DataFrame) -> list[str]:
    """Columns that identify rows: mostly unique codes, not measurements."""
    ids = []
    n = max(len(frame), 1)
    for col in frame.columns:
        series = frame[col].dropna()
        if series.empty:
            continue
        ratio = series.nunique() / n
        kind = series.dtype.kind
        if kind == "f":
            continue  # continuous measurements are unique but are not ids
        if kind in "iu":
            consecutive = series.is_monotonic_increasing and ratio > ID_UNIQUE_RATIO
            if consecutive or (ID_NAME.search(str(col)) and ratio > ID_UNIQUE_RATIO):
                ids.append(str(col))
            continue
        if ratio > ID_UNIQUE_RATIO and _numeric_share(series) < 0.9:
            ids.append(str(col))
    return ids


def binary_values(series: pd.Series) -> list[str] | None:
    values = series.dropna().astype(str).str.strip()
    values = values[values != ""].unique()
    return sorted(values) if len(values) == 2 else None


def guess_positive_label(values: list[str], series: pd.Series) -> str:
    lowered = {v.lower(): v for v in values}
    for word in POSITIVE_WORDS:
        if word in lowered:
            return lowered[word]
    counts = series.dropna().astype(str).str.strip().value_counts()
    return str(counts.index[-1])  # the minority class


def likely_targets(frame: pd.DataFrame) -> list[str]:
    """Binary columns whose name suggests churn, best first."""
    named = [str(c) for c in frame.columns
             if TARGET_NAME.search(str(c)) and binary_values(frame[c]) is not None]
    return sorted(named, key=lambda c: (c.lower() not in ("churn", "exited"), len(c)))


def likely_time_column(frame: pd.DataFrame) -> str | None:
    for col in frame.columns:
        if TIME_NAME.search(str(col)) and _numeric_share(frame[col]) > 0.95:
            return str(col)
    return None


def likely_revenue_column(frame: pd.DataFrame) -> str | None:
    """A numeric column that looks like monthly revenue per customer (ARPU)."""
    for col in frame.columns:
        if REVENUE_NAME.search(str(col)) and _numeric_share(frame[col]) > 0.95:
            return str(col)
    return None


def heuristic_type(series: pd.Series, is_id: bool) -> str:
    if is_id:
        return "id"
    if binary_values(series) is not None:
        return "binary"
    kind = series.dtype.kind
    if kind in "iuf":
        return "numeric"
    if kind == "M":
        return "datetime"
    if _numeric_share(series) > 0.95:
        return "numeric"
    non_null = series.dropna()
    if not non_null.empty and kind == "O":
        parsed = pd.to_datetime(non_null.astype(str).head(200), errors="coerce", format="mixed")
        if parsed.notna().mean() > 0.95:
            return "datetime"
        if non_null.nunique() <= max(20, int(0.05 * len(non_null))):
            return "categorical"
    return "text"


def heuristic_schema(frame: pd.DataFrame) -> dict[str, Any]:
    """A complete proposal from rules alone; used as fallback and for merging."""
    ids = likely_ids(frame)
    targets = likely_targets(frame)
    target = targets[0] if targets else None
    positive = None
    if target:
        values = binary_values(frame[target]) or []
        positive = guess_positive_label(values, frame[target])
    columns = [
        {"name": str(c), "semantic_type": heuristic_type(frame[c], str(c) in ids),
         "confidence": 0.6}
        for c in frame.columns
    ]
    return {
        "columns": columns,
        "target_column": target,
        "positive_label": positive,
        "id_columns": ids,
        "time_column": likely_time_column(frame),
        "revenue_column": likely_revenue_column(frame),
        "reasoning": "Proposed by rules (column names, distinct values and types).",
    }
