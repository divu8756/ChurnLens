"""Hypothesis tests must equal scipy/statsmodels within 1e-9 (CLAUDE.md rule 10)."""

import json

import numpy as np
import pandas as pd
import pytest
from scipy import stats
from statsmodels.stats.multitest import multipletests

from app.agents.analysis import hypothesis_node
from app.graph.state import ChurnState
from app.stats import hypothesis as h

TOL = dict(rel=1e-9, abs=1e-12)
SCHEMA = {"target_column": "churn", "positive_label": "1", "id_columns": ["id"],
          "time_column": None, "columns": []}


def frame(n=600, seed=11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    contract = rng.choice(["Monthly", "One year", "Two year"], n, p=[0.5, 0.3, 0.2])
    rate = np.select([contract == "Monthly", contract == "One year"], [0.45, 0.15], 0.05)
    churn = (rng.random(n) < rate).astype(int)
    return pd.DataFrame({
        "id": [f"c{i}" for i in range(n)],
        "contract": contract,
        "paperless": rng.choice(["Yes", "No"], n),
        "charges": rng.normal(60, 15, n) + churn * 8,            # normal groups -> Welch
        "tickets": rng.exponential(2, n).round() + churn * 2,     # skewed -> Mann-Whitney
        "constant": 5.0,
        "churn": churn,
    })


def get(result, variable):
    return next(t for t in result["tests"] if t["variable"] == variable)


# ---------------------------------------------------------------- chi-square


def test_chi_square_matches_scipy_for_3x2():
    df = frame()
    test = get(h.run_hypothesis_tests(df, SCHEMA), "contract")
    table = pd.crosstab(df.contract.astype("string"), df.churn)
    chi2, p, dof, expected = stats.chi2_contingency(table.to_numpy(), correction=False)
    assert test["test_name"] == "Chi-square test of independence"
    assert test["statistic"] == pytest.approx(chi2, **TOL)
    assert test["p_value"] == pytest.approx(p, **TOL)
    assert test["df"] == dof
    np.testing.assert_allclose(test["inputs"]["expected"]["values"], expected, rtol=1e-9)
    cells = (table.to_numpy() - expected) ** 2 / expected
    np.testing.assert_allclose(test["inputs"]["cell_contributions"]["values"], cells, rtol=1e-9)


def test_2x2_chi_square_has_no_yates_correction_explicitly():
    df = frame()
    test = get(h.run_hypothesis_tests(df, SCHEMA), "paperless")
    table = pd.crosstab(df.paperless.astype("string"), df.churn).to_numpy()
    no_yates = stats.chi2_contingency(table, correction=False)
    with_yates = stats.chi2_contingency(table)  # scipy default applies Yates to 2x2
    assert test["yates_correction"] is False
    assert test["statistic"] == pytest.approx(no_yates[0], **TOL)
    assert test["p_value"] == pytest.approx(no_yates[1], **TOL)
    assert test["statistic"] != pytest.approx(with_yates[0], rel=1e-6)


def test_cramers_v_hand_calculated():
    # [[10, 20], [30, 40]]: N=100, chi2 computed by hand
    table = np.array([[10, 20], [30, 40]])
    row, col, n = table.sum(1), table.sum(0), table.sum()
    expected = np.outer(row, col) / n
    chi2 = ((table - expected) ** 2 / expected).sum()
    assert h.cramers_v(chi2, n, (2, 2)) == pytest.approx(np.sqrt(chi2 / 100), **TOL)
    assert chi2 == pytest.approx(0.7936507936507936, **TOL)


def test_fisher_fallback_for_sparse_2x2():
    rng = np.random.default_rng(1)
    n = 150
    df = pd.DataFrame({"rare_flag": ["Yes"] * 6 + ["No"] * (n - 6),
                       "churn": [1, 1, 1, 0, 0, 0] + list((rng.random(n - 6) < 0.1).astype(int))})
    test = get(h.run_hypothesis_tests(df, {**SCHEMA, "id_columns": []}), "rare_flag")
    table = pd.crosstab(df.rare_flag.astype("string"), df.churn).to_numpy()
    odds, p = stats.fisher_exact(table)
    assert test["test_name"] == "Fisher's exact test"
    assert test["p_value"] == pytest.approx(p, **TOL)
    assert test["statistic"] == pytest.approx(odds, **TOL)


def test_rare_levels_merged_into_other():
    rng = np.random.default_rng(2)
    n = 300
    region = rng.choice(["North", "South"], n).astype(object)
    region[:3] = ["Island", "Moon", "Mars"]
    df = pd.DataFrame({"region": region, "churn": (rng.random(n) < 0.3).astype(int)})
    test = get(h.run_hypothesis_tests(df, {**SCHEMA, "id_columns": []}), "region")
    assert set(test["merged_levels"]) >= {"Island", "Moon", "Mars"}
    assert "Other" in test["inputs"]["observed"]["rows"]
    assert all(v >= 5 for row in test["inputs"]["expected"]["values"] for v in row)


# ---------------------------------------------------------------- numeric


def test_welch_matches_scipy_with_cohens_d():
    df = frame()
    test = get(h.run_hypothesis_tests(df, SCHEMA), "charges")
    a = df.loc[df.churn == 1, "charges"].to_numpy()
    b = df.loc[df.churn == 0, "charges"].to_numpy()
    ref = stats.ttest_ind(a, b, equal_var=False)
    assert test["test_name"] == "Welch's t-test"
    assert test["statistic"] == pytest.approx(ref.statistic, **TOL)
    assert test["p_value"] == pytest.approx(ref.pvalue, **TOL)
    assert test["df"] == pytest.approx(ref.df, **TOL)
    pooled = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1))
                     / (len(a) + len(b) - 2))
    assert test["effect_size"]["value"] == pytest.approx((a.mean() - b.mean()) / pooled, **TOL)


