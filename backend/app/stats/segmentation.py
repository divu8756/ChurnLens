"""Customer segmentation with K-means (docs/SPEC.md node 6).

Numeric features (not ids, target or time column) are median-imputed and
standard-scaled; k in 2..8 is chosen by silhouette score. Segments are
labelled by their two most distinctive features.
"""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.stats.common import feature_columns, jsonable

RANDOM_STATE = 42
K_RANGE = range(2, 9)
N_INIT = 10
# Silhouette needs an n x n distance matrix: 2,000 rows is 32 MB (5,000 was 200 MB).
SILHOUETTE_SAMPLE = 2000
MIN_FEATURES = 2


def segment_features(frame: pd.DataFrame, schema: dict[str, Any]) -> list[str]:
    time_col = schema.get("time_column")
    return [c for c in feature_columns(frame, schema)["numeric"]
            if c != time_col and frame[c].notna().any() and frame[c].nunique() > 1]


def _label(z: pd.Series) -> str:
    top = z.abs().sort_values(ascending=False).index[:2]
    parts = [f"{'High' if z[c] > 0 else 'Low'} {c}" for c in top]
    return ", ".join(parts) if parts else "Average"


def run_segmentation(
    frame: pd.DataFrame, schema: dict[str, Any]
) -> tuple[dict[str, Any], np.ndarray | None]:
    """Returns (JSON result, per-row segment labels or None when skipped)."""
    target = schema["target_column"]
    features = segment_features(frame, schema)
    if len(features) < MIN_FEATURES:
        return {"skipped": True,
                "reason": f"Segmentation needs at least {MIN_FEATURES} numeric features "
                          f"(found {len(features)}).",
                "features": features}, None
    n = len(frame)
    prep = make_pipeline(SimpleImputer(strategy="median"), StandardScaler())
    x = prep.fit_transform(frame[features])

    rng = np.random.default_rng(RANDOM_STATE)
    sample = rng.choice(n, size=SILHOUETTE_SAMPLE, replace=False) if n > SILHOUETTE_SAMPLE \
        else np.arange(n)
    scores: dict[int, float] = {}
    models: dict[int, KMeans] = {}
    for k in K_RANGE:
        if k >= n:
            break
        model = KMeans(n_clusters=k, n_init=N_INIT, random_state=RANDOM_STATE).fit(x)
        labels = model.labels_
        if len(np.unique(labels[sample])) < 2:
            continue
        scores[k] = float(silhouette_score(x[sample], labels[sample],
                                           random_state=RANDOM_STATE))
        models[k] = model
    if not scores:
        return {"skipped": True, "reason": "Clustering found no separable groups.",
                "features": features}, None
    best_k = max(scores, key=lambda k: (scores[k], -k))
    labels = models[best_k].labels_

    y = frame[target].astype(int).to_numpy()
    imputed = pd.DataFrame(prep[0].transform(frame[features]), columns=features)
    overall_mean = imputed.mean()
    overall_std = imputed.std(ddof=0).replace(0, np.nan)
    overall_rate = float(y.mean())

    segments = []
    for seg in range(best_k):
        mask = labels == seg
        means = imputed[mask].mean()
        z = ((means - overall_mean) / overall_std).fillna(0.0)
        segments.append({
            "segment": seg,
            "label": _label(z),
            "size": int(mask.sum()),
            "pct_of_base": float(mask.mean()),
            "churn_rate": float(y[mask].mean()),
            "churn_lift": float(y[mask].mean() / overall_rate) if overall_rate else None,
            "feature_means": {c: float(means[c]) for c in features},
            "feature_z": {c: float(z[c]) for c in features},
        })
    segments.sort(key=lambda s: -s["churn_rate"])
    return jsonable({
        "skipped": False,
        "k": best_k,
        "silhouette_by_k": scores,
        "features": features,
        "overall_means": {c: float(overall_mean[c]) for c in features},
        "overall_churn_rate": overall_rate,
        "segments": segments,
    }), labels
