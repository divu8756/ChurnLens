"""A/B test design for a churn-reduction offer: sample size per arm, the smallest
effect the available customers can detect, and the expected duration.

Two-proportion test on Cohen's h (statsmodels proportion_effectsize +
NormalIndPower.solve_power with the ratio argument), two-sided. The treatment is
expected to LOWER churn: p2 = p1 - mde (absolute) or p2 = p1 * (1 - mde) (relative).
Shared by Phase 5c (experiments) and Phase 5d (A/B plan).
"""

import math
from typing import Any, Literal

from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

MdeType = Literal["absolute", "relative"]
DAYS_PER_MONTH = 30.4375
FORMULA = (
    r"h = \left|2\arcsin\sqrt{p_1} - 2\arcsin\sqrt{p_2}\right|,\quad "
    r"n_T = \frac{\left(z_{1-\alpha/2} + z_{1-\beta}\right)^2}{h^2}"
    r"\left(1 + \frac{1}{r}\right),\quad n_C = r\,n_T,\quad r = \frac{s_C}{1 - s_C}"
)


class DesignError(ValueError):
    """Invalid experiment design input."""


def _validate(baseline_rate: float, mde: float, alpha: float, power: float,
              control_share: float, mde_type: str) -> None:
    if mde_type not in ("absolute", "relative"):
        raise DesignError("mde_type must be 'absolute' or 'relative'.")
    if not 0 < baseline_rate < 1:
        raise DesignError("Baseline churn rate must be between 0 and 1 (exclusive).")
    if not mde > 0:
        raise DesignError("The minimum detectable effect must be greater than 0.")
    if mde_type == "relative" and mde >= 1:
        raise DesignError("A relative MDE must be below 1 (100% of the baseline).")
    if mde_type == "absolute" and mde >= baseline_rate:
        raise DesignError("An absolute MDE must be smaller than the baseline churn rate.")
    if not 0 < alpha <= 0.2:
        raise DesignError("Alpha must be greater than 0 and at most 0.2.")
    if not 0.5 <= power < 1:
        raise DesignError("Power must be at least 0.5 and below 1.")
    if not 0.05 <= control_share <= 0.95:
        raise DesignError("Control share must be between 0.05 and 0.95.")


def target_rate(baseline_rate: float, mde: float, mde_type: MdeType) -> float:
    return baseline_rate - mde if mde_type == "absolute" else baseline_rate * (1 - mde)


def _ratio(control_share: float) -> float:
    """statsmodels ratio = nobs2 / nobs1, with nobs1 = treatment and nobs2 = control."""
    return control_share / (1 - control_share)


def detectable_effect(baseline_rate: float, n_available: int, alpha: float, power: float,
                      control_share: float) -> dict[str, float] | None:
    """Smallest churn reduction that n_available customers (split by control_share)
    can detect. None when the treatment arm would have fewer than 2 customers or
    even a drop to 0% churn is not detectable."""
    n_treatment = n_available * (1 - control_share)
    if n_treatment < 2:
        return None
    h = float(NormalIndPower().solve_power(
        effect_size=None, nobs1=n_treatment, alpha=alpha, power=power,
        ratio=_ratio(control_share), alternative="two-sided"))
    angle = math.asin(math.sqrt(baseline_rate)) - h / 2
    if angle <= 0:
        return None
    p2 = math.sin(angle) ** 2
    return {"treatment_rate": p2, "absolute": baseline_rate - p2,
            "relative": (baseline_rate - p2) / baseline_rate, "effect_size_h": h}


def sample_size(baseline_rate: float, mde: float, *, alpha: float = 0.05, power: float = 0.8,
                control_share: float = 0.5, mde_type: MdeType = "absolute",
                n_available: int | None = None,
                monthly_volume: int | None = None) -> dict[str, Any]:
    """Sample size per arm plus feasibility for the customers actually available."""
    _validate(baseline_rate, mde, alpha, power, control_share, mde_type)
    if n_available is not None and n_available < 0:
        raise DesignError("Available customers cannot be negative.")
    if monthly_volume is not None and monthly_volume <= 0:
        raise DesignError("Monthly volume must be greater than 0.")

    p2 = target_rate(baseline_rate, mde, mde_type)
    h = abs(float(proportion_effectsize(baseline_rate, p2)))
    ratio = _ratio(control_share)
    nobs1 = float(NormalIndPower().solve_power(
        effect_size=h, nobs1=None, alpha=alpha, power=power, ratio=ratio,
        alternative="two-sided"))
    n_treatment = math.ceil(nobs1)
    n_control = math.ceil(nobs1 * ratio)
    n_total = n_treatment + n_control

    result: dict[str, Any] = {
        "inputs": {"baseline_rate": baseline_rate, "mde": mde, "mde_type": mde_type,
                   "alpha": alpha, "power": power, "control_share": control_share,
                   "alternative": "two-sided", "n_available": n_available,
                   "monthly_volume": monthly_volume},
        "treatment_rate": p2,
        "absolute_mde": baseline_rate - p2,
        "relative_mde": (baseline_rate - p2) / baseline_rate,
        "effect_size_h": h,
        "n_treatment": n_treatment,
        "n_control": n_control,
        "n_total": n_total,
        "formula": FORMULA,
        "feasible": None,
        "detectable_with_available": None,
        "duration_months": None,
        "duration_days": None,
        "warnings": [],
    }

    if monthly_volume is not None:
        months = n_total / monthly_volume
        result["duration_months"] = months
        result["duration_days"] = math.ceil(months * DAYS_PER_MONTH)

    if n_available is not None:
        result["feasible"] = n_available >= n_total
        detectable = detectable_effect(baseline_rate, n_available, alpha, power, control_share)
        result["detectable_with_available"] = detectable
        if not result["feasible"]:
            if detectable is None:
                hint = ("even a drop to 0% churn is not detectable; widen the segment "
                        "or pool several months of customers.")
            else:
                hint = (f"the smallest detectable drop is {detectable['absolute'] * 100:.1f} "
                        f"percentage points ({detectable['relative'] * 100:.0f}% relative); "
                        "use an MDE at least that large or widen the segment.")
            result["warnings"].append(
                f"Segment too small: {n_available:,} customers available but "
                f"{n_total:,} are needed ({n_treatment:,} treatment + {n_control:,} "
                f"control). With {n_available:,} customers, {hint}")
    return result
