import numpy as np
import pandas as pd
import pytest
from statsmodels.stats.proportion import (
    confint_proportions_2indep,
    proportion_confint,
    proportions_ztest,
)
from statsmodels.stats.weightstats import CompareMeans, DescrStatsW

from app.graph.paths import resolve
from app.stats import experiment_analysis as ea

TOL = 1e-9
DESIGN = {"control_share": 0.5, "alpha": 0.05, "power": 0.8, "baseline_rate": 0.26,
          "mde": 0.05, "mde_type": "absolute", "guardrail_metrics": ["complaints", "arpu"]}


def outcomes(n_t=3000, n_c=3000, p_t=0.21, p_c=0.26, accept=0.45, seed=42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    arm = np.array(["treatment"] * n_t + ["control"] * n_c)
    p = np.where(arm == "treatment", p_t, p_c)
    return pd.DataFrame({
        "customer_id": [f"c{i}" for i in range(n_t + n_c)],
        "arm": arm,
        "offer_accepted": np.where(arm == "treatment", rng.random(n_t + n_c) < accept, 0)
        .astype(int),
        "churned": (rng.random(n_t + n_c) < p).astype(int),
        "revenue": rng.normal(60, 15, n_t + n_c),
        "complaints": rng.poisson(0.1, n_t + n_c),
        "segments": [["Fiber"] if i % 3 == 0 else [] for i in range(n_t + n_c)],
    })


def test_wilson_matches_statsmodels():
    for x, n in [(0, 10), (7, 30), (260, 1000), (30, 30)]:
        low, high = proportion_confint(x, n, alpha=0.05, method="wilson")
        got = ea.wilson(x, n)
        assert abs(got[0] - low) < TOL and abs(got[1] - high) < TOL


def test_newcombe_textbook_examples():
    # Newcombe (1998), Statistics in Medicine 17:873-890, Table II, method 10.
    low, high = ea.newcombe(56, 70, 48, 80)
    assert round(low, 4) == 0.0524 and round(high, 4) == 0.3339
    low, high = ea.newcombe(9, 10, 3, 10)
    assert round(low, 4) == 0.1705 and round(high, 4) == 0.8090
    for args in [(56, 70, 48, 80), (9, 10, 3, 10), (630, 3000, 780, 3000)]:
        ref = confint_proportions_2indep(*args, method="newcomb", compare="diff")
        got = ea.newcombe(*args)
        assert abs(got[0] - ref[0]) < TOL and abs(got[1] - ref[1]) < TOL


def test_itt_matches_statsmodels_ztest():
    df = outcomes()
    t, c = df[df.arm == "treatment"].churned, df[df.arm == "control"].churned
    out = ea.compare_rates(t, c, 0.05)
    z, p = proportions_ztest([t.sum(), c.sum()], [len(t), len(c)])
    assert abs(out["z"] - z) < TOL and abs(out["p_value"] - p) < TOL
    assert abs(out["difference"]["value"] - (t.mean() - c.mean())) < TOL
    assert abs(out["relative_lift"] - (t.mean() - c.mean()) / c.mean()) < TOL


def test_srm_fires_on_60_40_planned_50_50():
    assert ea.srm_check(3600, 2400, 0.5)["failed"]
    assert not ea.srm_check(3010, 2990, 0.5)["failed"]
    assert not ea.srm_check(4800, 1200, 0.2)["failed"]  # 80/20 as planned


def test_full_analysis_finds_real_effect_and_ships():
    df = outcomes()
    result = ea.analyse(df, DESIGN, {"customer_value": 800.0, "offer_cost": 50.0},
                        segment_names=["Fiber"])
    itt = result["itt"]
    assert not result["srm"]["failed"]
    assert itt["difference"]["ci_low"] < -0.05 < itt["difference"]["ci_high"] < 0
    impact = result["impact"]
    n_t = itt["arms"]["treatment"]["n"]
    assert abs(impact["customers_saved"] - (-itt["difference"]["value"] * n_t)) < TOL
    acceptors = int(df[(df.arm == "treatment")].offer_accepted.sum())
    assert impact["acceptors"] == acceptors
    assert abs(impact["net_value"] - (impact["customers_saved"] * 800 - 50 * acceptors)) < 1e-6
    assert result["per_protocol"]["available"] and "biased" in result["per_protocol"]["label"]
    assert result["segments"]["items"]["Fiber"]["p_adjusted"] is not None
    assert result["decision_helper"]["verdict"] == "ship"
    assert 0 < itt["achieved_power"] <= 1
    # Numbers are addressable by source key for the validator.
    assert resolve(result, "itt.difference.value") == itt["difference"]["value"]
    assert resolve(result, "impact.net_value") == impact["net_value"]


def test_guardrail_ci_matches_statsmodels():
    df = outcomes()
    t, c = df[df.arm == "treatment"].revenue, df[df.arm == "control"].revenue
    g = ea.guardrail(t, c, 0.05, "down", 0.05)
    low, high = CompareMeans(DescrStatsW(t.to_numpy()), DescrStatsW(c.to_numpy())
                             ).zconfint_diff(alpha=0.05, usevar="unequal")
    assert abs(g["difference"]["ci_low"] - low) < TOL
    assert abs(g["difference"]["ci_high"] - high) < TOL
    assert not g["breached"]


def test_guardrail_breach_blocks_ship():
    df = outcomes()
    df.loc[df.arm == "treatment", "complaints"] += 1
    result = ea.analyse(df, DESIGN, {"customer_value": 800.0, "offer_cost": 50.0})
    assert result["guardrails"]["complaints"]["breached"]
    assert result["decision_helper"]["verdict"] == "inconclusive"
    assert "complaints" in result["decision_helper"]["guardrails_breached"]


def test_no_effect_is_inconclusive_with_extra_sample():
    df = outcomes(n_t=500, n_c=500, p_t=0.26, p_c=0.26)
    result = ea.analyse(df, DESIGN, {"customer_value": 800.0, "offer_cost": 50.0})
    helper = result["decision_helper"]
    assert helper["verdict"] in ("inconclusive", "dont_ship")
    if helper["verdict"] == "inconclusive":
        assert helper["extra_sample_needed"]["treatment"] > 0


def test_harmful_offer_is_dont_ship():
    df = outcomes(p_t=0.32, p_c=0.26)
    result = ea.analyse(df, DESIGN, {"customer_value": 800.0, "offer_cost": 50.0})
    assert result["decision_helper"]["verdict"] == "dont_ship"


def test_srm_blocks_ship():
    df = outcomes(n_t=3600, n_c=2400)
    result = ea.analyse(df, DESIGN, {"customer_value": 800.0, "offer_cost": 50.0})
    assert result["srm"]["failed"]
    assert result["decision_helper"]["verdict"] == "untrustworthy"


def test_unknown_costs_are_inconclusive():
    result = ea.analyse(outcomes(), DESIGN, {})
    assert result["impact"]["net_value"] is None
    assert result["decision_helper"]["verdict"] == "inconclusive"


def test_empty_arm_rejected():
    df = outcomes()
    with pytest.raises(ValueError):
        ea.analyse(df[df.arm == "treatment"], DESIGN, {})
