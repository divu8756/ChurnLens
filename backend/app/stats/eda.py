"""Exploratory data analysis (docs/SPEC.md node 5). Pure functions: frame in, dict out.

The target column is already 0/1 (1 = churned) after cleaning.
"""

from typing import Any

import numpy as np
import pandas as pd

from app.stats.common import feature_columns, jsonable

MAX_LEVELS = 20
OTHER = "Other"
HIST_BINS = 20
MONTH_BANDS = [0, 6, 12, 24, 48, np.inf]


def overview(y: pd.Series) -> dict[str, Any]:
    return {"rows": int(len(y)), "churned": int(y.sum()),
            "churn_rate": float(y.mean()) if len(y) else None}


def numeric_summary(x: pd.Series, y: pd.Series) -> dict[str, Any]:
    values = x.dropna()
    churned, retained = x[y == 1].dropna(), x[y == 0].dropna()

    def stats(s: pd.Series) -> dict[str, Any]:
        if s.empty:
            return {"n": 0, "mean": None, "median": None, "std": None}
        return {"n": int(len(s)), "mean": float(s.mean()), "median": float(s.median()),
                "std": float(s.std(ddof=1)) if len(s) > 1 else None}

    summary: dict[str, Any] = {
        "count": int(len(values)),
        "missing": int(x.isna().sum()),
        "churned": stats(churned),
        "retained": stats(retained),
    }
    if values.empty:
        summary.update({k: None for k in ("mean", "std", "min", "q25", "median", "q75", "max")})
        summary["histogram"] = {"edges": [], "counts": []}
        return summary
    q = values.quantile([0.25, 0.5, 0.75])
    summary.update({
        "mean": float(values.mean()),
        "std": float(values.std(ddof=1)) if len(values) > 1 else None,
        "min": float(values.min()), "q25": float(q[0.25]), "median": float(q[0.5]),
        "q75": float(q[0.75]), "max": float(values.max()),
    })
    bins = min(HIST_BINS, max(1, int(values.nunique())))
    counts, edges = np.histogram(values, bins=bins)
    summary["histogram"] = {"edges": edges.tolist(), "counts": counts.tolist()}
    return summary


def churn_by_category(x: pd.Series, y: pd.Series) -> dict[str, Any]:
    """Churn rate per level (with n), sorted by churn rate; > 20 levels folded into Other."""
    levels = x.astype("string").fillna("Missing")
    counts = levels.value_counts()
    folded = 0
    if len(counts) > MAX_LEVELS:
        keep = set(counts.index[: MAX_LEVELS - 1])
        folded = len(counts) - (MAX_LEVELS - 1)
        levels = levels.where(levels.isin(keep), OTHER)
    table = pd.DataFrame({"level": levels, "y": y}).groupby("level", observed=True)["y"]
    rows = [{"level": str(level), "n": int(g.size), "churned": int(g.sum()),
             "churn_rate": float(g.mean())} for level, g in table]
    rows.sort(key=lambda r: (-r["churn_rate"], -r["n"], r["level"]))
    return {"levels": rows, "levels_folded_into_other": folded}


def correlation(frame: pd.DataFrame, numeric: list[str], target: str) -> dict[str, Any]:
    usable = [c for c in numeric if frame[c].notna().sum() > 1 and frame[c].nunique() > 1]
    if not usable:
        return {"columns": [], "matrix": [], "with_target": {}}
    matrix = frame[usable].corr(method="pearson")
    with_target = {c: frame[c].corr(frame[target]) for c in usable}
    return {"columns": usable, "matrix": matrix.to_numpy().tolist(),
            "with_target": with_target}


def tenure_bands(time: pd.Series, y: pd.Series) -> dict[str, Any]:
    values = time.dropna()
    if values.empty:
        return {"bands": []}
    if values.max() <= 120:
        edges = MONTH_BANDS
    else:
        edges = sorted(set(values.quantile([0, 0.2, 0.4, 0.6, 0.8]).tolist())) + [np.inf]
    labels = []
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        labels.append(f"{lo:g}+" if np.isinf(hi) else f"{lo:g}-{hi:g}")
    bands = pd.cut(time, bins=edges, labels=labels, right=False, include_lowest=True)
    rows = []
    for label in labels:
        mask = bands == label
        n = int(mask.sum())
        if n:
            rows.append({"band": label, "n": n, "churned": int(y[mask].sum()),
                         "churn_rate": float(y[mask].mean())})
    return {"bands": rows, "unit": "same as the time column"}


def run_eda(frame: pd.DataFrame, schema: dict[str, Any]) -> dict[str, Any]:
    target = schema["target_column"]
    y = frame[target].astype(int)
    cols = feature_columns(frame, schema)
    time_col = schema.get("time_column")
    result: dict[str, Any] = {
        "overview": overview(y),
        "numeric": {c: numeric_summary(frame[c], y) for c in cols["numeric"]},
        "categorical": {c: churn_by_category(frame[c], y) for c in cols["categorical"]},
        "correlation": correlation(frame, cols["numeric"], target),
        "tenure_bands": (tenure_bands(frame[time_col], y)
                         if time_col and time_col in frame.columns else None),
    }
    return jsonable(result)
