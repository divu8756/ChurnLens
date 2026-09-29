"""Business metrics (SPEC v1.3, runbook T5d.2): revenue at risk, expected saving per offer,
the assumption-driven next best offer and ROI by segment. Python only.

    revenue_at_risk_i   = p_i * ARPU_i * months_remaining
    expected_saving_i,o = p_i * acceptance_o * save_rate_o * ARPU_i * months_remaining
                          - acceptance_o * cost_o            (cost_basis = per_accepted)
                          - cost_o                           (cost_basis = per_targeted)

p is the calibrated churn probability (CLAUDE.md rule 23). The offer with the highest
expected saving wins; "No offer" when the best is <= 0. Offer acceptance / save rates /
costs are ASSUMPTIONS from app/config/offers.yaml unless measured values exist (Phase 5b
offer data or a Phase 5c experiment), which replace them with source = "data".
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from app.catalog import ColumnInRule, OfferSpec, RiskBandRule
from app.stats.common import jsonable
from app.stats.experiment_design import sample_size_two_proportions

NO_OFFER = "No offer"
DEFAULT_MONTHS = 12
MONTHS_RANGE = (1, 60)
SAVING_FORMULA = (r"\text{saving}_{i,o} = p_i \cdot a_o \cdot s_o \cdot \text{ARPU}_i \cdot m"
                  r" - a_o \cdot c_o")
RISK_FORMULA = r"\text{revenue at risk}_i = p_i \cdot \text{ARPU}_i \cdot m"


@dataclass(frozen=True)
class OfferTerms:
    """One offer with the numbers actually used and where each came from."""

    name: str
    cost: float
    cost_basis: str
    acceptance: float
    save_rate: float
    rules: tuple[Any, ...]
    sources: dict[str, str]


def _check_months(months: float) -> None:
    if not MONTHS_RANGE[0] <= months <= MONTHS_RANGE[1]:
        raise ValueError(f"months_remaining must be between {MONTHS_RANGE[0]} and "
                         f"{MONTHS_RANGE[1]}.")


def revenue_at_risk(df: pd.DataFrame, p: np.ndarray, arpu_col: str,
                    months_remaining: float = DEFAULT_MONTHS) -> tuple[np.ndarray, dict[str, Any]]:
    """(per-customer revenue at risk, summary)."""
    _check_months(months_remaining)
    arpu = pd.to_numeric(df[arpu_col], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    values = np.asarray(p, dtype=float) * arpu * months_remaining
    return values, {"total": float(values.sum()), "customers": int(len(values)),
                    "months_remaining": months_remaining, "arpu_column": arpu_col,
                    "formula": RISK_FORMULA}


def expected_saving(p: Any, arpu: Any, months_remaining: float, offer: OfferTerms) -> Any:
    """Vectorised over customers (p and arpu may be arrays)."""
    gain = np.asarray(p) * offer.acceptance * offer.save_rate * np.asarray(arpu) \
        * months_remaining
    cost = offer.acceptance * offer.cost if offer.cost_basis == "per_accepted" else offer.cost
    return gain - cost


def expected_cost(offer: OfferTerms) -> float:
    """Expected spend per targeted customer."""
    return offer.acceptance * offer.cost if offer.cost_basis == "per_accepted" else offer.cost


def _rule_columns(rule: Any) -> list[str]:
    return [] if isinstance(rule, RiskBandRule) else [rule.column]


def _rule_mask(rule: Any, df: pd.DataFrame) -> np.ndarray:
    if isinstance(rule, RiskBandRule):
        return df["risk_band"].isin(rule.risk_band).to_numpy()
    if isinstance(rule, ColumnInRule):
        return df[rule.column].astype(str).isin([str(v) for v in rule.in_]).to_numpy()
    values = pd.to_numeric(df[rule.column], errors="coerce")
    mask = values.notna()
    if rule.min is not None:
        mask &= values >= rule.min
    if rule.max is not None:
        mask &= values <= rule.max
    return mask.to_numpy()


def eligible_offers(customers: pd.DataFrame, catalogue: list[OfferTerms]
                    ) -> tuple[dict[str, np.ndarray], list[str]]:
    """({offer: eligibility mask per customer}, warnings). An offer whose rule names a
    column that is not in the data is skipped with a warning, never a crash."""
    masks: dict[str, np.ndarray] = {}
    warnings: list[str] = []
    for offer in catalogue:
        missing = sorted({c for r in offer.rules for c in _rule_columns(r)
                          if c not in customers.columns})
        if missing:
            warnings.append(f"Offer '{offer.name}' skipped: its eligibility rules use "
                            f"{', '.join(missing)}, which is not in this data.")
            continue
        mask = np.ones(len(customers), dtype=bool)
        for rule in offer.rules:
            mask &= _rule_mask(rule, customers)
        masks[offer.name] = mask
    return masks, warnings


def next_best_offer(customers: pd.DataFrame, p: np.ndarray, arpu: np.ndarray,
                    catalogue: list[OfferTerms], months_remaining: float = DEFAULT_MONTHS
                    ) -> tuple[pd.DataFrame, list[str]]:
    """Per customer: best offer, runner-up and their expected savings ("No offer" <= 0)."""
    _check_months(months_remaining)
    masks, warnings = eligible_offers(customers, catalogue)
    usable = [o for o in catalogue if o.name in masks]
    n = len(customers)
    if usable:
        savings = np.column_stack([
            np.where(masks[o.name], expected_saving(p, arpu, months_remaining, o), -np.inf)
            for o in usable])
    else:
        savings = np.full((n, 1), -np.inf)
    # Stable ordering: ties go to the offer listed first in the catalogue.
    order = np.argsort(-savings, axis=1, kind="stable")
    rows = np.arange(n)
    best_i, second_i = order[:, 0], order[:, 1] if savings.shape[1] > 1 else None
    best = savings[rows, best_i]
    names = np.array([o.name for o in usable] or [NO_OFFER], dtype=object)
    costs = np.array([expected_cost(o) for o in usable] or [0.0])
    has_best = np.isfinite(best) & (best > 0)
    table = pd.DataFrame({
        "customer_id": customers["customer_id"].to_numpy(),
        "risk_band": customers["risk_band"].to_numpy(),
        "p_churn": np.asarray(p, dtype=float),
        "arpu": np.asarray(arpu, dtype=float),
        "best_offer": np.where(has_best, names[best_i], NO_OFFER),
        "expected_saving": np.where(has_best, best, 0.0),
        "expected_cost": np.where(has_best, costs[best_i], 0.0),
        "eligible_offers": np.isfinite(savings).sum(axis=1),
    })
    if second_i is not None:
        second = savings[rows, second_i]
        ok = has_best & np.isfinite(second) & (second > 0)
        table["runner_up"] = np.where(ok, names[second_i], None)
        table["runner_up_saving"] = np.where(ok, second, np.nan)
    else:
        table["runner_up"] = None
        table["runner_up_saving"] = np.nan
    return table, warnings


def offer_roi_by_segment(table: pd.DataFrame, segment: pd.Series) -> list[dict[str, Any]]:
    """Customers with an offer, total expected saving, total expected cost and ROI
    (net expected saving per unit of expected offer cost) by segment."""
    with_offer = table.assign(segment=segment.to_numpy())
    with_offer = with_offer[with_offer["best_offer"] != NO_OFFER]
    rows = []
    for name, g in with_offer.groupby("segment", sort=True):
        cost = float(g["expected_cost"].sum())
        saving = float(g["expected_saving"].sum())
        rows.append({"segment": str(name), "customers": int(len(g)),
                     "total_expected_saving": saving, "total_expected_cost": cost,
                     "roi": saving / cost if cost > 0 else None})
    return sorted(rows, key=lambda r: -r["total_expected_saving"])


def data_overrides(offer_effectiveness: dict[str, Any] | None,
                   evidence: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Measured acceptance / save rate / cost per offer (casefolded name).

    - Phase 5c experiment (preferred): save_rate = retention lift per acceptor / control
      churn (share of would-be churners kept among acceptors); acceptance from the test.
    - Phase 5b offer data: acceptance rate; save_rate = (churn if declined - churn if
      accepted) / churn if declined, an association; cost = average cost of acceptors.
    Values are clipped to [0, 1]."""
    out: dict[str, dict[str, Any]] = {}
    eff = offer_effectiveness or {}
    costs = ((eff.get("next_best_offer") or {}).get("offer_costs")) or {}
    for row in eff.get("offers") or []:
        key = str(row.get("offer", "")).casefold()
        acc_churn = (row.get("acceptors") or {}).get("churn_rate")
        dec_churn = (row.get("decliners") or {}).get("churn_rate")
        entry: dict[str, Any] = {"label": "observational"}
        if row.get("acceptance_rate") is not None:
            entry["acceptance"] = float(row["acceptance_rate"])
        if acc_churn is not None and dec_churn:
            entry["save_rate"] = float(min(1.0, max(0.0, (dec_churn - acc_churn) / dec_churn)))
        if row.get("offer") in costs and costs[row["offer"]]:
            entry["cost"] = float(costs[row["offer"]])
        out[key] = entry
    for key, ev in evidence.items():
        entry = dict(out.get(key, {}))
        control = ev.get("control_churn")
        lift = ev.get("retention_lift_per_acceptor")
        if lift is not None and control:
            entry["save_rate"] = float(min(1.0, max(0.0, lift / control)))
        if ev.get("acceptance_rate") is not None:
            entry["acceptance"] = float(ev["acceptance_rate"])
        entry["label"] = "experiment-proven"
        out[key] = entry
    return out


