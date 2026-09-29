"""Survival analysis with lifelines (docs/SPEC.md node 7).

Duration = the confirmed time column (for example tenure in months); event =
churned (target = 1). Kaplan-Meier overall and for the 3 categoricals most
associated with churn (Cramér's V, 2-6 levels), with log-rank tests.
"""

from typing import Any

import numpy as np
import pandas as pd
from lifelines import KaplanMeierFitter
from lifelines.statistics import multivariate_logrank_test
from scipy.stats import chi2_contingency

from app.stats.common import feature_columns, jsonable

MAX_POINTS = 200
TOP_CATEGORICALS = 3
MIN_LEVELS, MAX_LEVELS = 2, 6
HORIZONS = (6, 12, 24)
MIN_GROUP_SIZE = 5


def downsample(times: np.ndarray, values: list[np.ndarray],
               max_points: int = MAX_POINTS) -> tuple[np.ndarray, list[np.ndarray]]:
    """Evenly spaced points, always keeping the first and last."""
    if len(times) <= max_points:
        return times, values
    idx = np.unique(np.linspace(0, len(times) - 1, max_points).round().astype(int))
    return times[idx], [v[idx] for v in values]


def km_summary(durations: pd.Series, events: pd.Series, label: str) -> dict[str, Any]:
    kmf = KaplanMeierFitter(label=label).fit(durations, events)
    sf = kmf.survival_function_[label].to_numpy()
    ci = kmf.confidence_interval_survival_function_.to_numpy()
    times = kmf.survival_function_.index.to_numpy(dtype=float)
    times, (sf, lower, upper) = downsample(times, [sf, ci[:, 0], ci[:, 1]])
    median = kmf.median_survival_time_
    max_t = float(durations.max())
    at = {str(h): (float(kmf.survival_function_at_times(h).iloc[0]) if h <= max_t else None)
          for h in HORIZONS}
    return {
        "label": label,
        "n": int(len(durations)),
        "events": int(events.sum()),
        "median_survival": None if np.isinf(median) else float(median),
        "median_reached": bool(not np.isinf(median)),
        "survival_at": at,
        "curve": {"time": times.tolist(), "survival": sf.tolist(),
                  "ci_lower": lower.tolist(), "ci_upper": upper.tolist()},
    }


def cramers_v(x: pd.Series, y: pd.Series) -> float:
    table = pd.crosstab(x, y)
    if table.shape[0] < 2 or table.shape[1] < 2:
        return 0.0
    chi2 = chi2_contingency(table, correction=False)[0]
    n = table.to_numpy().sum()
    return float(np.sqrt(chi2 / (n * (min(table.shape) - 1))))


def pick_categoricals(frame: pd.DataFrame, categoricals: list[str], target: str) -> list[str]:
    scored = []
    for col in categoricals:
        levels = frame[col].nunique(dropna=True)
        if MIN_LEVELS <= levels <= MAX_LEVELS:
            scored.append((cramers_v(frame[col], frame[target]), col))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [col for _, col in scored[:TOP_CATEGORICALS]]


def run_survival(frame: pd.DataFrame, schema: dict[str, Any]) -> dict[str, Any]:
    time_col, target = schema.get("time_column"), schema["target_column"]
    if not time_col or time_col not in frame.columns:
        return {"skipped": True, "reason": "No time column was confirmed."}
    data = frame[[time_col, target, *feature_columns(frame, schema)["categorical"]]].copy()
    data[time_col] = pd.to_numeric(data[time_col], errors="coerce")
    dropped = int((data[time_col].isna() | (data[time_col] < 0)).sum())
    data = data[data[time_col].notna() & (data[time_col] >= 0)]
    if data.empty or data[target].sum() == 0:
        return {"skipped": True, "reason": "No usable durations or no churn events."}
    durations, events = data[time_col], data[target].astype(int)

    groups = []
    for col in pick_categoricals(data, feature_columns(frame, schema)["categorical"], target):
        levels = [lvl for lvl, n in data[col].value_counts().items() if n >= MIN_GROUP_SIZE]
        subset = data[data[col].isin(levels)]
        test = multivariate_logrank_test(subset[time_col], subset[col], subset[target])
        groups.append({
            "column": col,
            "cramers_v": cramers_v(data[col], data[target]),
            "logrank": {"statistic": float(test.test_statistic), "p_value": float(test.p_value),
                        "df": int(test.degrees_of_freedom)},
            "curves": [km_summary(subset.loc[subset[col] == lvl, time_col],
                                  subset.loc[subset[col] == lvl, target], str(lvl))
                       for lvl in sorted(levels, key=str)],
        })

    return jsonable({
        "skipped": False,
        "time_column": time_col,
        "rows_dropped_no_duration": dropped,
        "overall": km_summary(durations, events, "All customers"),
        "by_group": groups,
        "horizons": list(HORIZONS),
    })
