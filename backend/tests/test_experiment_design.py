import math

import pytest
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

from app.stats.experiment_design import DesignError, detectable_effect, sample_size

TOL = 1e-9


def _statsmodels_n(p1: float, p2: float, alpha: float, power: float, ratio: float) -> float:
    h = abs(proportion_effectsize(p1, p2))
    return NormalIndPower().solve_power(effect_size=h, nobs1=None, alpha=alpha, power=power,
                                        ratio=ratio, alternative="two-sided")


def test_equal_split_matches_statsmodels():
    out = sample_size(0.26, 0.05)
    expected = _statsmodels_n(0.26, 0.21, 0.05, 0.8, 1.0)
    assert out["n_treatment"] == math.ceil(expected)
    assert out["n_control"] == math.ceil(expected)
    assert out["n_total"] == 2 * math.ceil(expected)
    assert abs(out["effect_size_h"] - abs(proportion_effectsize(0.26, 0.21))) < TOL
    assert abs(out["absolute_mde"] - 0.05) < TOL
    assert out["formula"].startswith("h =")


def test_unequal_split_uses_ratio():
    # 80% treatment / 20% control: control = 0.25 x treatment.
    out = sample_size(0.26, 0.05, control_share=0.2, alpha=0.1, power=0.9)
    expected = _statsmodels_n(0.26, 0.21, 0.1, 0.9, 0.25)
    assert out["n_treatment"] == math.ceil(expected)
    assert out["n_control"] == math.ceil(expected * 0.25)
    assert out["n_treatment"] > out["n_control"]
    # Unbalanced designs need more customers in total than a 50/50 split.
    assert out["n_total"] > sample_size(0.26, 0.05, alpha=0.1, power=0.9)["n_total"]


def test_relative_mde():
    out = sample_size(0.30, 0.2, mde_type="relative")
    assert abs(out["treatment_rate"] - 0.24) < TOL
    assert abs(out["relative_mde"] - 0.2) < TOL
    assert out["n_treatment"] == math.ceil(_statsmodels_n(0.30, 0.24, 0.05, 0.8, 1.0))


def test_segment_too_small_warns_with_detectable_effect():
    out = sample_size(0.26, 0.02, n_available=1000)
    assert out["feasible"] is False
    assert out["warnings"] and "Segment too small" in out["warnings"][0]
    det = out["detectable_with_available"]
    assert det is not None and det["absolute"] > 0.02
    # Designing for the detectable effect needs no more than the available customers.
    assert sample_size(0.26, det["absolute"])["n_total"] <= 1000 + 2


def test_detectable_effect_round_trips():
    det = detectable_effect(0.26, 5000, 0.05, 0.8, 0.5)
    assert det is not None
    h = abs(proportion_effectsize(0.26, det["treatment_rate"]))
    assert abs(h - det["effect_size_h"]) < TOL
    # 2,500 per arm has exactly the requested power at that effect (root-finder tolerance).
    achieved = NormalIndPower().power(effect_size=h, nobs1=2500, alpha=0.05, ratio=1.0)
    assert abs(achieved - 0.8) < 1e-5


def test_hopeless_segment():
    assert detectable_effect(0.26, 2, 0.05, 0.8, 0.5) is None
    out = sample_size(0.05, 0.01, n_available=10)
    assert out["feasible"] is False and "0% churn" in out["warnings"][0]


def test_feasible_segment_and_duration():
    out = sample_size(0.26, 0.05, n_available=100_000, monthly_volume=500)
    assert out["feasible"] is True and out["warnings"] == []
    assert abs(out["duration_months"] - out["n_total"] / 500) < TOL
    assert out["duration_days"] == math.ceil(out["n_total"] / 500 * 30.4375)


@pytest.mark.parametrize("kwargs", [
    {"baseline_rate": 0.26, "mde": 0},
    {"baseline_rate": 0.26, "mde": -0.01},
    {"baseline_rate": 0.26, "mde": 0.26},
    {"baseline_rate": 0.26, "mde": 1.0, "mde_type": "relative"},
    {"baseline_rate": 0.26, "mde": 0.05, "alpha": 0},
    {"baseline_rate": 0.26, "mde": 0.05, "alpha": 0.25},
    {"baseline_rate": 0.26, "mde": 0.05, "power": 1.0},
    {"baseline_rate": 0.26, "mde": 0.05, "power": 0.3},
    {"baseline_rate": 0.26, "mde": 0.05, "control_share": 0.99},
    {"baseline_rate": 0, "mde": 0.05},
    {"baseline_rate": 1.2, "mde": 0.05},
    {"baseline_rate": 0.26, "mde": 0.05, "mde_type": "percent"},
    {"baseline_rate": 0.26, "mde": 0.05, "n_available": -1},
    {"baseline_rate": 0.26, "mde": 0.05, "monthly_volume": 0},
])
def test_invalid_inputs_rejected(kwargs):
    with pytest.raises(DesignError):
        sample_size(**kwargs)