def offer_terms(catalogue: list[OfferSpec], overrides: dict[str, dict[str, Any]],
                user: dict[str, dict[str, float]] | None = None) -> list[OfferTerms]:
    """Catalogue values, then measured data, then the user's edits (highest priority)."""
    user = {k.casefold(): v for k, v in (user or {}).items()}
    terms = []
    for spec in catalogue:
        key = spec.name.casefold()
        values = {"acceptance": spec.assumed_acceptance_rate,
                  "save_rate": spec.assumed_save_rate, "cost": spec.cost}
        sources = dict.fromkeys(values, "default")
        for field, value in (overrides.get(key) or {}).items():
            if field in values:
                values[field], sources[field] = value, "data"
        for field, value in (user.get(key) or {}).items():
            if field in values and value is not None:
                values[field], sources[field] = float(value), "user"
        terms.append(OfferTerms(spec.name, values["cost"], spec.cost_basis,
                                values["acceptance"], values["save_rate"],
                                tuple(spec.eligible_segments), sources))
    return terms


def assumptions_block(months: float, months_source: str, terms: list[OfferTerms]
                      ) -> list[dict[str, Any]]:
    block = [{"name": "months_remaining", "value": months, "unit": "months",
              "source": months_source,
              "meaning": "How many months of revenue a saved customer is worth."}]
    for o in terms:
        block += [
            {"name": f"{o.name}: acceptance", "value": o.acceptance, "unit": "share",
             "source": o.sources["acceptance"],
             "meaning": "Share of targeted customers who accept the offer."},
            {"name": f"{o.name}: save rate", "value": o.save_rate, "unit": "share",
             "source": o.sources["save_rate"],
             "meaning": "Share of would-be churners who stay after accepting."},
            {"name": f"{o.name}: cost", "value": o.cost, "unit": o.cost_basis.replace("_", " "),
             "source": o.sources["cost"],
             "meaning": "Cost of the offer (paid when accepted)" if o.cost_basis ==
             "per_accepted" else "Cost of the offer (paid for every customer targeted)"},
        ]
    return block


