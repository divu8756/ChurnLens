"""Compact results digest for the LLM agents (runbook T5.1a).

The LLM sees only this digest, never rows. Every number is a fact
{"key", "value", "label"} where key is a dot path into graph state
(app/graph/paths.py), so agents can cite it and the validator can check it.
The digest must stay under TOKEN_BUDGET (estimated at 4 characters/token).
"""

import json
from typing import Any

from app.graph.paths import join, resolve

TOKEN_BUDGET = 12_000
MAX_CATEGORY_COLUMNS = 10
LEVELS_PER_COLUMN = 3
MAX_SIGNIFICANT_TESTS = 20
NON_SIGNIFICANT_TESTS = 5
MAX_DRIVERS = 10
MAX_IMPACT_ITEMS = 12
MAX_OFFERS = 10


def _round(value: Any) -> Any:
    if isinstance(value, float):
        return float(f"{value:.4g}")
    return value


class _Facts:
    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state
        self.sections: dict[str, list[dict[str, Any]]] = {}

    def add(self, section: str, key: str, label: str) -> None:
        try:
            value = resolve(self.state, key)
        except KeyError:
            return
        if value is None or isinstance(value, dict | list):
            return
        self.sections.setdefault(section, []).append(
            {"key": key, "value": _round(value), "label": label})


def estimate_tokens(digest: dict[str, Any]) -> int:
    return len(json.dumps(digest, ensure_ascii=False)) // 4


