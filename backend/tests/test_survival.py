import json

import numpy as np
import pandas as pd
import pytest
from lifelines import KaplanMeierFitter
from lifelines.statistics import logrank_test, multivariate_logrank_test

from app.agents.analysis import survival_node
from app.graph.state import ChurnState
from app.stats import survival as sv

SCHEMA = {"target_column": "churn", "positive_label": "1", "id_columns": [],
          "time_column": "tenure", "columns": []}


def data(n=400, seed=5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    contract = rng.choice(["Monthly", "Annual"], n)
    # Monthly customers churn sooner.
    scale = np.where(contract == "Monthly", 12, 40)
    tenure = np.minimum(rng.exponential(scale).round(), 72)
    churn_prob = np.where(contract == "Monthly", 0.9, 0.4)
    churn = ((tenure < 72) & (rng.random(n) < churn_prob)).astype(int)
    return pd.DataFrame({
        "tenure": tenure, "churn": churn, "contract": contract,
        "region": rng.choice(["N", "S", "E"], n),
        "city": [f"c{i % 40}" for i in range(n)],  # > 6 levels: never picked
    })


def test_overall_km_matches_lifelines_exactly():
    df = data()
    result = sv.run_survival(df, SCHEMA)
    kmf = KaplanMeierFitter().fit(df["tenure"], df["churn"])
    expected = kmf.survival_function_.iloc[:, 0]
    curve = result["overall"]["curve"]
    assert curve["time"] == expected.index.tolist()
    np.testing.assert_allclose(curve["survival"], expected.to_numpy(), rtol=0, atol=1e-12)
    assert result["overall"]["median_survival"] == pytest.approx(kmf.median_survival_time_)
    assert result["overall"]["survival_at"]["12"] == pytest.approx(
        float(kmf.survival_function_at_times(12).iloc[0]), abs=1e-12)


def test_logrank_matches_lifelines():
    df = data()
    result = sv.run_survival(df, SCHEMA)
    group = next(g for g in result["by_group"] if g["column"] == "contract")
    direct = logrank_test(df.loc[df.contract == "Monthly", "tenure"],
                          df.loc[df.contract == "Annual", "tenure"],
                          df.loc[df.contract == "Monthly", "churn"],
                          df.loc[df.contract == "Annual", "churn"])
    assert group["logrank"]["p_value"] == pytest.approx(direct.p_value, rel=1e-9, abs=1e-300)
    assert group["logrank"]["statistic"] == pytest.approx(direct.test_statistic, rel=1e-9)
    three = multivariate_logrank_test(df["tenure"], df["region"], df["churn"])
    region = next(g for g in result["by_group"] if g["column"] == "region")
    assert region["logrank"]["p_value"] == pytest.approx(three.p_value, rel=1e-9)


def test_top_categoricals_ranked_and_level_limited():
    result = sv.run_survival(data(), SCHEMA)
    columns = [g["column"] for g in result["by_group"]]
    assert columns[0] == "contract" and "city" not in columns
    assert len(columns) <= 3


def test_median_not_reached():
    n = 200
    df = pd.DataFrame({"tenure": np.arange(n) % 50, "churn": [1] + [0] * (n - 1),
                       "contract": ["A", "B"] * (n // 2)})
    overall = sv.run_survival(df, SCHEMA)["overall"]
    assert overall["median_survival"] is None and overall["median_reached"] is False
    assert overall["survival_at"]["24"] > 0.9


def test_horizons_beyond_follow_up_are_null():
    df = data()
    df["tenure"] = df["tenure"].clip(upper=10)
    overall = sv.run_survival(df, SCHEMA)["overall"]
    assert overall["survival_at"]["12"] is None and overall["survival_at"]["24"] is None


def test_curves_are_downsampled_to_200_points():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"tenure": rng.random(2000) * 1000, "churn": rng.integers(0, 2, 2000),
                       "contract": rng.choice(["A", "B"], 2000)})
    result = sv.run_survival(df, SCHEMA)
    curve = result["overall"]["curve"]
    assert len(curve["time"]) <= 200
    assert curve["time"][0] == 0.0 and curve["time"][-1] == pytest.approx(df.tenure.max())


def test_skipped_without_time_column():
    result = sv.run_survival(data(), {**SCHEMA, "time_column": None})
    assert result["skipped"] is True


def test_negative_or_missing_durations_are_dropped():
    df = data()
    df.loc[:4, "tenure"] = np.nan
    df.loc[5, "tenure"] = -3
    result = sv.run_survival(df, SCHEMA)
    assert result["rows_dropped_no_duration"] == 6
    json.dumps(result, allow_nan=False)


def test_survival_node(tmp_path):
    path = tmp_path / "clean.parquet"
    data().to_parquet(path, index=False)
    update = survival_node(ChurnState(session_id="s", clean_path=str(path),
                                      confirmed_schema=SCHEMA, time_column="tenure"))
    assert update["survival_results"]["skipped"] is False
    assert update["progress"][0].status == "done"
