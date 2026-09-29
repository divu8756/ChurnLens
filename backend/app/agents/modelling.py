"""modelling_node: thin wrapper around app/stats/modelling.py."""

from pathlib import Path
from typing import Any

import pandas as pd

from app.graph.errors import FatalNodeError
from app.graph.state import ChurnState, ProgressEntry
from app.stats.modelling import LeakageError, save_artifacts, train_and_evaluate

MODEL_FILE = "model.joblib"


def treatment_columns(state: ChurnState) -> list[str]:
    """Offer/campaign columns confirmed in Phase 5b are treatments, not traits."""
    offers = state.offer_columns or {}
    return [str(v) for v in offers.values() if isinstance(v, str)]


def modelling_node(state: ChurnState) -> dict[str, Any]:
    if not state.clean_path or not state.confirmed_schema:
        raise FatalNodeError("Modelling needs cleaned data and a confirmed schema.")
    frame = pd.read_parquet(state.clean_path)
    try:
        metrics, importance, artifacts = train_and_evaluate(
            frame, state.confirmed_schema, exclude=treatment_columns(state))
    except LeakageError as exc:
        raise FatalNodeError(str(exc)) from None
    path = Path(state.clean_path).with_name(MODEL_FILE)
    save_artifacts(artifacts, path)
    metrics["model_path"] = str(path)
    test = metrics["test"]
    return {
        "model_metrics": metrics,
        "feature_importance": importance,
        "progress": [ProgressEntry(
            node="modelling", status="done",
            detail=f"{metrics['chosen_model_name']}, test ROC-AUC {test['roc_auc']:.3f}")],
    }
