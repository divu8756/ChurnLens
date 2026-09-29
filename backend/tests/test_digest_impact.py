import json

import numpy as np
import pandas as pd
import pytest
from pipeline import telco_state

from app.graph import paths
from app.graph.results_digest import TOKEN_BUDGET, build_digest, digest_keys, estimate_tokens
from app.stats.impact import run_impact

# ---------------------------------------------------------------- paths


def test_resolve_dicts_lists_and_dotted_keys():
    data = {"a": {"b": [10, {"c": 3}]}, "x": {"Rev.Q1": {"n": 5}, "Rev": {"Q1": {"n": 9}}}}
    assert paths.resolve(data, "a.b.0") == 10
    assert paths.resolve(data, "a.b.1.c") == 3
    assert paths.resolve(data, "x.Rev.Q1.n") == 5  # longest key wins
    with pytest.raises(paths.PathNotFound):
        paths.resolve(data, "a.b.7")
    with pytest.raises(paths.PathNotFound):
        paths.resolve(data, "a.zzz")
    assert paths.exists(data, "a.b") and not paths.exists(data, "nope")


# ---------------------------------------------------------------- impact


def tiny() -> tuple[pd.DataFrame, dict]:
    # plan A: 40 customers, 20 churn, revenue 10 each; plan B: 60 customers, 6 churn, revenue 5
    df = pd.DataFrame({
        "plan": ["A"] * 40 + ["B"] * 60,
        "revenue": [10.0] * 40 + [5.0] * 60,
        "churn": [1] * 20 + [0] * 20 + [1] * 6 + [0] * 54,
    })
    schema = {"target_column": "churn", "revenue_column": "revenue", "id_columns": []}
    hypothesis = {"tests": [{"variable": "plan", "kind": "categorical", "significant": True,
                             "merged_levels": []}]}
    return df, schema, hypothesis


def test_impact_maths_by_hand():
    df, schema, hypothesis = tiny()
    result = run_impact(df, schema, None, None, hypothesis)
    overall = result["overall"]
    assert overall["customers"] == 100 and overall["churners"] == 26
    assert overall["churn_rate"] == pytest.approx(0.26)
    assert overall["monthly_revenue_at_risk"] == 20 * 10 + 6 * 5

    a = result["items"]["plan=A"]
    assert a["customers"] == 40 and a["churners"] == 20 and a["churn_rate"] == 0.5
    assert a["lift_vs_overall"] == pytest.approx(0.5 / 0.26)
    assert a["monthly_revenue_at_risk"] == 200.0
    assert a["scenarios"]["reduce_10pct"]["churners_saved"] == 2.0
    assert a["scenarios"]["reduce_25pct"]["churners_saved"] == 5.0
    assert a["scenarios"]["reduce_25pct"]["monthly_revenue_saved"] == 50.0
    assert "not a causal estimate" in a["scenarios"]["reduce_10pct"]["assumption"]
    assert "plan=B" not in result["items"]  # churn rate below overall


def test_impact_without_revenue_column():
    df, schema, hypothesis = tiny()
    result = run_impact(df, {**schema, "revenue_column": None}, None, None, hypothesis)
    assert result["items"]["plan=A"]["monthly_revenue_at_risk"] is None
    assert "No revenue column" in result["revenue_note"]


def test_impact_segments_use_assignments():
    df, schema, _ = tiny()
    labels = np.array([0] * 40 + [1] * 60)
    segments = {"skipped": False, "segments": [{"segment": 0, "label": "High revenue"},
                                               {"segment": 1, "label": "Low revenue"}]}
    result = run_impact(df, schema, segments, labels, None)
    assert result["items"]["segment_0"]["churners"] == 20
    assert result["items"]["segment_1"]["customers"] == 60


# ---------------------------------------------------------------- digest on Telco


def test_digest_under_budget_and_every_key_resolves():
    state = telco_state()
    digest = build_digest(state)
    assert estimate_tokens(digest) < TOKEN_BUDGET
    keys = digest_keys(digest)
    assert len(keys) > 100
    for section in digest["sections"].values():
        for fact in section:
            value = paths.resolve(state, fact["key"])
            if isinstance(value, float):
                assert fact["value"] == pytest.approx(value, rel=1e-3)
            else:
                assert fact["value"] == value


def test_digest_contains_no_raw_rows():
    state = telco_state()
    text = json.dumps(build_digest(state))
    assert "7590-" not in text and "customerID" not in text  # no ids
    assert "8944-YQZDP" not in text


def test_telco_impact_estimates():
    impact = telco_state()["impact_estimates"]
    assert impact["revenue_column"] == "MonthlyCharges"
    first = impact["items"][impact["item_order"][0]]
    assert first["id"] == "Contract=Month-to-month"
    assert first["scenarios"]["reduce_10pct"]["churners_saved"] == pytest.approx(
        first["churners"] * 0.1, abs=0.05)
