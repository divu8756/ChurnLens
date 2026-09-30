"""A/B test results analysis (runbook T5c.3). Everything is computed here in Python;
the LLM summary (T5c.4) only explains these numbers, addressed by dot-path source keys
into the returned dict (e.g. "itt.difference.value").

Sign convention: difference = treatment churn rate - control churn rate, so a
negative difference means the offer reduced churn (the good direction).
"""

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import chisquare
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import (
    proportion_confint,
    proportion_effectsize,
    proportions_ztest,
)
from statsmodels.stats.weightstats import CompareMeans, DescrStatsW

from app.stats.experiment_design import sample_size, target_rate

SRM_THRESHOLD = 0.001
CI_LEVEL = 0.95
PER_PROTOCOL_LABEL = ("Per-protocol (acceptors vs control): biased, because customers who "
                      "accept an offer differ from those who do not. Secondary view only.")
SEGMENTS_LABEL = ("Exploratory: pre-registered segments only, p-values Benjamini-Hochberg "
                  "corrected. Not a basis for the ship decision.")
IMPACT_FORMULA = (r"\text{saved} = (p_C - p_T)\,n_T,\quad "
                  r"\text{net} = \text{saved}\times V - c\times n_{\text{accepted}}")


def wilson(count: int, n: int, alpha: float = 1 - CI_LEVEL) -> tuple[float, float]:
    low, high = proportion_confint(count, n, alpha=alpha, method="wilson")
    return float(low), float(high)


def newcombe(x1: int, n1: int, x2: int, n2: int, alpha: float = 1 - CI_LEVEL
             ) -> tuple[float, float]:
    """Newcombe (1998) method 10 hybrid score CI for p1 - p2, from the Wilson intervals."""
    p1, p2 = x1 / n1, x2 / n2
    l1, u1 = wilson(x1, n1, alpha)
    l2, u2 = wilson(x2, n2, alpha)
    d = p1 - p2
    return (d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2),
            d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2))


def srm_check(n_treatment: int, n_control: int, control_share: float) -> dict[str, Any]:
    total = n_treatment + n_control
    expected = [total * (1 - control_share), total * control_share]
    chi2, p = chisquare([n_treatment, n_control], f_exp=expected)
    return {"observed": {"treatment": n_treatment, "control": n_control},
            "expected": {"treatment": expected[0], "control": expected[1]},
            "planned_control_share": control_share,
            "observed_control_share": n_control / total if total else None,
            "chi2": float(chi2), "p_value": float(p), "threshold": SRM_THRESHOLD,
            "failed": bool(p < SRM_THRESHOLD)}


def _arm(churned: pd.Series) -> dict[str, Any]:
    n, x = int(len(churned)), int(churned.sum())
    low, high = wilson(x, n)
    return {"n": n, "churned": x, "rate": x / n, "ci_low": low, "ci_high": high}


def compare_rates(treat: pd.Series, ctrl: pd.Series, alpha: float) -> dict[str, Any]:
    """Churn per arm with Wilson CIs, Newcombe CI of the difference, z-test."""
    t, c = _arm(treat), _arm(ctrl)
    out: dict[str, Any] = {"arms": {"treatment": t, "control": c}}
    diff = t["rate"] - c["rate"]
    low, high = newcombe(t["churned"], t["n"], c["churned"], c["n"], alpha=alpha)
    out["difference"] = {"value": diff, "ci_low": low, "ci_high": high, "method": "newcombe",
                         "ci_level": 1 - alpha}
    out["relative_lift"] = diff / c["rate"] if c["rate"] > 0 else None
    pooled = (t["churned"] + c["churned"]) / (t["n"] + c["n"])
    if 0 < pooled < 1:
        z, p = proportions_ztest([t["churned"], c["churned"]], [t["n"], c["n"]])
        out["z"], out["p_value"] = float(z), float(p)
    else:
        out["z"], out["p_value"] = None, None  # nobody (or everybody) churned: no test
    out["significant"] = out["p_value"] is not None and out["p_value"] < alpha
    return out


def _mean_ci(values: pd.Series, alpha: float) -> dict[str, Any]:
    stats = DescrStatsW(values.to_numpy(dtype=float))
    low, high = stats.zconfint_mean(alpha=alpha) if len(values) > 1 else (None, None)
    return {"n": int(len(values)), "mean": float(stats.mean) if len(values) else None,
            "ci_low": _num(low), "ci_high": _num(high)}


def _num(value: Any) -> float | None:
    return None if value is None or not np.isfinite(value) else float(value)


