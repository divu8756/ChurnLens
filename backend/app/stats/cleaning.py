"""Data cleaning and data health as pure functions (docs/SPEC.md node 4).

Every action is logged as {step, column, rows_affected, detail}.

Decisions:
- Numeric blanks are NOT imputed here. The model pipeline imputes medians on
  the training split only (no test-set leakage), and some blanks carry
  meaning (for example NPS never answered).
- Categorical blanks become "Unknown" (a constant, so no leakage).
- Outliers are flagged (IQR 1.5x and |z| > 3) and counted, never deleted or capped.
"""

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from app.stats import profiling

UNKNOWN = "Unknown"
IQR_K = 1.5
Z_LIMIT = 3.0
INVALID_NEGATIVE_MAX_SHARE = 0.005
SIGNED_NAME = re.compile(r"change|chg|delta|diff|pct|percent|growth|balance|trend|gap|score|"
                         r"sentiment|net", re.I)
HEALTH_FORMULA = (
    "health = 100 - 40*m - 20*d - 20*o - 20*b, where m = mean share of missing cells "
    "per column, d = min(1, 10 * duplicate rows / rows before), o = min(1, 5 * mean "
    "share of IQR-outlier rows per numeric column), b = min(1, max(0, 0.5 - minority "
    "class share) / 0.45); rounded and clipped to 0-100."
)


class CleaningFatal(ValueError):
    """The data cannot be analysed (shown to the user)."""


@dataclass
class CleaningResult:
    frame: pd.DataFrame
    log: list[dict[str, Any]] = field(default_factory=list)
    health: dict[str, Any] = field(default_factory=dict)


def _log(log: list, step: str, column: str | None, rows: int, detail: str) -> None:
    if rows:
        log.append({"step": step, "column": column, "rows_affected": int(rows), "detail": detail})


def column_types(frame: pd.DataFrame, schema: dict[str, Any]) -> dict[str, str]:
    """Confirmed semantic types, falling back to heuristics for unlisted columns."""
    confirmed = {c["name"]: c["semantic_type"] for c in schema.get("columns", [])}
    ids = set(schema.get("id_columns", []))
    return {str(col): ("id" if col in ids else confirmed.get(col)
                       or profiling.heuristic_type(frame[col], False))
            for col in frame.columns}


def normalise_text(series: pd.Series) -> tuple[pd.Series, int, int]:
    """Trim, collapse inner spaces, blank -> NaN, unify case variants.

    Returns (series, cells changed by whitespace, cells changed by case).
    """
    original = series
    text = series.astype("string")
    stripped = text.str.strip().str.replace(r"\s+", " ", regex=True)
    stripped = stripped.mask(stripped == "")
    ws_changed = int(((original.astype("string") != stripped) & stripped.notna()).sum())

    counts = stripped.value_counts()
    canonical: dict[str, str] = {}
    for value in counts.index:  # most frequent spelling first
        canonical.setdefault(value.casefold(), value)
    unified = stripped.map(lambda v: canonical[v.casefold()] if pd.notna(v) else v)
    case_changed = int(((unified != stripped) & unified.notna()).sum())
    return unified.astype(object).where(unified.notna(), np.nan), ws_changed, case_changed


def coerce_numeric(series: pd.Series) -> tuple[pd.Series, int, int]:
    """Blank strings -> NaN, then numbers. Returns (series, blanks, unparseable)."""
    if series.dtype.kind in "iuf":
        return series.astype(float) if series.dtype.kind == "f" else series, 0, 0
    text = series.astype("string").str.strip().str.replace(",", "", regex=False)
    blanks = int((text == "").sum())
    text = text.mask(text == "")
    numbers = pd.to_numeric(text, errors="coerce")
    unparseable = int((numbers.isna() & text.notna()).sum())
    return numbers.astype(float), blanks, unparseable


def invalid_negatives(series: pd.Series, name: str) -> pd.Series:
    """Mask for a few negative values in a column that is otherwise never negative."""
    values = series.dropna()
    if values.empty or SIGNED_NAME.search(name):
        return pd.Series(False, index=series.index)
    negative = series < 0
    share = negative.sum() / len(values)
    if 0 < share <= INVALID_NEGATIVE_MAX_SHARE:
        return negative.fillna(False)
    return pd.Series(False, index=series.index)


