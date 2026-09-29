"""Model explanations: SHAP, odds ratios and the driver impact table (runbook T4.2).

- SHAP explains the CHOSEN model (the one that scores customers), on the
  transformed test matrix (<= 2,000 rows). TreeExplainer for tree models;
  otherwise shap.Explainer with a 100-row background (linear models get the
  exact linear explainer). One-hot columns are summed back to their
  original feature; SHAP values are additive, so the sum is the feature's
  contribution.
- Odds ratios come from a statsmodels Logit on the TRAINING split: numerics
  median-imputed and standardised (OR is "per 1 SD"), categoricals one-hot
  with drop-first where the dropped reference is the most frequent level
  (OR is "vs <reference>"). Perfect separation and singular designs drop the
  offending term with a warning, never crash.
"""

import warnings
from typing import Any

import numpy as np
import pandas as pd
import shap
import statsmodels.api as sm
from sklearn.compose import ColumnTransformer

from app.stats.common import jsonable
from app.stats.modelling import ModelArtifacts

RANDOM_STATE = 42
SHAP_MAX_ROWS = 2000
SHAP_BACKGROUND = 100
BEESWARM_FEATURES = 10
BEESWARM_POINTS = 200
MAX_ABS_COEF = 15.0
MAX_REFITS = 10


# ---------------------------------------------------------------- SHAP


def transformed_feature_map(prep: ColumnTransformer) -> list[str]:
    """Original feature name for every column of the transformed matrix."""
    owners: list[str] = []
    for name, transformer, columns in prep.transformers_:
        if name == "num":
            owners.extend(columns)
        elif name == "cat":
            encoder = transformer[-1]
            for col, cats in zip(columns, encoder.categories_, strict=True):
                owners.extend([col] * len(cats))
    return owners


def aggregate_by_feature(values: np.ndarray, owners: list[str],
                         features: list[str]) -> np.ndarray:
    """Sum SHAP columns that belong to the same original feature."""
    out = np.zeros((values.shape[0], len(features)))
    index = {f: i for i, f in enumerate(features)}
    for col, owner in enumerate(owners):
        out[:, index[owner]] += values[:, col]
    return out


def shap_values(artifacts: ModelArtifacts, x: pd.DataFrame,
                background: pd.DataFrame) -> tuple[np.ndarray, str]:
    """Per-row SHAP values by ORIGINAL feature (log-odds scale) and the method used."""
    prep, model = artifacts.pipeline[0], artifacts.pipeline[-1]
    features = artifacts.numeric + artifacts.categorical
    xt = np.asarray(prep.transform(x), dtype=float)
    try:
        explainer = shap.TreeExplainer(model)
        raw = explainer.shap_values(xt)
        method = "TreeExplainer"
    except Exception:  # not a tree model: generic explainer with a small background
        bt = np.asarray(prep.transform(background), dtype=float)
        explainer = shap.Explainer(model, bt)
        raw = explainer(xt).values
        method = f"{type(explainer).__name__} ({len(bt)}-row background)"
    raw = np.asarray(raw)
    if raw.ndim == 3:  # (rows, columns, classes): keep the churn class
        raw = raw[:, :, 1]
    return aggregate_by_feature(raw, transformed_feature_map(prep), features), method


def shap_summary(artifacts: ModelArtifacts, frame: pd.DataFrame) -> dict[str, Any]:
    features = artifacts.numeric + artifacts.categorical
    rng = np.random.default_rng(RANDOM_STATE)
    test_idx = artifacts.test_index
    if len(test_idx) > SHAP_MAX_ROWS:
        test_idx = np.sort(rng.choice(test_idx, SHAP_MAX_ROWS, replace=False))
    bg_idx = rng.choice(artifacts.train_index, min(SHAP_BACKGROUND, len(artifacts.train_index)),
                        replace=False)
    x = frame[features].iloc[test_idx]
    values, method = shap_values(artifacts, x, frame[features].iloc[bg_idx])

    mean_abs = np.abs(values).mean(axis=0)
    order = np.argsort(-mean_abs)
    global_importance = [{"feature": features[i], "mean_abs_shap": float(mean_abs[i])}
                         for i in order]
    beeswarm = []
    for i in order[:BEESWARM_FEATURES]:
        col = features[i]
        pick = np.arange(len(x))
        if len(pick) > BEESWARM_POINTS:
            pick = np.sort(rng.choice(pick, BEESWARM_POINTS, replace=False))
        raw_values = x[col].iloc[pick]
        beeswarm.append({
            "feature": col,
            "kind": "numeric" if col in artifacts.numeric else "categorical",
            "points": [{"shap": float(values[p, i]),
                        "value": (None if pd.isna(v) else (float(v) if col in artifacts.numeric
                                                           else str(v)))}
                       for p, v in zip(pick, raw_values, strict=True)],
        })
    return jsonable({
        "method": method,
        "explained_model": artifacts.model_key,
        "scale": "log-odds (positive pushes towards churn)",
        "n_rows": int(len(x)),
        "global": global_importance,
        "beeswarm": beeswarm,
    })


# ---------------------------------------------------------------- odds ratios


