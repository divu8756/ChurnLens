"""Churn model training and evaluation (docs/SPEC.md node 9, runbook T4.1).

- Features: every analysis column except ids, the target, datetimes, free text
  and any explicitly excluded columns (for example offer/treatment columns).
- Stratified 80/20 split (seed 42) BEFORE any transformer is fitted.
- Two sklearn Pipelines (impute + scale / impute + one-hot), compared by
  5-fold stratified CV PR-AUC on the training split only.
- The chosen model is evaluated ONCE on the test split.
- Leakage guard: test ROC-AUC > 0.99 is an error; a single feature with
  |correlation| > 0.9 with the target is a warning.
- Permutation importance on the test split, on ORIGINAL column names.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.stats.common import feature_columns, jsonable

RANDOM_STATE = 42
TEST_SIZE = 0.2
CV_FOLDS = 5
THRESHOLD = 0.5
LEAKAGE_AUC = 0.99
LEAKAGE_CORR = 0.9
ROC_POINTS = 100
PERMUTATION_REPEATS = 10
MODEL_NAMES = {"logistic_regression": "Logistic regression",
               "gradient_boosting": "Gradient boosting"}


class LeakageError(ValueError):
    """The model is too good to be true; a feature probably leaks the target."""


@dataclass
class ModelArtifacts:
    pipeline: Pipeline
    model_key: str
    numeric: list[str]
    categorical: list[str]
    train_index: np.ndarray
    test_index: np.ndarray


def model_features(frame: pd.DataFrame, schema: dict[str, Any],
                   exclude: list[str] | None = None) -> tuple[list[str], list[str]]:
    groups = feature_columns(frame, schema)
    skip = set(exclude or [])
    numeric = [c for c in groups["numeric"] if c not in skip and frame[c].notna().any()]
    categorical = [c for c in groups["categorical"] if c not in skip]
    return numeric, categorical


def preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    return ColumnTransformer([
        ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), numeric),
        ("cat", make_pipeline(SimpleImputer(strategy="most_frequent"),
                              OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
         categorical),
    ])


def candidate_models(numeric: list[str], categorical: list[str]) -> dict[str, Pipeline]:
    return {
        "logistic_regression": Pipeline([
            ("prep", preprocessor(numeric, categorical)),
            ("model", LogisticRegression(class_weight="balanced", max_iter=2000,
                                         random_state=RANDOM_STATE)),
        ]),
        "gradient_boosting": Pipeline([
            ("prep", preprocessor(numeric, categorical)),
            ("model", HistGradientBoostingClassifier(class_weight="balanced",
                                                     random_state=RANDOM_STATE)),
        ]),
    }


def leakage_warnings(x: pd.DataFrame, y: pd.Series, numeric: list[str],
                     categorical: list[str]) -> list[dict[str, Any]]:
    warnings = []
    for col in numeric:
        values = x[col]
        if values.notna().sum() > 2 and values.nunique() > 1:
            corr = values.corr(y)
            if pd.notna(corr) and abs(corr) > LEAKAGE_CORR:
                warnings.append({"column": col, "measure": "Pearson r", "value": float(corr)})
    for col in categorical:
        table = pd.crosstab(x[col].astype("string"), y)
        if table.shape[0] > 1 and table.shape[1] > 1:
            chi2 = chi2_contingency(table, correction=False)[0]
            v = float(np.sqrt(chi2 / (table.to_numpy().sum() * (min(table.shape) - 1))))
            if v > LEAKAGE_CORR:
                warnings.append({"column": col, "measure": "Cramér's V", "value": v})
    return warnings


def roc_points(y_true: np.ndarray, scores: np.ndarray) -> dict[str, list[float]]:
    fpr, tpr, _ = roc_curve(y_true, scores)
    if len(fpr) > ROC_POINTS:
        idx = np.unique(np.linspace(0, len(fpr) - 1, ROC_POINTS).round().astype(int))
        fpr, tpr = fpr[idx], tpr[idx]
    return {"fpr": fpr.tolist(), "tpr": tpr.tolist()}


def test_metrics(y_true: np.ndarray, proba: np.ndarray) -> dict[str, Any]:
    pred = (proba >= THRESHOLD).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    return {
        "threshold": THRESHOLD,
        "n_test": int(len(y_true)),
        "accuracy": accuracy_score(y_true, pred),
        "precision": precision_score(y_true, pred, zero_division=0),
        "recall": recall_score(y_true, pred, zero_division=0),
        "f1": f1_score(y_true, pred, zero_division=0),
        "roc_auc": roc_auc_score(y_true, proba),
        "pr_auc": average_precision_score(y_true, proba),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "roc_curve": roc_points(y_true, proba),
    }


def train_and_evaluate(
    frame: pd.DataFrame, schema: dict[str, Any], exclude: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], ModelArtifacts]:
    """Returns (model_metrics, feature_importance, artifacts)."""
    target = schema["target_column"]
    numeric, categorical = model_features(frame, schema, exclude)
    features = numeric + categorical
    if not features:
        raise ValueError("No usable feature columns for the model.")
    x = frame[features]
    y = frame[target].astype(int)

    idx_train, idx_test = train_test_split(
        np.arange(len(frame)), test_size=TEST_SIZE, stratify=y, random_state=RANDOM_STATE)
    x_train, x_test = x.iloc[idx_train], x.iloc[idx_test]
    y_train, y_test = y.iloc[idx_train], y.iloc[idx_test]

    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    cv_results: dict[str, dict[str, Any]] = {}
    models = candidate_models(numeric, categorical)
    for key, pipe in models.items():
        scores = cross_validate(pipe, x_train, y_train, cv=cv,
                                scoring={"roc_auc": "roc_auc", "pr_auc": "average_precision"})
        cv_results[key] = {
            "name": MODEL_NAMES[key],
            "roc_auc_mean": float(scores["test_roc_auc"].mean()),
            "roc_auc_std": float(scores["test_roc_auc"].std(ddof=1)),
            "pr_auc_mean": float(scores["test_pr_auc"].mean()),
            "pr_auc_std": float(scores["test_pr_auc"].std(ddof=1)),
        }
    best = max(cv_results, key=lambda k: (cv_results[k]["pr_auc_mean"], k))
    pipeline = models[best].fit(x_train, y_train)

    proba = pipeline.predict_proba(x_test)[:, 1]
    metrics = test_metrics(y_test.to_numpy(), proba)
    if metrics["roc_auc"] > LEAKAGE_AUC:
        raise LeakageError(
            f"Test ROC-AUC is {metrics['roc_auc']:.3f}, which is too good to be true. A column "
            "probably records the outcome itself (for example a churn date or reason). Mark it "
            "as an ID or remove it and re-run."
        )

    perm = permutation_importance(pipeline, x_test, y_test, scoring="roc_auc",
                                  n_repeats=PERMUTATION_REPEATS, random_state=RANDOM_STATE)
    importance = sorted(
        ({"feature": f, "importance_mean": float(m), "importance_std": float(s)}
         for f, m, s in zip(features, perm.importances_mean, perm.importances_std, strict=True)),
        key=lambda r: -r["importance_mean"])
    for rank, row in enumerate(importance, start=1):
        row["rank"] = rank

    model_metrics = jsonable({
        "chosen_model": best,
        "chosen_model_name": MODEL_NAMES[best],
        "selection_rule": "Highest mean 5-fold CV PR-AUC on the training split.",
        "cv": cv_results,
        "test": metrics,
        "n_train": int(len(idx_train)),
        "n_test": int(len(idx_test)),
        "train_churn_rate": float(y_train.mean()),
        "test_churn_rate": float(y_test.mean()),
        "features": {"numeric": numeric, "categorical": categorical,
                     "excluded": sorted(set(exclude or []) & set(frame.columns))},
        "leakage_warnings": leakage_warnings(x_train, y_train, numeric, categorical),
    })
    feature_importance = jsonable({
        "method": "Permutation importance on the test split (ROC-AUC drop, 10 repeats)",
        "features": importance,
    })
    artifacts = ModelArtifacts(pipeline, best, numeric, categorical, idx_train, idx_test)
    return model_metrics, feature_importance, artifacts


def save_artifacts(artifacts: ModelArtifacts, path: Path) -> None:
    joblib.dump(artifacts, path)


def load_artifacts(path: str | Path) -> ModelArtifacts:
    return joblib.load(path)
