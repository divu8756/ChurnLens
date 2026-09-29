"""modelling_node: thin wrapper around app/stats/modelling.py and app/stats/explain.py."""

from pathlib import Path
from typing import Any

import pandas as pd

from app.graph.errors import FatalNodeError
from app.graph.state import ChurnState, ErrorEntry, ProgressEntry
from app.stats.explain import driver_impact, odds_ratios, shap_summary
from app.stats.modelling import LeakageError, save_artifacts, train_and_evaluate

MODEL_FILE = "model.joblib"


def treatment_columns(state: ChurnState) -> list[str]:
    """Offer/campaign columns confirmed in Phase 5b are treatments, not traits."""
    offers = state.offer_columns or {}
    return [str(v) for v in offers.values() if isinstance(v, str)]


def modelling_node(state: ChurnState) -> dict[str, Any]:
    if not state.clean_path or not state.confirmed_schema:
        raise FatalNodeError("Modelling needs cleaned data and a confirmed schema.")
    schema = state.confirmed_schema
    frame = pd.read_parquet(state.clean_path)
    try:
        metrics, importance, artifacts = train_and_evaluate(
            frame, schema, exclude=treatment_columns(state))
    except LeakageError as exc:
        raise FatalNodeError(str(exc)) from None
    path = Path(state.clean_path).with_name(MODEL_FILE)
    save_artifacts(artifacts, path)
    metrics["model_path"] = str(path)

    # Explanations are valuable but not essential: a failure is logged, not fatal.
    errors: list[ErrorEntry] = []
    shap_result: dict[str, Any] = {"global": [], "beeswarm": [], "error": None}
    odds: dict[str, Any] = {"terms": [], "dropped": [], "error": None}
    try:
        shap_result = shap_summary(artifacts, frame)
    except Exception as exc:
        shap_result["error"] = f"{type(exc).__name__}: {exc}"
        errors.append(ErrorEntry(node="modelling", message=f"SHAP failed: {exc}"))
    try:
        odds = odds_ratios(artifacts, frame, schema["target_column"])
    except Exception as exc:
        odds["error"] = f"{type(exc).__name__}: {exc}"
        errors.append(ErrorEntry(node="modelling", message=f"Odds ratios failed: {exc}"))
    importance["driver_impact"] = driver_impact(importance, shap_result, odds,
                                                state.hypothesis_results)

    test = metrics["test"]
    return {
        "model_metrics": metrics,
        "feature_importance": importance,
        "shap_summary": shap_result,
        "odds_ratios": odds,
        "errors": errors,
        "progress": [ProgressEntry(
            node="modelling", status="done",
            detail=f"{metrics['chosen_model_name']}, test ROC-AUC {test['roc_auc']:.3f}")],
    }