def guardrail(treat: pd.Series, ctrl: pd.Series, alpha: float, bad_direction: str,
              tolerance: float) -> dict[str, Any]:
    """Mean per arm with CIs and a Welch (unequal variance) z CI of the difference.
    Breached when the CI shows the bad direction beyond the tolerance (as a share of
    the control mean): complaints up, ARPU down."""
    treat, ctrl = treat.dropna().astype(float), ctrl.dropna().astype(float)
    t, c = _mean_ci(treat, alpha), _mean_ci(ctrl, alpha)
    out: dict[str, Any] = {"arms": {"treatment": t, "control": c}, "bad_direction": bad_direction,
                           "tolerance": tolerance, "breached": False}
    if len(treat) < 2 or len(ctrl) < 2:
        out["difference"] = None
        return out
    low, high = CompareMeans(DescrStatsW(treat.to_numpy()), DescrStatsW(ctrl.to_numpy())
                             ).zconfint_diff(alpha=alpha, usevar="unequal")
    diff = float(treat.mean() - ctrl.mean())
    out["difference"] = {"value": diff, "ci_low": _num(low), "ci_high": _num(high)}
    margin = tolerance * abs(c["mean"] or 0.0)
    if bad_direction == "up":
        out["breached"] = bool(low is not None and low > margin)
    else:
        out["breached"] = bool(high is not None and high < -margin)
    return out


def achieved_power(design: dict[str, Any], n_treatment: int, n_control: int) -> float | None:
    """Power to detect the design's MDE at the sample size actually observed."""
    if n_treatment < 2 or n_control < 1:
        return None
    p2 = target_rate(design["baseline_rate"], design["mde"], design["mde_type"])
    h = abs(float(proportion_effectsize(design["baseline_rate"], p2)))
    return float(NormalIndPower().power(effect_size=h, nobs1=n_treatment, alpha=design["alpha"],
                                        ratio=n_control / n_treatment, alternative="two-sided"))


def business_impact(itt: dict[str, Any], acceptors: int, assumptions: dict[str, Any]
                    ) -> dict[str, Any]:
    n_t = itt["arms"]["treatment"]["n"]
    d = itt["difference"]
    saved = -d["value"] * n_t
    saved_low, saved_high = -d["ci_high"] * n_t, -d["ci_low"] * n_t
    value, cost = assumptions.get("customer_value"), assumptions.get("offer_cost")
    out: dict[str, Any] = {
        "customers_saved": saved, "saved_ci_low": saved_low, "saved_ci_high": saved_high,
        "acceptors": acceptors, "acceptance_rate": acceptors / n_t if n_t else None,
        "customer_value": value, "offer_cost": cost,
        "total_offer_cost": cost * acceptors if cost is not None else None,
        "net_value": None, "net_value_ci_low": None, "net_value_ci_high": None,
        "formula": IMPACT_FORMULA,
        "assumptions": [
            {"name": "customer_value", "value": value,
             "source": assumptions.get("customer_value_source", "user")},
            {"name": "offer_cost", "value": cost,
             "source": assumptions.get("offer_cost_source", "user")},
        ],
    }
    if value is not None and cost is not None:
        total_cost = cost * acceptors
        out["net_value"] = saved * value - total_cost
        out["net_value_ci_low"] = saved_low * value - total_cost
        out["net_value_ci_high"] = saved_high * value - total_cost
    return out


def segment_breakdown(outcomes: pd.DataFrame, names: list[str], alpha: float
                      ) -> dict[str, Any]:
    items: dict[str, Any] = {}
    for name in names:
        member = outcomes["segments"].apply(lambda s, n=name: n in (s or []))
        part = outcomes[member]
        treat, ctrl = part[part.arm == "treatment"].churned, part[part.arm == "control"].churned
        if len(treat) == 0 or len(ctrl) == 0:
            items[name] = {"n": int(len(part)), "skipped": "one arm is empty"}
            continue
        items[name] = {"n": int(len(part)), **compare_rates(treat, ctrl, alpha)}
    tested = [n for n, v in items.items() if v.get("p_value") is not None]
    if tested:
        reject, adjusted, _, _ = multipletests([items[n]["p_value"] for n in tested],
                                               alpha=alpha, method="fdr_bh")
        for n, adj, rej in zip(tested, adjusted, reject, strict=True):
            items[n]["p_adjusted"] = float(adj)
            items[n]["significant"] = bool(rej)
    return {"label": SEGMENTS_LABEL, "method": "benjamini-hochberg", "items": items}