def outlier_flags(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """(IQR mask, z-score mask) for one numeric column; NaN is never an outlier."""
    values = series.dropna()
    none = pd.Series(False, index=series.index)
    if len(values) < 4 or values.nunique() < 3:
        return none, none
    q1, q3 = values.quantile([0.25, 0.75])
    iqr = q3 - q1
    iqr_mask = ((series < q1 - IQR_K * iqr) | (series > q3 + IQR_K * iqr)).fillna(False)
    std = values.std(ddof=0)
    if std == 0:
        return iqr_mask, none
    z_mask = ((series - values.mean()).abs() / std > Z_LIMIT).fillna(False)
    return iqr_mask, z_mask


def map_target(series: pd.Series, positive_label: str) -> pd.Series:
    text = series.astype("string").str.strip()
    mapped = (text == str(positive_label)).astype("Int64")
    return mapped.mask(text.isna() | (text == ""))


def health_score(frame_before: int, dups: int, missing_pct: dict[str, float],
                 outlier_share: list[float], minority_share: float) -> int:
    m = float(np.mean(list(missing_pct.values())) / 100) if missing_pct else 0.0
    d = min(1.0, 10 * dups / frame_before) if frame_before else 0.0
    o = min(1.0, 5 * float(np.mean(outlier_share))) if outlier_share else 0.0
    b = min(1.0, max(0.0, 0.5 - minority_share) / 0.45)
    return int(round(min(100.0, max(0.0, 100 - 40 * m - 20 * d - 20 * o - 20 * b))))


def clean(frame: pd.DataFrame, schema: dict[str, Any], min_rows: int) -> CleaningResult:
    target = schema["target_column"]
    positive = str(schema["positive_label"])
    time_col = schema.get("time_column")
    if target not in frame.columns:
        raise CleaningFatal(f"Target column '{target}' is missing from the data.")

    df = frame.copy()
    log: list[dict[str, Any]] = []
    rows_before = len(df)
    types = column_types(df, schema)
    types[target] = "binary"
    missing_before = {c: round(float(df[c].isna().mean() * 100), 2) for c in df.columns}

    # 1. Types and text
    for col, kind in types.items():
        if col == target:
            continue
        if kind == "numeric":
            df[col], blanks, bad = coerce_numeric(df[col])
            _log(log, "blank_to_missing", col, blanks, "Blank text became missing.")
            _log(log, "coerce_numeric", col, bad, "Non-numeric text became missing.")
        elif kind == "datetime":
            parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
            _log(log, "coerce_datetime", col, int((parsed.isna() & df[col].notna()).sum()),
                 "Unparseable dates became missing.")
            df[col] = parsed
        elif kind in ("categorical", "binary", "text", "id"):
            df[col], ws, case = normalise_text(df[col])
            _log(log, "trim_whitespace", col, ws, "Trimmed or collapsed spaces.")
            _log(log, "unify_case", col, case, "Merged spellings that differ only in case.")

    # 2. Duplicates. Without an ID column, identical rows may be different
    # customers, so they are only flagged.
    dup_mask = df.duplicated(keep="first")
    has_ids = any(col in df.columns for col in schema.get("id_columns", []))
    dups = int(dup_mask.sum()) if has_ids else 0
    if has_ids:
        df = df.loc[~dup_mask]
        _log(log, "drop_duplicates", None, dups, "Removed exact duplicate rows.")
    else:
        _log(log, "possible_duplicates", None, int(dup_mask.sum()),
             "Identical rows kept: without an ID column they may be different customers.")
    for id_col in schema.get("id_columns", []):
        if id_col in df.columns:
            repeated = int(df[id_col].duplicated(keep=False).sum())
            _log(log, "duplicate_ids", id_col, repeated,
                 "Rows share an ID but differ in other columns; kept all of them.")

    # 3. Target
    df[target] = map_target(df[target], positive)
    no_target = int(df[target].isna().sum())
    df = df.loc[df[target].notna()]
    _log(log, "drop_missing_target", target, no_target, "Removed rows without a target value.")
    df[target] = df[target].astype(int)
    _log(log, "map_target", target, len(df), f"Mapped '{positive}' to 1, the other value to 0.")

    # 4. Invalid values, missing categoricals, outliers
    outliers: dict[str, dict[str, int]] = {}
    outlier_share: list[float] = []
    for col, kind in types.items():
        if col == target or col not in df.columns:
            continue
        if kind == "numeric":
            neg = invalid_negatives(df[col], col)
            if neg.any():
                df.loc[neg, col] = np.nan
                _log(log, "invalid_negative", col, int(neg.sum()),
                     "Negative values in a never-negative column became missing.")
            iqr_mask, z_mask = outlier_flags(df[col])
            outliers[col] = {"iqr": int(iqr_mask.sum()), "zscore": int(z_mask.sum())}
            outlier_share.append(float(iqr_mask.mean()) if len(df) else 0.0)
            _log(log, "flag_outliers", col, int((iqr_mask | z_mask).sum()),
                 f"Flagged, not changed: {outliers[col]['iqr']} by IQR, "
                 f"{outliers[col]['zscore']} by z-score.")
            if df[col].isna().any():
                _log(log, "missing_left_for_model", col, int(df[col].isna().sum()),
                     "Left missing; the model imputes the training-set median.")
        elif kind in ("categorical", "binary") and col != time_col:
            n_missing = int(df[col].isna().sum())
            if n_missing:
                df[col] = df[col].fillna(UNKNOWN)
                _log(log, "fill_unknown", col, n_missing, f"Missing values became '{UNKNOWN}'.")

    df = df.reset_index(drop=True)

    # 5. Fatal checks
    if len(df) < min_rows:
        removed = rows_before - len(df)
        raise CleaningFatal(
            f"Only {len(df)} rows remain after cleaning ({removed} removed as duplicates or "
            f"missing target); at least {min_rows} are needed."
        )
    positives = int(df[target].sum())
    negatives = len(df) - positives
    if positives == 0 or negatives == 0:
        raise CleaningFatal(
            f"The target '{target}' has only one class after cleaning; churn cannot be "
            "analysed without both churned and retained customers."
        )

    minority = min(positives, negatives) / len(df)
    missing_after = {c: round(float(df[c].isna().mean() * 100), 2) for c in df.columns}
    health = {
        "rows_before": rows_before,
        "rows_after": len(df),
        "columns": len(df.columns),
        "duplicates_removed": dups,
        "missing_pct_before": missing_before,
        "missing_pct_after": missing_after,
        "outliers_flagged": outliers,
        "class_balance": {"positive": positives, "negative": negatives,
                          "positive_rate": round(positives / len(df), 4),
                          "positive_label": positive},
        "health_score": health_score(rows_before, dups, missing_before, outlier_share,
                                     minority),
        "score_formula": HEALTH_FORMULA,
    }
    return CleaningResult(df, log, health)