def summarise(table: pd.DataFrame, risk: dict[str, Any], terms: list[OfferTerms],
              roi: list[dict[str, Any]], warnings: list[str], months: float,
              months_source: str) -> dict[str, Any]:
    with_offer = table[table["best_offer"] != NO_OFFER]
    total_cost = float(with_offer["expected_cost"].sum())
    total_saving = float(with_offer["expected_saving"].sum())
    by_offer = [{"offer": name, "customers": int(len(g)),
                 "expected_saving": float(g["expected_saving"].sum()),
                 "expected_cost": float(g["expected_cost"].sum())}
                for name, g in with_offer.groupby("best_offer", sort=True)]
    return jsonable({
        "enabled": True,
        "revenue_at_risk": risk,
        "kpis": {"revenue_at_risk": risk["total"], "expected_saving": total_saving,
                 "customers_with_offer": int(len(with_offer)),
                 "customers_scored": int(len(table)),
                 "overall_roi": total_saving / total_cost if total_cost > 0 else None},
        "by_offer": sorted(by_offer, key=lambda r: -r["expected_saving"]),
        "roi_by_segment": roi,
        "offers": [{"name": o.name, "acceptance": o.acceptance, "save_rate": o.save_rate,
                    "cost": o.cost, "cost_basis": o.cost_basis, "sources": o.sources}
                   for o in terms],
        "formula": {"saving": SAVING_FORMULA, "revenue_at_risk": RISK_FORMULA},
        "warnings": warnings,
        "assumptions": assumptions_block(months, months_source, terms),
    })


