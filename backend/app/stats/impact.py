"""Impact estimates (docs/SPEC.md node 10). Python only; these are the ONLY impact
numbers recommendations may use.

For each segment and each high-churn level of a significant categorical
variable: customers affected, churn rate, churners, monthly revenue at risk
(if a revenue column was confirmed) and what a 10% or 25% relative churn
reduction would save. These are what-if scenarios on observed churn, not
causal predictions.
"""

from typing import Any

import numpy as np
import pandas as pd

from app.stats.common import jsonable

SCENARIOS = {"reduce_10pct": 0.10, "reduce_25pct": 0.25}
MIN_GROUP = 30
MIN_LIFT = 1.1
MAX_ITEMS = 40
OTHER = "Other"


def _scenario_text(share: float) -> str:
    return (f"If churn in this group fell by {share:.0%} (relative), with everything else "
            "unchanged. Based on observed churn; not a causal estimate.")


def group_impact(mask: pd.Series, y: pd.Series, revenue: pd.Series | None,
                 overall_rate: float) -> dict[str, Any]:
    n = int(mask.sum())
    churners = int(y[mask].sum())
    rate = churners / n if n else 0.0
    at_risk = float(revenue[mask & (y == 1)].sum()) if revenue is not None else None
    scenarios = {}
    for key, share in SCENARIOS.items():
        scenarios[key] = {
            "relative_reduction": share,
            "churners_saved": round(churners * share, 1),
            "monthly_revenue_saved": round(at_risk * share, 2) if at_risk is not None else None,
            "assumption": _scenario_text(share),
        }
    return {
        "customers": n,
        "pct_of_base": n / len(y) if len(y) else 0.0,
        "churners": churners,
        "churn_rate": rate,
        "lift_vs_overall": rate / overall_rate if overall_rate else None,
        "monthly_revenue_at_risk": round(at_risk, 2) if at_risk is not None else None,
        "scenarios": scenarios,
    }


def run_impact(frame: pd.DataFrame, schema: dict[str, Any], segments: dict[str, Any] | None,
               segment_labels: np.ndarray | None,
               hypothesis: dict[str, Any] | None) -> dict[str, Any]:
    y = frame[schema["target_column"]].astype(int)
    revenue_col = schema.get("revenue_column")
    revenue = (pd.to_numeric(frame[revenue_col], errors="coerce").fillna(0.0)
               if revenue_col and revenue_col in frame.columns else None)
    overall_rate = float(y.mean())
    everyone = pd.Series(True, index=frame.index)

    items: list[dict[str, Any]] = []
    if segments and not segments.get("skipped") and segment_labels is not None:
        labels = pd.Series(segment_labels, index=frame.index)
        for seg in segments.get("segments", []):
            mask = labels == seg["segment"]
            if mask.sum() >= MIN_GROUP:
                items.append({"id": f"segment_{seg['segment']}", "kind": "segment",
                              "label": f"Segment {seg['segment']}: {seg['label']}",
                              **group_impact(mask, y, revenue, overall_rate)})

    for test in (hypothesis or {}).get("tests", []):
        if test.get("kind") != "categorical" or not test.get("significant"):
            continue
        variable = test["variable"]
        if variable not in frame.columns:
            continue
        values = frame[variable].astype("string")
        for level in values.dropna().unique():
            if level == OTHER and level in test.get("merged_levels", []):
                continue
            mask = (values == level).fillna(False)
            if mask.sum() < MIN_GROUP:
                continue
            impact = group_impact(mask, y, revenue, overall_rate)
            if impact["lift_vs_overall"] and impact["lift_vs_overall"] >= MIN_LIFT:
                items.append({"id": f"{variable}={level}", "kind": "category",
                              "variable": variable, "level": str(level),
                              "label": f"{variable} = {level}", **impact})

    items.sort(key=lambda it: (-it["churners"], it["id"]))
    items = items[:MAX_ITEMS]
    return jsonable({
        "overall": {"id": "overall", "label": "All customers",
                    **group_impact(everyone, y, revenue, overall_rate)},
        "items": {it["id"]: it for it in items},
        "item_order": [it["id"] for it in items],
        "revenue_column": revenue_col if revenue is not None else None,
        "revenue_note": (f"Monthly revenue from '{revenue_col}' of customers who churned."
                         if revenue is not None else
                         "No revenue column was confirmed, so revenue figures are not available."),
        "scenarios": {k: _scenario_text(v) for k, v in SCENARIOS.items()},
    })