def test_cohens_d_hand_calculated():
    a, b = np.array([2.0, 4.0, 6.0]), np.array([1.0, 2.0, 3.0])
    # means 4 and 2; variances 4 and 1; pooled sd = sqrt((2*4 + 2*1)/4) = sqrt(2.5)
    assert h.cohens_d(a, b) == pytest.approx(2 / np.sqrt(2.5), **TOL)


def test_mann_whitney_matches_scipy():
    df = frame()
    test = get(h.run_hypothesis_tests(df, SCHEMA), "tickets")
    a = df.loc[df.churn == 1, "tickets"].to_numpy()
    b = df.loc[df.churn == 0, "tickets"].to_numpy()
    ref = stats.mannwhitneyu(a, b, alternative="two-sided")
    assert test["test_name"] == "Mann-Whitney U test"
    assert test["statistic"] == pytest.approx(ref.statistic, **TOL)
    assert test["p_value"] == pytest.approx(ref.pvalue, **TOL)
    assert test["effect_size"]["value"] == pytest.approx(
        2 * ref.statistic / (len(a) * len(b)) - 1, **TOL)
    assert test["effect_size"]["value"] > 0  # churned customers have more tickets


# ---------------------------------------------------------------- BH + output


def test_benjamini_hochberg_matches_statsmodels():
    result = h.run_hypothesis_tests(frame(), SCHEMA)
    raw = [t["p_value"] for t in result["tests"]]
    _, adjusted, _, _ = multipletests(raw, alpha=0.05, method="fdr_bh")
    np.testing.assert_allclose([t["p_adjusted"] for t in result["tests"]], adjusted,
                               rtol=1e-9, atol=1e-15)


def test_constant_column_skipped_not_crashed():
    result = h.run_hypothesis_tests(frame(), SCHEMA)
    assert {"variable": "constant", "reason": "constant column"} in result["skipped"]
    assert "id" not in [t["variable"] for t in result["tests"]]
    assert "churn" not in [t["variable"] for t in result["tests"]]


def test_categoricals_over_20_levels_skipped():
    df = frame()
    df["city"] = [f"c{i % 30}" for i in range(len(df))]
    result = h.run_hypothesis_tests(
        df, {**SCHEMA, "columns": [{"name": "city", "semantic_type": "categorical"}]})
    assert {"variable": "city", "reason": "more than 20 levels"} in result["skipped"]


def test_test_cap_at_40():
    rng = np.random.default_rng(3)
    df = pd.DataFrame({f"x{i}": rng.normal(size=200) for i in range(45)})
    df["churn"] = rng.integers(0, 2, 200)
    result = h.run_hypothesis_tests(df, {**SCHEMA, "id_columns": []})
    assert result["n_tests"] == 40
    assert sum("limit" in s["reason"] for s in result["skipped"]) == 5


def test_every_test_is_complete_and_json():
    result = h.run_hypothesis_tests(frame(), SCHEMA)
    json.dumps(result, allow_nan=False)
    for test in result["tests"]:
        for key in ("h0", "h1", "assumptions", "test_name", "why", "inputs", "steps",
                    "statistic", "p_value", "p_adjusted", "effect_size", "conclusion"):
            assert key in test, (test["variable"], key)
        assert all({"label", "formula", "substituted"} <= set(s) for s in test["steps"])
        assert test["effect_size"]["band"] in ("negligible", "small", "medium", "large")
    contract = get(result, "contract")
    assert contract["significant"] and contract["conclusion"].startswith("Significant")


def test_hypothesis_node(tmp_path):
    path = tmp_path / "clean.parquet"
    frame().to_parquet(path, index=False)
    update = hypothesis_node(ChurnState(session_id="s", clean_path=str(path),
                                        confirmed_schema=SCHEMA))
    assert update["hypothesis_results"]["n_tests"] == 4
