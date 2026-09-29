"""Model metrics on the held-out test split, and probability calibration (runbook T5d.1).

Pure functions: arrays in, JSON-serialisable dicts out. Every metric is computed on the
Phase 4 test split only; the calibrator is fitted on the training split only (isotonic
when n_train >= 1000, else sigmoid, 5-fold), so money metrics can use calibrated
probabilities (CLAUDE.md rule 23) without touching the test customers.
"""

import math
from typing import Any

import numpy as np
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold

from app.stats.common import jsonable
from app.stats.modelling import RANDOM_STATE, ModelArtifacts, roc_points

TOP_SHARE = 0.10
N_BINS = 10
N_DECILES = 10
ISOTONIC_MIN_TRAIN = 1000
CV_FOLDS = 5
PR_POINTS = 100


def _arrays(y: Any, p: Any) -> tuple[np.ndarray, np.ndarray]:
    y, p = np.asarray(y, dtype=int), np.asarray(p, dtype=float)
    if y.shape != p.shape or y.size == 0:
        raise ValueError("Outcomes and probabilities must be non-empty and the same length.")
    return y, p


def _ranked(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Outcomes ordered from the highest to the lowest score; ties keep row order."""
    return y[np.argsort(-p, kind="stable")]


def at_top(y: Any, p: Any, share: float = TOP_SHARE) -> dict[str, Any]:
    """Precision and recall among the top ceil(share * n) customers by score."""
    y, p = _arrays(y, p)
    k = math.ceil(share * len(y))
    hits = int(_ranked(y, p)[:k].sum())
    positives = int(y.sum())
    return {"share": share, "k": k, "churners_in_top": hits,
            "precision": hits / k, "recall": hits / positives if positives else None}


def deciles(y: Any, p: Any, n: int = N_DECILES) -> list[dict[str, Any]]:
    """Lift and cumulative gains by score decile (decile 1 = highest scores).
    Groups come from np.array_split, so earlier deciles take the extra rows."""
    y, p = _arrays(y, p)
    ranked = _ranked(y, p)
    overall = y.mean()
    positives = y.sum()
    rows, cum_churners, cum_n = [], 0, 0
    for i, part in enumerate(np.array_split(ranked, n), start=1):
        churners = int(part.sum())
        cum_churners += churners
        cum_n += len(part)
        rate = churners / len(part) if len(part) else None
        rows.append({
            "decile": i, "n": int(len(part)), "churners": churners, "churn_rate": rate,
            "lift": rate / overall if rate is not None and overall > 0 else None,
            # Share of all churners found by targeting deciles 1..i (cumulative gains).
            "cumulative_gain": cum_churners / positives if positives else None,
            "cumulative_share": cum_n / len(y),
        })
    return rows


def calibration(y: Any, p: Any, n_bins: int = N_BINS) -> list[dict[str, Any]]:
    """Uniform bins with counts; non-empty bins equal sklearn's calibration_curve."""
    y, p = _arrays(y, p)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ids = np.searchsorted(edges[1:-1], p)
    sums = np.bincount(ids, weights=p, minlength=n_bins)
    trues = np.bincount(ids, weights=y, minlength=n_bins)
    counts = np.bincount(ids, minlength=n_bins)
    return [{"bin": i + 1, "low": float(edges[i]), "high": float(edges[i + 1]),
             "n": int(counts[i]),
             "mean_predicted": float(sums[i] / counts[i]) if counts[i] else None,
             "observed_rate": float(trues[i] / counts[i]) if counts[i] else None}
            for i in range(n_bins)]


def pr_points(y: np.ndarray, p: np.ndarray) -> dict[str, list[float]]:
    precision, recall, _ = precision_recall_curve(y, p)
    if len(recall) > PR_POINTS:
        idx = np.unique(np.linspace(0, len(recall) - 1, PR_POINTS).round().astype(int))
        precision, recall = precision[idx], recall[idx]
    return {"recall": recall.tolist(), "precision": precision.tolist()}


def evaluate(y: Any, p: Any) -> dict[str, Any]:
    y, p = _arrays(y, p)
    both = len(np.unique(y)) == 2
    return jsonable({
        "n": int(len(y)),
        "churn_rate": float(y.mean()),
        "roc_auc": float(roc_auc_score(y, p)) if both else None,
        "pr_auc": float(average_precision_score(y, p)) if both else None,
        "brier": float(brier_score_loss(y, p)),
        "top_10pct": at_top(y, p),
        "deciles": deciles(y, p),
        "calibration": calibration(y, p),
        "roc_curve": roc_points(y, p) if both else None,
        "pr_curve": pr_points(y, p) if both else None,
    })


def calibrate(artifacts: ModelArtifacts, x_train: Any, y_train: Any
              ) -> tuple[CalibratedClassifierCV, str]:
    """Fit a calibrated copy of the chosen (unfitted) pipeline on the training split."""
    method = "isotonic" if len(y_train) >= ISOTONIC_MIN_TRAIN else "sigmoid"
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    model = CalibratedClassifierCV(clone(artifacts.pipeline), method=method, cv=cv)
    return model.fit(x_train, y_train), method


def model_metrics_v2(artifacts: ModelArtifacts, x: Any, y: Any
                     ) -> tuple[dict[str, Any], np.ndarray, CalibratedClassifierCV]:
    """(metrics for raw and calibrated scores on the test split, calibrated probabilities
    for every customer, the fitted calibrator). x / y are the full modelling frame."""
    train, test = artifacts.train_index, artifacts.test_index
    if np.intersect1d(train, test).size:
        raise ValueError("Training and test splits overlap.")
    y = np.asarray(y, dtype=int)
    calibrator, method = calibrate(artifacts, x.iloc[train], y[train])
    raw_test = artifacts.pipeline.predict_proba(x.iloc[test])[:, 1]
    calibrated_all = calibrator.predict_proba(x)[:, 1]
    raw = evaluate(y[test], raw_test)
    cal = evaluate(y[test], calibrated_all[test])
    metrics = jsonable({
        "split": "held-out test split (Phase 4, stratified 80/20, seed 42)",
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "raw": raw,
        "calibrated": cal,
        "calibration_method": method,
        "calibration_note": (
            f"CalibratedClassifierCV ({method}, {CV_FOLDS}-fold) fitted on the training split "
            "only; money metrics and risk bands use the calibrated probabilities."),
        "definitions": {
            "top_10pct": "The 10% of test customers with the highest scores (ties keep row "
                         "order): precision = share of them who churned, recall = share of "
                         "all churners they include.",
            "lift": "Churn rate in the decile divided by the overall churn rate.",
            "brier": "Mean squared gap between predicted probability and outcome (lower is "
                     "better).",
        },
    })
    return metrics, calibrated_all, calibrator