def _design(frame: pd.DataFrame, numeric: list[str], categorical: list[str],
            train_idx: np.ndarray) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    train = frame.iloc[train_idx]
    parts, terms = [], {}
    for col in numeric:
        values = train[col].astype(float)
        filled = values.fillna(values.median())
        sd = filled.std(ddof=0)
        if not sd or np.isnan(sd):
            continue
        parts.append(((filled - filled.mean()) / sd).rename(col))
        terms[col] = {"feature": col, "kind": "numeric", "label": f"{col} (per 1 SD)",
                      "sd": float(sd)}
    for col in categorical:
        values = train[col].astype("string").fillna("Missing")
        reference = values.value_counts().index[0]
        for level in sorted(set(values) - {reference}, key=str):
            name = f"{col} = {level}"
            parts.append((values == level).astype(float).rename(name))
            terms[name] = {"feature": col, "kind": "categorical", "level": str(level),
                           "reference": str(reference),
                           "label": f"{col}: {level} vs {reference}"}
    design = pd.concat(parts, axis=1) if parts else pd.DataFrame(index=train.index)
    return design, terms


def _drop_dependent_columns(design: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    kept: list[str] = []
    dropped: list[str] = []
    base = np.ones((len(design), 1))
    for col in design.columns:
        candidate = np.column_stack([base, design[kept + [col]].to_numpy()]) if kept else \
            np.column_stack([base, design[[col]].to_numpy()])
        if np.linalg.matrix_rank(candidate) == candidate.shape[1]:
            kept.append(col)
        else:
            dropped.append(col)
    return design[kept], dropped


def odds_ratios(artifacts: ModelArtifacts, frame: pd.DataFrame,
                target: str) -> dict[str, Any]:
    design, terms = _design(frame, artifacts.numeric, artifacts.categorical,
                            artifacts.train_index)
    y = frame[target].astype(int).iloc[artifacts.train_index].to_numpy()
    design, dependent = _drop_dependent_columns(design)
    notes = [{"term": t, "reason": "linearly dependent on other terms (singular design)"}
             for t in dependent]

    result = None
    for _ in range(MAX_REFITS):
        x = sm.add_constant(design, has_constant="add")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fitted = sm.Logit(y, x).fit(disp=0, maxiter=200)
        except (np.linalg.LinAlgError, ValueError) as exc:
            worst = design.var().idxmin()
            notes.append({"term": worst, "reason": f"model could not be fitted: {exc}"})
            design = design.drop(columns=worst)
            continue
        params, bse = fitted.params.drop("const"), fitted.bse.drop("const")
        bad = params[(params.abs() > MAX_ABS_COEF) | bse.isna() | ~np.isfinite(bse)]
        if len(bad):
            worst = bad.abs().idxmax()
            notes.append({"term": worst,
                          "reason": "perfect or quasi-perfect separation (coefficient diverges)"})
            design = design.drop(columns=worst)
            continue
        result = fitted
        break

    if result is None:
        return jsonable({"terms": [], "dropped": notes,
                         "error": "The logistic regression for odds ratios did not converge."})

    ci = result.conf_int(alpha=0.05)
    rows = []
    for term in design.columns:
        coef, se = float(result.params[term]), float(result.bse[term])
        rows.append({**terms[term], "term": term, "coef": coef, "se": se,
                     "odds_ratio": float(np.exp(coef)),
                     "ci_lower": float(np.exp(ci.loc[term, 0])),
                     "ci_upper": float(np.exp(ci.loc[term, 1])),
                     "p_value": float(result.pvalues[term])})
    rows.sort(key=lambda r: -abs(r["coef"]))
    return jsonable({
        "method": "statsmodels Logit on the training split; numerics standardised (per 1 SD), "
                  "categoricals vs their most frequent level; 95% Wald CI.",
        "n": int(len(y)),
        "converged": bool(result.mle_retvals.get("converged", True)),
        "pseudo_r2": float(result.prsquared),
        "terms": rows,
        "dropped": notes,
    })


# ---------------------------------------------------------------- driver impact


def driver_impact(importance: dict[str, Any], shap_result: dict[str, Any],
                  odds: dict[str, Any], hypothesis: dict[str, Any] | None) -> list[dict[str, Any]]:
    shap_by = {g["feature"]: g["mean_abs_shap"] for g in shap_result.get("global", [])}
    tests = {t["variable"]: t for t in (hypothesis or {}).get("tests", [])}
    strongest: dict[str, dict[str, Any]] = {}
    for term in odds.get("terms", []):
        current = strongest.get(term["feature"])
        if current is None or abs(term["coef"]) > abs(current["coef"]):
            strongest[term["feature"]] = term
    rows = []
    for item in importance["features"]:
        feature = item["feature"]
        term = strongest.get(feature)
        test = tests.get(feature)
        rows.append({
            "feature": feature,
            "permutation_rank": item["rank"],
            "permutation_importance": item["importance_mean"],
            "mean_abs_shap": shap_by.get(feature),
            "odds_ratio": term["odds_ratio"] if term else None,
            "or_ci_lower": term["ci_lower"] if term else None,
            "or_ci_upper": term["ci_upper"] if term else None,
            "or_label": term["label"] if term else None,
            "test_name": test["test_name"] if test else None,
            "p_adjusted": test["p_adjusted"] if test else None,
            "significant": test["significant"] if test else None,
        })
    return jsonable(rows)
