import math

import numpy as np
import pytest
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

from app.stats.business_metrics import ab_plan
from app.stats.experiment_design import sample_size_two_proportions


def test_textbook_reference_903_per_arm():
    out = sample_size_two_proportions(0.20, 0.25)
    assert out["p2"] == pytest.approx(0.15)
    assert out["n_unrounded"] == pytest.approx(902.34, abs=0.01)
    assert out["n_per_arm"] == 903 and out["total_n"] == 1806
    assert out["z_alpha"] == pytest.approx(1.959964, abs=1e-6)
    assert out["z_beta"] == pytest.approx(0.841621, abs=1e-6)
    assert out["cohens_h"] == pytest.approx(abs(proportion_effectsize(0.2, 0.15)), abs=1e-12)
    assert out["formula_latex"].startswith("n =")


def test_second_reference_1038_per_arm():
    assert sample_size_two_proportions(0.26, 0.20)["n_per_arm"] == 1038


def test_unequal_ratio_matches_statsmodels():
    out = sample_size_two_proportions(0.26, 0.2, ratio=0.25)
    h = abs(proportion_effectsize(0.26, 0.26 * 0.8))
    n1 = NormalIndPower().solve_power(h, alpha=0.05, power=0.8, ratio=0.25)
    assert out["n_per_arm"] == math.ceil(n1)
    assert out["n_second_arm"] == math.ceil(n1 * 0.25)


@pytest.mark.parametrize("kwargs", [
    {"p1": 0.2, "relative_lift": 0}, {"p1": 0.2, "relative_lift": 1},
    {"p1": 0.2, "relative_lift": -0.1}, {"p1": 0, "relative_lift": 0.2},
    {"p1": 1.2, "relative_lift": 0.2}, {"p1": 0.2, "relative_lift": 0.2, "power": 0},
    {"p1": 0.2, "relative_lift": 0.2, "power": 1},
])
def test_bad_inputs_raise_clear_errors(kwargs):
    with pytest.raises(ValueError):
        sample_size_two_proportions(**kwargs)


def test_ab_plan_uses_observed_churn_and_warns_when_too_small():
    y = np.array([1] * 26 + [0] * 74)
    plan = ab_plan(y, "month-to-month customers")
    assert plan["available"] and plan["p1"] == pytest.approx(0.26)
    assert plan["n_per_arm"] == 1038
    assert plan["warnings"] and "100 customers" in plan["warnings"][0]
    sources = {a["name"]: a["source"] for a in plan["assumptions"]}
    assert sources == {"p1": "data", "relative_lift": "default", "alpha": "default",
                       "power": "default"}
    big = ab_plan(np.tile(y, 30), "everyone", relative_lift=0.2, power=0.8)
    assert big["warnings"] == []
    assert {a["name"]: a["source"] for a in big["assumptions"]}["power"] == "user"


def test_ab_plan_degenerate_segments():
    assert ab_plan([], "nobody")["available"] is False
    assert ab_plan([0, 0, 0], "no churn")["available"] is False