def decision_helper(srm: dict[str, Any], itt: dict[str, Any], impact: dict[str, Any],
                    guardrails: dict[str, Any], design: dict[str, Any]) -> dict[str, Any]:
    """A suggestion for the human, never a decision."""
    reasons: list[str] = []
    breached = [name for name, g in guardrails.items() if g["breached"]]
    d = itt["difference"]
    good, bad = d["ci_high"] < 0, d["ci_low"] > 0
    net = impact["net_value"]
    extra = None
    if srm["failed"]:
        verdict = "untrustworthy"
        reasons.append(f"Sample ratio mismatch (p = {srm['p_value']:.2g} < {SRM_THRESHOLD}): "
                       "the split differs from the plan, so results are not trustworthy and "
                       "shipping is blocked.")
    elif bad or (net is not None and net < 0):
        verdict = "dont_ship"
        if bad:
            reasons.append("The confidence interval shows the offer increased churn.")
        if net is not None and net < 0:
            reasons.append("The offer costs more than the value of the customers it saves.")
    elif good and net is not None and net > 0 and not breached:
        verdict = "ship"
        reasons.append("Churn fell (the confidence interval excludes 0), net value is "
                       "positive and no guardrail was breached.")
    else:
        verdict = "inconclusive"
        if not good:
            reasons.append("The confidence interval of the difference includes 0.")
        if net is None:
            reasons.append("Net value is unknown: enter the customer value and offer cost.")
        if breached:
            reasons.append("Guardrail breached: " + ", ".join(breached) + ".")
        if not good:
            n_t, n_c = itt["arms"]["treatment"]["n"], itt["arms"]["control"]["n"]
            need = sample_size(design["baseline_rate"], design["mde"], alpha=design["alpha"],
                               power=design["power"], control_share=design["control_share"],
                               mde_type=design["mde_type"])
            extra = {"treatment": max(0, need["n_treatment"] - n_t),
                     "control": max(0, need["n_control"] - n_c)}
            if extra["treatment"] == 0 and extra["control"] == 0:
                reasons.append("The test reached its planned size; any effect is probably "
                               "smaller than the minimum detectable effect.")
    return {"verdict": verdict, "reasons": reasons, "guardrails_breached": breached,
            "extra_sample_needed": extra,
            "note": "Decision helper only: a person makes the ship decision."}


def analyse(outcomes: pd.DataFrame, design: dict[str, Any], assumptions: dict[str, Any],
            segment_names: list[str] | None = None) -> dict[str, Any]:
    """outcomes: customer_id, arm, offer_accepted (0/1, treatment), churned (0/1), and
    optionally revenue, complaints, segments (list of pre-registered segment names).
    design: control_share, alpha, power, baseline_rate, mde, mde_type, guardrail_metrics."""
    alpha = design["alpha"]
    treat = outcomes[outcomes.arm == "treatment"]
    ctrl = outcomes[outcomes.arm == "control"]
    if treat.empty or ctrl.empty:
        raise ValueError("Both arms need at least one customer.")
    srm = srm_check(len(treat), len(ctrl), design["control_share"])
    itt = compare_rates(treat.churned, ctrl.churned, alpha)
    itt["achieved_power"] = achieved_power(design, len(treat), len(ctrl))
    itt["label"] = "Intention-to-treat: everyone assigned, whether or not they accepted."
    acceptors = treat[treat.offer_accepted == 1]
    impact = business_impact(itt, len(acceptors), assumptions)

    per_protocol: dict[str, Any] = {"label": PER_PROTOCOL_LABEL, "available": False}
    if len(acceptors):
        per_protocol = {"label": PER_PROTOCOL_LABEL, "available": True,
                        **compare_rates(acceptors.churned, ctrl.churned, alpha)}

    guardrails: dict[str, Any] = {}
    metrics = design.get("guardrail_metrics") or []
    if "complaints" in metrics and "complaints" in outcomes and outcomes.complaints.notna().any():
        guardrails["complaints"] = guardrail(treat.complaints, ctrl.complaints, alpha, "up",
                                             assumptions.get("complaints_tolerance", 0.0))
    if "arpu" in metrics and "revenue" in outcomes and outcomes.revenue.notna().any():
        guardrails["arpu"] = guardrail(treat.revenue, ctrl.revenue, alpha, "down",
                                       assumptions.get("arpu_tolerance", 0.05))

    result: dict[str, Any] = {
        "srm": srm, "itt": itt, "impact": impact, "per_protocol": per_protocol,
        "guardrails": guardrails,
        "segments": segment_breakdown(outcomes, segment_names or [], alpha)
        if segment_names and "segments" in outcomes else None,
        "assumptions": [*impact["assumptions"],
                        {"name": "arpu_tolerance", "value": assumptions.get("arpu_tolerance", 0.05),
                         "source": assumptions.get("arpu_tolerance_source", "default")}],
    }
    result["decision_helper"] = decision_helper(srm, itt, impact, guardrails, design)
    return result
