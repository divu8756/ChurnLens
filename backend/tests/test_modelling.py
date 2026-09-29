import json
from functools import lru_cache

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

from app.agents.modelling import modelling_node
from app.config import BACKEND_DIR
from app.graph.errors import FatalNodeError
from app.graph.state import ChurnState
from app.stats import cleaning, profiling
from app.stats import modelling as m

TELCO = BACKEND_DIR / "sample_data" / "telco_churn.csv"
TREATMENTS = ["CampaignGroup", "OfferShown", "OfferChannel", "OfferDate", "OfferClicked",
              "OfferAccepted", "OfferCost"]


@lru_cache
def telco() -> tuple[pd.DataFrame, dict]:
    raw = pd.read_csv(TELCO)
    heur = profiling.heuristic_schema(raw)
    schema = {**heur, "columns": [{"name": c["name"], "semantic_type": c["semantic_type"]}
                                  for c in heur["columns"]]}
    return cleaning.clean(raw, schema, 100).frame, schema


@lru_cache
def telco_model():
    frame, schema = telco()
    return m.train_and_evaluate(frame, schema, exclude=TREATMENTS)


def small(n=600, seed=0) -> tuple[pd.DataFrame, dict]:
    rng = np.random.default_rng(seed)
    x1 = rng.normal(size=n)
    plan = rng.choice(["A", "B", "C"], n)
    logit = 1.2 * x1 + np.where(plan == "A", 1.0, -0.5)
    churn = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    df = pd.DataFrame({"id": [f"c{i}" for i in range(n)], "x1": x1,
                       "noise": rng.normal(size=n), "plan": plan, "churn": churn})
    schema = {"target_column": "churn", "positive_label": "1", "id_columns": ["id"],
              "time_column": None, "columns": []}
    return df, schema


def test_telco_reaches_roc_auc_080():
    metrics, importance, artifacts = telco_model()
    assert metrics["test"]["roc_auc"] >= 0.80
    assert metrics["n_test"] == 1400 and metrics["n_train"] == 5600
    assert set(metrics["cv"]) == {"logistic_regression", "gradient_boosting"}
    assert metrics["chosen_model"] == max(metrics["cv"],
                                          key=lambda k: metrics["cv"][k]["pr_auc_mean"])
    assert not set(TREATMENTS) & set(metrics["features"]["numeric"]
                                     + metrics["features"]["categorical"])
    assert "customerID" not in metrics["features"]["categorical"]


def test_importance_uses_original_column_names():
    metrics, importance, _ = telco_model()
    names = [row["feature"] for row in importance["features"]]
    assert set(names) == set(metrics["features"]["numeric"] + metrics["features"]["categorical"])
    assert "Contract" in names and not any("_" in n and n.startswith("Contract_") for n in names)
    assert [row["rank"] for row in importance["features"]] == list(range(1, len(names) + 1))


def test_metrics_are_consistent_with_the_saved_model():
    frame, schema = telco()
    metrics, _, artifacts = telco_model()
    x = frame[artifacts.numeric + artifacts.categorical].iloc[artifacts.test_index]
    y = frame[schema["target_column"]].iloc[artifacts.test_index]
    proba = artifacts.pipeline.predict_proba(x)[:, 1]
    assert metrics["test"]["roc_auc"] == pytest.approx(roc_auc_score(y, proba), abs=1e-12)
    cm = metrics["test"]["confusion_matrix"]
    assert cm["tp"] + cm["fn"] == int(y.sum()) and sum(cm.values()) == len(y)
    json.dumps(metrics, allow_nan=False)


def test_split_is_stratified_and_disjoint():
    metrics, _, artifacts = telco_model()
    assert not set(artifacts.train_index) & set(artifacts.test_index)
    assert metrics["train_churn_rate"] == pytest.approx(metrics["test_churn_rate"], abs=0.01)


def test_planted_leaky_column_trips_the_guard():
    df, schema = small()
    df["churn_date_known"] = df["churn"] * 10 + np.random.default_rng(1).normal(0, 0.01, len(df))
    with pytest.raises(m.LeakageError, match="too good to be true"):
        m.train_and_evaluate(df, schema)


def test_high_correlation_is_a_warning():
    df, _ = small(seed=2)
    rng = np.random.default_rng(3)
    df["proxy"] = df["churn"] + rng.normal(0, 0.1, len(df))
    df["level"] = np.where(df["churn"] == 1, "gone", "here")
    warnings = m.leakage_warnings(df, df["churn"], ["x1", "proxy"], ["plan", "level"])
    flagged = {w["column"]: w["measure"] for w in warnings}
    assert flagged == {"proxy": "Pearson r", "level": "Cramér's V"}
    assert abs(df["proxy"].corr(df["churn"])) > 0.9


def test_results_identical_across_runs():
    df, schema = small()
    first = m.train_and_evaluate(df, schema)[:2]
    second = m.train_and_evaluate(df, schema)[:2]
    assert first == second


def test_modelling_node_saves_model_and_routes_leakage(tmp_path):
    df, schema = small()
    path = tmp_path / "clean.parquet"
    df.to_parquet(path, index=False)
    update = modelling_node(ChurnState(session_id="s", clean_path=str(path),
                                       confirmed_schema=schema))
    loaded = m.load_artifacts(update["model_metrics"]["model_path"])
    assert loaded.model_key == update["model_metrics"]["chosen_model"]

    df["leak"] = df["churn"]
    df.to_parquet(path, index=False)
    with pytest.raises(FatalNodeError, match="too good to be true"):
        modelling_node(ChurnState(session_id="s", clean_path=str(path), confirmed_schema=schema))
