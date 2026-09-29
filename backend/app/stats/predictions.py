"""Per-customer churn scores, risk bands and top-3 SHAP reasons (runbook T4.3)."""

from typing import Any

import numpy as np
import pandas as pd

from app.stats.explain import shap_values
from app.stats.modelling import ModelArtifacts

RANDOM_STATE = 42
BACKGROUND_ROWS = 100
TOP_REASONS = 3
BANDS = ("High", "Medium", "Low")


def risk_band(probability: np.ndarray, high: float, medium: float) -> np.ndarray:
    if not 0 < medium < high < 1:
        raise ValueError("Risk thresholds must satisfy 0 < medium < high < 1.")
    return np.where(probability >= high, "High", np.where(probability >= medium, "Medium", "Low"))


def describe(feature: str, value: Any, contribution: float, numeric: bool) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        shown = "missing"
    elif numeric:
        shown = f"{float(value):,.4g}"
    else:
        shown = str(value)
    sep = " = " if numeric else ": "
    return f"{feature}{sep}{shown} ({contribution:+.2f})"


def score_customers(artifacts: ModelArtifacts, frame: pd.DataFrame, schema: dict[str, Any],
                    high: float, medium: float) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Returns (predictions table, summary with band counts and thresholds)."""
    features = artifacts.numeric + artifacts.categorical
    x = frame[features]
    probability = artifacts.pipeline.predict_proba(x)[:, 1]
    bands = risk_band(probability, high, medium)

    rng = np.random.default_rng(RANDOM_STATE)
    bg_idx = rng.choice(artifacts.train_index,
                        min(BACKGROUND_ROWS, len(artifacts.train_index)), replace=False)
    contributions, method = shap_values(artifacts, x, x.iloc[bg_idx])

    k = min(TOP_REASONS, len(features))
    top = np.argsort(-contributions, axis=1, kind="stable")[:, :k]
    numeric = set(artifacts.numeric)
    reasons: list[list[str]] = []
    values = x.to_numpy(dtype=object)
    for row in range(len(x)):
        reasons.append([describe(features[j], values[row, j], float(contributions[row, j]),
                                 features[j] in numeric) for j in top[row]])

    ids = [c for c in schema.get("id_columns", []) if c in frame.columns]
    table = pd.DataFrame({
        "customer_id": frame[ids[0]].astype(str).to_numpy() if ids
        else np.arange(len(frame)).astype(str),
        "churn_probability": np.round(probability, 3),
        "risk_band": bands,
        "actual_churn": frame[schema["target_column"]].astype(int).to_numpy(),
    })
    for i in range(TOP_REASONS):
        table[f"reason_{i + 1}"] = [r[i] if i < len(r) else None for r in reasons]
    table = table.sort_values("churn_probability", ascending=False, kind="stable")
    table = table.reset_index(drop=True)

    counts = {band: int((bands == band).sum()) for band in BANDS}
    summary = {
        "thresholds": {"high": high, "medium": medium},
        "band_counts": counts,
        "total": int(len(table)),
        "explainer": method,
        "reason_format": "feature value (SHAP contribution in log-odds; + raises churn risk)",
    }
    return table, summary