def build_digest(state: dict[str, Any]) -> dict[str, Any]:
    f = _Facts(state)

    # Data health
    for key, label in (("rows_after", "customers analysed"),
                       ("health_score", "data health score (0-100)"),
                       ("duplicates_removed", "duplicate rows removed"),
                       ("class_balance.positive_rate", "overall churn rate (fraction)")):
        f.add("data_health", join("data_health", key), label)

    # Strongest categorical variables first (by effect size in the tests).
    tests = (state.get("hypothesis_results") or {}).get("tests", [])
    strength = {t["variable"]: abs(t["effect_size"]["value"]) for t in tests}
    categorical = (state.get("eda_results") or {}).get("categorical", {})
    columns = sorted(categorical, key=lambda c: -strength.get(c, 0))[:MAX_CATEGORY_COLUMNS]
    for col in columns:
        for i, level in enumerate(categorical[col]["levels"][:LEVELS_PER_COLUMN]):
            base = join("eda_results.categorical", col, "levels", i)
            f.add("churn_by_category", join(base, "churn_rate"),
                  f"churn rate (fraction) where {col} = {level['level']}")
            f.add("churn_by_category", join(base, "n"),
                  f"customers where {col} = {level['level']}")

    # Segments
    for i, seg in enumerate((state.get("segments") or {}).get("segments", [])):
        base = join("segments.segments", i)
        name = f"segment '{seg['label']}'"
        f.add("segments", join(base, "size"), f"customers in {name}")
        f.add("segments", join(base, "churn_rate"), f"churn rate (fraction) of {name}")
        f.add("segments", join(base, "churn_lift"), f"churn rate of {name} / overall rate")

    # Hypothesis tests: significant ones plus the strongest non-significant ones.
    significant = [i for i, t in enumerate(tests) if t["significant"]][:MAX_SIGNIFICANT_TESTS]
    weak = sorted((i for i, t in enumerate(tests) if not t["significant"]),
                  key=lambda i: -abs(tests[i]["effect_size"]["value"]))[:NON_SIGNIFICANT_TESTS]
    for i in significant + weak:
        t = tests[i]
        base = join("hypothesis_results.tests", i)
        tag = "significant" if t["significant"] else "NOT significant"
        f.add("hypothesis_tests", join(base, "p_adjusted"),
              f"{t['variable']}: {t['test_name']} BH-adjusted p ({tag})")
        f.add("hypothesis_tests", join(base, "effect_size.value"),
              f"{t['variable']}: {t['effect_size']['name']} ({t['effect_size']['band']})")

    # Model
    for key, label in (("chosen_model_name", "chosen model"),
                       ("test.roc_auc", "test ROC-AUC"), ("test.pr_auc", "test PR-AUC"),
                       ("test.recall", "test recall at threshold 0.5"),
                       ("test.precision", "test precision at threshold 0.5"),
                       ("risk_bands.band_counts.High", "customers in the High risk band"),
                       ("risk_bands.band_counts.Medium", "customers in the Medium risk band"),
                       ("risk_bands.band_counts.Low", "customers in the Low risk band")):
        f.add("model", join("model_metrics", key), label)

    # Drivers
    drivers = (state.get("feature_importance") or {}).get("driver_impact", [])
    for i, d in enumerate(drivers[:MAX_DRIVERS]):
        base = join("feature_importance.driver_impact", i)
        name = d["feature"]
        f.add("drivers", join(base, "permutation_rank"), f"{name}: importance rank")
        f.add("drivers", join(base, "mean_abs_shap"), f"{name}: mean |SHAP| (log-odds)")
        if d.get("or_label"):
            f.add("drivers", join(base, "odds_ratio"), f"odds ratio, {d['or_label']}")
            f.add("drivers", join(base, "or_ci_lower"), f"95% CI lower, {d['or_label']}")
            f.add("drivers", join(base, "or_ci_upper"), f"95% CI upper, {d['or_label']}")

    # Survival
    survival = state.get("survival_results") or {}
    if not survival.get("skipped", True):
        f.add("survival", "survival_results.overall.median_survival",
              f"median time to churn in {survival.get('time_column')} units (null = not reached)")
        for h in survival.get("horizons", []):
            f.add("survival", join("survival_results.overall.survival_at", h),
                  f"share still active at {h} {survival.get('time_column')} units")
        for gi, g in enumerate(survival.get("by_group", [])):
            f.add("survival", join("survival_results.by_group", gi, "logrank.p_value"),
                  f"log-rank p for survival by {g['column']}")

    # Impact
    impact = state.get("impact_estimates") or {}
    for item_id in impact.get("item_order", [])[:MAX_IMPACT_ITEMS]:
        item = impact["items"][item_id]
        base = join("impact_estimates.items", item_id)
        name = item["label"]
        f.add("impact", join(base, "customers"), f"{name}: customers")
        f.add("impact", join(base, "churners"), f"{name}: churned customers")
        f.add("impact", join(base, "churn_rate"), f"{name}: churn rate (fraction)")
        f.add("impact", join(base, "monthly_revenue_at_risk"),
              f"{name}: monthly revenue of churned customers")
        for scenario in ("reduce_10pct", "reduce_25pct"):
            sbase = join(base, "scenarios", scenario)
            f.add("impact", join(sbase, "churners_saved"),
                  f"{name}: churners saved if churn fell {scenario[7:9]}% (assumption)")
            f.add("impact", join(sbase, "monthly_revenue_saved"),
                  f"{name}: monthly revenue saved if churn fell {scenario[7:9]}% (assumption)")

    # Offers (Phase 5b): effectiveness per offer and the next-best-offer summary.
    offers = state.get("offer_effectiveness") or {}
    for i, row in enumerate(offers.get("offers", [])[:MAX_OFFERS]):
        base = join("offer_effectiveness.offers", i)
        name = f"offer '{row['offer']}'"
        f.add("offers", join(base, "shown"), f"{name}: customers shown")
        f.add("offers", join(base, "acceptance_rate"), f"{name}: acceptance rate (fraction)")
        f.add("offers", join(base, "acceptors.churn_rate"),
              f"{name}: churn rate (fraction) of customers who accepted")
        f.add("offers", join(base, "decliners.churn_rate"),
              f"{name}: churn rate (fraction) of customers who declined")
        if row.get("test"):
            tag = "significant" if row["test"]["significant"] else "NOT significant"
            f.add("offers", join(base, "test.p_adjusted"),
                  f"{name}: accepted vs declined churn, BH-adjusted p ({tag})")
    f.add("offers", "offer_effectiveness.never_offered.churn_rate",
          "churn rate (fraction) of customers never offered anything")
    f.add("offers", "offer_effectiveness.selection_bias.gap",
          "offered minus never-offered mean predicted churn (selection bias check)")
    nbo = offers.get("next_best_offer") or {}
    f.add("offers", "offer_effectiveness.next_best_offer.customers_scored",
          "Medium/High-risk customers scored for a next best offer")
    for i, row in enumerate(nbo.get("by_offer", [])):
        base = join("offer_effectiveness.next_best_offer.by_offer", i)
        f.add("offers", join(base, "customers"),
              f"customers whose next best offer is '{row['offer']}'")
        f.add("offers", join(base, "expected_value"),
              f"total expected value if '{row['offer']}' goes to them "
              f"({nbo.get('value_unit')}, assumption)")

    digest = {
        "about": "Computed results. Every fact has a key (source_key) and a value.",
        "sections": f.sections,
        "impact_assumptions": impact.get("scenarios", {}),
    }
    # Trim the largest sections if the budget is exceeded (never expected on normal data).
    while estimate_tokens(digest) > TOKEN_BUDGET:
        largest = max(f.sections, key=lambda s: len(f.sections[s]))
        if len(f.sections[largest]) <= 1:
            break
        f.sections[largest] = f.sections[largest][: len(f.sections[largest]) * 3 // 4]
    return digest


def digest_keys(digest: dict[str, Any]) -> list[str]:
    return [fact["key"] for facts in digest["sections"].values() for fact in facts]