DEFAULT_LIFT = 0.2


def ab_plan(outcomes: Any, segment: str, relative_lift: float | None = None,
            alpha: float | None = None, power: float | None = None) -> dict[str, Any]:
    """A/B test plan for a target segment: p1 = its observed churn rate. Warns when the
    segment has fewer customers than the test needs (2 x n per arm)."""
    y = np.asarray(outcomes, dtype=float)
    lift = DEFAULT_LIFT if relative_lift is None else relative_lift
    a = 0.05 if alpha is None else alpha
    pw = 0.8 if power is None else power
    assumptions = [
        {"name": "relative_lift", "value": lift, "unit": "share",
         "source": "default" if relative_lift is None else "user",
         "meaning": "Relative drop in churn the test must be able to detect."},
        {"name": "alpha", "value": a, "unit": "probability",
         "source": "default" if alpha is None else "user",
         "meaning": "Chance of a false positive (two-sided)."},
        {"name": "power", "value": pw, "unit": "probability",
         "source": "default" if power is None else "user",
         "meaning": "Chance of detecting the effect if it is real."},
    ]
    if len(y) == 0:
        return {"available": False, "segment": segment, "reason": "The segment is empty.",
                "assumptions": assumptions}
    p1 = float(y.mean())
    assumptions.insert(0, {"name": "p1", "value": p1, "unit": "share", "source": "data",
                           "meaning": f"Observed churn rate of {segment}."})
    if not 0 < p1 < 1:
        return {"available": False, "segment": segment, "assumptions": assumptions,
                "reason": "The segment's churn rate is 0% or 100%, so no test can be sized."}
    plan = sample_size_two_proportions(p1, lift, alpha=a, power=pw)
    warnings = []
    if len(y) < plan["total_n"]:
        warnings.append(f"{segment} has {len(y):,} customers but the test needs "
                        f"{plan['total_n']:,} ({plan['n_per_arm']:,} per arm). Detect a larger "
                        "lift, lower the power or test over a longer period.")
    return jsonable({"available": True, "segment": segment, "segment_customers": len(y),
                     **plan, "warnings": warnings, "assumptions": assumptions})
