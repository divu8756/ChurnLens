"""modelling_node: thin wrapper around app/stats/modelling.py and app/stats/explain.py."""

from pathlib import Path
from typing import Any

import pandas as pd

from app.config import get_settings
from app.graph.errors import FatalNodeError
from app.graph.state import ChurnState, ErrorEntry, ProgressEntry
from app.schema_validation import offer_column_names
from app.stats.explain import driver_impact, odds_ratios, shap_summary
from app.stats.model_metrics import model_metrics_v2
from app.stats.modelling import LeakageError, save_artifacts, train_and_evaluate
from app.stats.predictions import score_customers

MODEL_FILE = "model.joblib"
PREDICTIONS_FILE = "predictions.parquet"


def treatment_columns(state: ChurnState) -> list[str]:
    """Offer/campaign columns confirmed in Phase 5b are treatments, not traits."""
    return offer_column_names(state.offer_columns)


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
    # Explanations and calibration are valuable but not essential: failures are logged.
    errors: list[ErrorEntry] = []
    metrics_v2: dict[str, Any] | None = None
    calibrated = None
    try:
        x = frame[artifacts.numeric + artifacts.categorical]
        metrics_v2, calibrated, artifacts.calibrator = model_metrics_v2(
            artifacts, x, frame[schema["target_column"]].astype(int))
    except Exception as exc:
        errors.append(ErrorEntry(node="modelling", message=f"Calibration failed, using raw "
                                                           f"probabilities: {exc}"))
    path = Path(state.clean_path).with_name(MODEL_FILE)
    save_artifacts(artifacts, path)
    metrics["model_path"] = str(path)

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

    settings = get_settings()
    predictions_path: str | None = None
    try:
        table, summary = score_customers(artifacts, frame, schema,
                                         settings.RISK_HIGH, settings.RISK_MEDIUM, calibrated)
        target = Path(state.clean_path).with_name(PREDICTIONS_FILE)
        table.to_parquet(target, index=False)
        predictions_path = str(target)
        metrics["risk_bands"] = summary
    except Exception as exc:
        errors.append(ErrorEntry(node="modelling", message=f"Scoring failed: {exc}"))

    test = metrics["test"]
    return {
        "model_metrics": metrics,
        "model_metrics_v2": metrics_v2,
        "feature_importance": importance,
        "shap_summary": shap_result,
        "odds_ratios": odds,
        "predictions_path": predictions_path,
        "errors": errors,
        "progress": [ProgressEntry(
            node="modelling", status="done",
            detail=f"{metrics['chosen_model_name']}, test ROC-AUC {test['roc_auc']:.3f}")],
    }
