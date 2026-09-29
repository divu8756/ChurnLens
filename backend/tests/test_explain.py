import json
import warnings

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from scipy.stats import norm

from app.agents.modelling import modelling_node
from app.graph.state import ChurnState
from app.stats import explain as ex
from app.stats import modelling as m

SCHEMA = {"target_column": "churn", "positive_label": "1", "id_columns": ["id"],
          "time_column": None, "columns": []}


def data(n=800, seed=4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    x1 = rng.normal(50, 10, n)
    plan = rng.choice(["Basic", "Plus", "Pro"], n, p=[0.5, 0.3, 0.2])
    logit = 0.08 * (x1 - 50) + np.select([plan == "Pro", plan == "Plus"], [1.2, 0.4], 0) - 0.8
    churn = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return pd.DataFrame({"id": [f"c{i}" for i in range(n)], "x1": x1,
                         "noise": rng.normal(size=n), "plan": plan, "churn": churn})


@pytest.fixture(scope="module")
def trained():
    df = data()
    _, importance, artifacts = m.train_and_evaluate(df, SCHEMA)
    return df, importance, artifacts


# ---------------------------------------------------------------- SHAP


def test_one_hot_aggregation_sums_correctly():
    values = np.array([[1.0, 2.0, 3.0, 4.0], [0.5, -1.0, 0.25, 0.0]])
    owners = ["x1", "plan", "plan", "plan"]
    out = ex.aggregate_by_feature(values, owners, ["x1", "plan"])
    np.testing.assert_allclose(out, [[1.0, 9.0], [0.5, -0.75]])


def test_transformed_feature_map_matches_encoder(trained):
    _, _, artifacts = trained
    owners = ex.transformed_feature_map(artifacts.pipeline[0])
    names = artifacts.pipeline[0].get_feature_names_out()
    assert len(owners) == len(names)
    assert owners.count("plan") == 3 and owners.count("x1") == 1


def test_shap_explains_chosen_model_additively(trained):
    df, _, artifacts = trained
    x = df[artifacts.numeric + artifacts.categorical].iloc[artifacts.test_index[:50]]
    bg = df[artifacts.numeric + artifacts.categorical].iloc[artifacts.train_index[:100]]
    values, method = ex.shap_values(artifacts, x, bg)
    assert values.shape == (50, 3)
    if artifacts.model_key == "logistic_regression":
        # Linear SHAP is exact: base value + sum of contributions = model log-odds
        margin = artifacts.pipeline.decision_function(x)
        base = margin - values.sum(axis=1)
        assert np.ptp(base) < 1e-8
    else:
        assert method == "TreeExplainer"


def test_shap_summary_contents(trained):
    df, _, artifacts = trained
    summary = ex.shap_summary(artifacts, df)
    assert summary["explained_model"] == artifacts.model_key
    assert [g["feature"] for g in summary["global"]][0] in ("x1", "plan")
    assert {g["feature"] for g in summary["global"]} == {"x1", "noise", "plan"}
    assert summary["n_rows"] == len(artifacts.test_index)
    assert all(len(b["points"]) <= 200 for b in summary["beeswarm"])
    json.dumps(summary, allow_nan=False)


def test_tree_model_uses_tree_explainer():
    df = data()
    _, _, artifacts = m.train_and_evaluate(df, SCHEMA)
    models = m.candidate_models(artifacts.numeric, artifacts.categorical)
    gb = models["gradient_boosting"].fit(
        df[artifacts.numeric + artifacts.categorical].iloc[artifacts.train_index],
        df["churn"].iloc[artifacts.train_index])
    tree_artifacts = m.ModelArtifacts(gb, "gradient_boosting", artifacts.numeric,
                                      artifacts.categorical, artifacts.train_index,
                                      artifacts.test_index)
    summary = ex.shap_summary(tree_artifacts, df)
    assert summary["method"] == "TreeExplainer"


# ---------------------------------------------------------------- odds ratios


def test_odds_ratios_match_statsmodels_within_1e9(trained):
    df, _, artifacts = trained
    result = ex.odds_ratios(artifacts, df, "churn")
    train = df.iloc[artifacts.train_index]
    # Rebuild the same design by hand.
    x = pd.DataFrame(index=train.index)
    for col in ("x1", "noise"):
        v = train[col].fillna(train[col].median())
        x[col] = (v - v.mean()) / v.std(ddof=0)
    reference = train["plan"].value_counts().index[0]
    for level in sorted(set(train["plan"]) - {reference}):
        x[f"plan = {level}"] = (train["plan"] == level).astype(float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ref = sm.Logit(train["churn"].to_numpy(), sm.add_constant(x)).fit(disp=0, maxiter=200)
    z = norm.ppf(0.975)
    for row in result["terms"]:
        coef, se = ref.params[row["term"]], ref.bse[row["term"]]
        assert row["odds_ratio"] == pytest.approx(np.exp(coef), rel=1e-9)
        assert row["ci_lower"] == pytest.approx(np.exp(coef - z * se), rel=1e-9)
        assert row["ci_upper"] == pytest.approx(np.exp(coef + z * se), rel=1e-9)
    labels = {r["term"]: r["label"] for r in result["terms"]}
    assert labels["x1"] == "x1 (per 1 SD)"
    assert labels["plan = Pro"] == f"plan: Pro vs {reference}"


def test_perfect_separation_drops_term_without_crashing():
    df = data()
    df["giveaway"] = np.where(df["churn"] == 1, "gone", "stay")
    df.loc[df.index[:3], "giveaway"] = "unknown"
    _, _, artifacts = m.train_and_evaluate(df.drop(columns="giveaway"), SCHEMA)
    artifacts.categorical.append("giveaway")
    result = ex.odds_ratios(artifacts, df, "churn")
    assert any("separation" in d["reason"] or "fitted" in d["reason"] for d in result["dropped"])
    assert result["terms"], "other terms still reported"


def test_singular_design_drops_duplicate_column(trained):
    df, _, artifacts = trained
    df = df.copy()
    df["x1_copy"] = df["x1"] * 2
    artifacts.numeric.append("x1_copy")
    try:
        result = ex.odds_ratios(artifacts, df, "churn")
    finally:
        artifacts.numeric.remove("x1_copy")
    assert {"term": "x1_copy",
            "reason": "linearly dependent on other terms (singular design)"} in result["dropped"]


# ---------------------------------------------------------------- driver impact + node


def test_driver_impact_joins_all_sources(trained):
    df, importance, artifacts = trained
    shap_result = ex.shap_summary(artifacts, df)
    odds = ex.odds_ratios(artifacts, df, "churn")
    hypothesis = {"tests": [{"variable": "plan", "test_name": "Chi-square test of independence",
                             "p_adjusted": 0.001, "significant": True}]}
    rows = ex.driver_impact(importance, shap_result, odds, hypothesis)
    plan = next(r for r in rows if r["feature"] == "plan")
    assert plan["p_adjusted"] == 0.001 and plan["odds_ratio"] is not None
    assert plan["mean_abs_shap"] is not None
    assert [r["permutation_rank"] for r in rows] == sorted(r["permutation_rank"] for r in rows)


def test_modelling_node_writes_explanations(tmp_path):
    path = tmp_path / "clean.parquet"
    data().to_parquet(path, index=False)
    update = modelling_node(ChurnState(session_id="s", clean_path=str(path),
                                       confirmed_schema=SCHEMA))
    assert update["shap_summary"]["global"] and update["odds_ratios"]["terms"]
    assert update["feature_importance"]["driver_impact"]
    assert update["errors"] == []
