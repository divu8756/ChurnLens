"""Customer table for experiments, built from an analysed session: cleaned data joined
to the Phase 4 predictions, plus the balance covariates."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app import sessions
from app.agents.offer_message import CACHE_FILE

PLAN_HINTS = ("contract", "plan", "tier", "package", "subscription")


class NotAnalysed(LookupError):
    """The session has no finished analysis (no cleaned data or predictions)."""


def plan_column(schema: dict[str, Any], frame: pd.DataFrame) -> str | None:
    """The categorical column that looks most like a plan / contract type. Hints are tried
    in priority order (so "Contract" beats "CityTier"); ties go to column order."""
    kinds = {c["name"]: c.get("semantic_type") for c in schema.get("columns", [])}
    candidates = [c for c in frame.columns
                  if kinds.get(c, "categorical") in ("categorical", "binary")
                  and not pd.api.types.is_numeric_dtype(frame[c])]
    for hint in PLAN_HINTS:
        for col in candidates:
            if hint in str(col).lower():
                return str(col)
    return None


def session_customers(values: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, str]]:
    """(one row per customer, balance covariates {column: numeric | categorical})."""
    schema = values.get("confirmed_schema") or {}
    clean_path, pred_path = values.get("clean_path"), values.get("predictions_path")
    if not schema or not clean_path or not pred_path or not Path(pred_path).exists():
        raise NotAnalysed("This session has no finished analysis with risk predictions.")
    frame = pd.read_parquet(clean_path)
    ids = [c for c in schema.get("id_columns", []) if c in frame.columns]
    # Same ID rule as stats/predictions.py, so the join always lines up.
    frame["customer_id"] = (frame[ids[0]].astype(str).to_numpy() if ids
                            else np.arange(len(frame)).astype(str))
    preds = pd.read_parquet(pred_path)[
        ["customer_id", "churn_probability", "risk_band", "actual_churn"]]
    merged = frame.merge(preds.drop_duplicates("customer_id"), on="customer_id", how="inner")
    merged = merged.drop_duplicates("customer_id").reset_index(drop=True)

    covariates = {"churn_probability": "numeric"}
    for key in ("time_column", "revenue_column"):
        col = schema.get(key)
        if col and col in merged.columns:
            covariates[col] = "numeric"
    plan = plan_column(schema, merged)
    if plan:
        covariates[plan] = "categorical"
    return merged, covariates


def cached_messages(session_id: str, offer: str) -> dict[str, str]:
    """Offer messages already generated in Phase 5b for this offer, by customer ID.
    Never generates new ones (that would be one LLM call per customer)."""
    try:
        path = sessions.session_dir(session_id) / CACHE_FILE
    except sessions.SessionNotFound:
        return {}
    if not path.exists():
        return {}
    cache = json.loads(path.read_text(encoding="utf-8"))
    suffix = f"␟{offer}"
    return {key.removesuffix(suffix): entry["message"] for key, entry in cache.items()
            if key.endswith(suffix) and isinstance(entry, dict) and entry.get("message")}
