"""Next best offer (Phase 5b, runbook T5b.3). Python only; the LLM never sees this maths.

For each Medium/High-risk customer and each eligible offer:
    expected_value = P(churn) * P(accept) * retention_lift * customer_value
                     - P(accept) * cost_per_acceptance
    retention_lift = max(0, P(stay | accepted) - P(stay | declined))
The runbook's formula uses P(stay | accepted) alone, which credits an offer with every
acceptor who would have stayed anyway (an offer with no effect still looks valuable). The
lift counts only the extra retention among customers shown the offer. It is still an
association (acceptors self-select); a holdout test (Phase 5c) measures the causal effect.
The cost is only paid when an offer is accepted (OfferCost is 0 otherwise), so it is
weighted by P(accept). A "No offer" option (value 0) wins when every offer is negative.

- P(accept): per offer with >= MIN_EXPOSURES customers shown, a logistic regression on the
  churn model's features (same preprocessing), unweighted so its probabilities stay
  calibrated (CLAUDE.md rule 23). Smaller offers use the Laplace-smoothed acceptance rate
  of the customer's segment, flagged "low data".
- P(stay | accepted) and P(stay | declined): per offer and segment, Laplace-smoothed
  (stayed + 1) / (n + 2).
- customer_value: monthly revenue x horizon when a revenue column exists; otherwise 1
  (the expected value is then "customers saved").
- Eligibility: no offer above the maximum discount, and no offer the customer declined
  within the last DECLINE_DAYS (any past decline when offer dates are unknown).
"""

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

from app.schema_validation import OfferColumns
from app.stats.common import jsonable
from app.stats.modelling import RANDOM_STATE, model_features, preprocessor
from app.stats.offers import customer_ids, cutoff_column

NO_OFFER = "No offer"
DISCOUNT = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:loyalty\s*)?(?:discount|off)", re.I)
CV_FOLDS = 5


@dataclass
class NboConfig:
    horizon_months: int = 12
    max_discount: float = 0.20
    decline_days: int = 30
    min_exposures: int = 50
    laplace: float = 1.0
    bands: tuple[str, ...] = ("High", "Medium")
    sources: dict[str, str] = field(default_factory=lambda: {
        "horizon_months": "default", "max_discount": "default", "decline_days": "default"})


def offer_discount(offer: str) -> float | None:
    """Discount share written in the offer name ("10% loyalty discount" -> 0.10), if any."""
    match = DISCOUNT.search(offer)
    return float(match.group(1)) / 100 if match else None


def smoothed(successes: float, trials: float, laplace: float) -> float:
    return float((successes + laplace) / (trials + 2 * laplace))


def expected_value(p_churn: float, p_accept: float, lift: float, value: float,
                   cost: float) -> float:
    return p_churn * p_accept * lift * value - p_accept * cost


def _acceptance_models(frame: pd.DataFrame, schema: dict[str, Any], long: pd.DataFrame,
                       ids: pd.Series, exclude: list[str], cfg: NboConfig
                       ) -> tuple[dict[str, Pipeline], dict[str, dict[str, Any]]]:
    numeric, categorical = model_features(frame, schema, exclude)
    x_all = frame[numeric + categorical]
    row_of = pd.Series(np.arange(len(frame)), index=ids.to_numpy())
    row_of = row_of[~row_of.index.duplicated()]
    models: dict[str, Pipeline] = {}
    info: dict[str, dict[str, Any]] = {}
    for offer, group in long.groupby("offer", sort=True):
        y = group["accepted"].to_numpy()
        n, positives = len(group), int(y.sum())
        entry: dict[str, Any] = {"shown": n, "accepted": positives, "low_data": True,
                                 "method": "segment acceptance rate (Laplace-smoothed)",
                                 "roc_auc": None}
        if n >= cfg.min_exposures and 0 < positives < n and numeric + categorical:
            rows = group["customer_id"].map(row_of).to_numpy()
            x = x_all.iloc[rows]
            pipe = Pipeline([("prep", preprocessor(numeric, categorical)),
                             ("model", LogisticRegression(max_iter=2000,
                                                          random_state=RANDOM_STATE))])
            folds = min(CV_FOLDS, positives, n - positives)
            if folds >= 2:
                cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=RANDOM_STATE)
                entry["roc_auc"] = float(np.mean(cross_val_score(pipe, x, y, cv=cv,
                                                                 scoring="roc_auc")))
            models[str(offer)] = pipe.fit(x, y)
            entry.update({"low_data": False, "method": "logistic regression on customer "
                          "features (unweighted, calibrated probabilities)"})
        info[str(offer)] = entry
    return models, info


def _declined_recently(frame: pd.DataFrame, schema: dict[str, Any], long: pd.DataFrame,
                       cfg: NboConfig) -> set[tuple[str, str]]:
    declined = long[long["accepted"] == 0]
    if declined.empty:
        return set()
    if declined["offer_date"].notna().any():
        cutoff = cutoff_column(frame, schema)
        ids = customer_ids(frame, schema)
        as_of = (pd.Series(pd.to_datetime(frame[cutoff], errors="coerce").to_numpy(),
                           index=ids.to_numpy()) if cutoff else None)
        if as_of is not None:
            as_of = as_of[~as_of.index.duplicated()]
            ref = declined["customer_id"].map(as_of)
        else:
            ref = pd.Series(declined["offer_date"].max(), index=declined.index)
        days = (ref - declined["offer_date"]).dt.days
        # A decline with an unknown date counts as recent (the conservative choice).
        recent = days.isna() | (days <= cfg.decline_days)
        declined = declined[recent.to_numpy()]
    return set(zip(declined["customer_id"], declined["offer"], strict=True))


def score_next_best_offers(frame: pd.DataFrame, schema: dict[str, Any], long: pd.DataFrame,
                           predictions: pd.DataFrame, segment_labels: np.ndarray | None,
                           exclude: list[str], cfg: NboConfig | None = None
                           ) -> tuple[pd.DataFrame, dict[str, Any]]:
    """(one row per scored customer, summary with assumptions). Deterministic (seed 42)."""
    cfg = cfg or NboConfig()
    ids = customer_ids(frame, schema)
    target = frame[schema["target_column"]].astype(int).to_numpy()
    churned = pd.Series(target, index=ids.to_numpy())
    churned = churned[~churned.index.duplicated()]
    seg = (pd.Series(segment_labels, index=ids.to_numpy()) if segment_labels is not None
           and len(segment_labels) == len(frame) else pd.Series(0, index=ids.to_numpy()))
    seg = seg[~seg.index.duplicated()]

    catalog = sorted(long["offer"].unique().tolist())
    models, model_info = _acceptance_models(frame, schema, long, ids, exclude, cfg)
    declined = _declined_recently(frame, schema, long, cfg)

    # P(stay | accepted) and segment acceptance rates, Laplace-smoothed.
    shown = long.assign(segment=long["customer_id"].map(seg).to_numpy(),
                        churned=long["customer_id"].map(churned).to_numpy())
    p_stay: dict[tuple[str, Any], tuple[float, float]] = {}  # (if accepted, if declined)
    p_rate: dict[tuple[str, Any], float] = {}

    def stay_rates(g: pd.DataFrame) -> tuple[float, float]:
        acc, dec = g[g["accepted"] == 1], g[g["accepted"] == 0]
        return (smoothed(int((acc["churned"] == 0).sum()), len(acc), cfg.laplace),
                smoothed(int((dec["churned"] == 0).sum()), len(dec), cfg.laplace))

    for (offer, segment), g in shown.groupby(["offer", "segment"], sort=True):
        p_stay[(offer, segment)] = stay_rates(g)
        p_rate[(offer, segment)] = smoothed(int(g["accepted"].sum()), len(g), cfg.laplace)
    for offer, g in shown.groupby("offer", sort=True):
        p_stay[(offer, None)] = stay_rates(g)
        p_rate[(offer, None)] = smoothed(int(g["accepted"].sum()), len(g), cfg.laplace)

    offers_cfg = OfferColumns.model_validate(schema["offer_columns"])
    cost: dict[str, float] = {o: 0.0 for o in catalog}
    cost_source = "default"
    if offers_cfg.cost and offers_cfg.cost in frame.columns:
        costs = pd.Series(pd.to_numeric(frame[offers_cfg.cost], errors="coerce").to_numpy(),
                          index=ids.to_numpy())
        costs = costs[~costs.index.duplicated()]
        acc = long[long["accepted"] == 1]
        for offer, g in acc.groupby("offer"):
            values = g["customer_id"].map(costs).dropna()
            cost[str(offer)] = float(values.mean()) if len(values) else 0.0
        cost_source = "data"

    revenue_col = schema.get("revenue_column")
    unit = "revenue" if revenue_col and revenue_col in frame.columns else "customers"
    if unit == "revenue":
        rev = pd.Series(pd.to_numeric(frame[revenue_col], errors="coerce").to_numpy(),
                        index=ids.to_numpy())
        rev = rev[~rev.index.duplicated()].fillna(0.0) * cfg.horizon_months
    eligible_offers = [o for o in catalog
                       if (offer_discount(o) or 0.0) <= cfg.max_discount + 1e-12]

    scored = predictions[predictions["risk_band"].isin(cfg.bands)]
    numeric, categorical = model_features(frame, schema, exclude)
    x_all = frame[numeric + categorical]
    row_of = pd.Series(np.arange(len(frame)), index=ids.to_numpy())
    row_of = row_of[~row_of.index.duplicated()]
    rows_idx = scored["customer_id"].map(row_of).to_numpy()
    accept_pred = {o: models[o].predict_proba(x_all.iloc[rows_idx])[:, 1] for o in models}

    records = []
    for i, (cid, p_churn) in enumerate(zip(scored["customer_id"], scored["churn_probability"],
                                           strict=True)):
        segment = seg.get(cid)
        value = float(rev.get(cid, 0.0)) if unit == "revenue" else 1.0
        options = []
        for offer in eligible_offers:
            if (cid, offer) in declined:
                continue
            pa = (float(accept_pred[offer][i]) if offer in accept_pred
                  else p_rate.get((offer, segment), p_rate[(offer, None)]))
            stay_acc, stay_dec = p_stay.get((offer, segment), p_stay[(offer, None)])
            lift = max(0.0, stay_acc - stay_dec)
            ev = expected_value(float(p_churn), pa, lift, value, cost[offer])
            options.append((ev, offer, pa, stay_acc, stay_dec, lift))
        options.sort(key=lambda o: (-o[0], o[1]))
        best = options[0] if options and options[0][0] > 0 else None
        runner = options[1] if best and len(options) > 1 and options[1][0] > 0 else None
        records.append({
            "customer_id": cid,
            "best_offer": best[1] if best else NO_OFFER,
            "expected_value": round(best[0], 4) if best else 0.0,
            "runner_up": runner[1] if runner else None,
            "runner_up_value": round(runner[0], 4) if runner else None,
            "p_churn": float(p_churn),
            # Inputs kept unrounded so the stored expected value can be recomputed from them.
            "p_accept": best[2] if best else None,
            "p_stay_if_accepted": best[3] if best else None,
            "p_stay_if_declined": best[4] if best else None,
            "retention_lift": best[5] if best else None,
            "customer_value": round(value, 2),
            "offer_cost": round(cost[best[1]], 2) if best else None,
            "low_data": bool(best and model_info[best[1]]["low_data"]),
            "eligible_offers": len(options),
            "no_offer_reason": None if best else (
                "every eligible offer has a negative expected value" if options
                else "no eligible offers"),
        })
    table = pd.DataFrame.from_records(records, columns=[
        "customer_id", "best_offer", "expected_value", "runner_up", "runner_up_value",
        "p_churn", "p_accept", "p_stay_if_accepted", "p_stay_if_declined", "retention_lift",
        "customer_value", "offer_cost",
        "low_data", "eligible_offers", "no_offer_reason"])

    counts = table["best_offer"].value_counts()
    summary = jsonable({
        "customers_scored": int(len(table)),
        "bands": list(cfg.bands),
        "value_unit": unit,
        "total_expected_value": float(table["expected_value"].sum()),
        "by_offer": [{"offer": o, "customers": int(counts.get(o, 0)),
                      "expected_value": float(table.loc[table["best_offer"] == o,
                                                        "expected_value"].sum())}
                     for o in [*catalog, NO_OFFER] if counts.get(o, 0)],
        "offer_models": model_info,
        "offer_costs": cost,
        "excluded_by_discount": [o for o in catalog if o not in eligible_offers],
        "formula": "expected_value = P(churn) * P(accept) * retention_lift * customer_value"
                   " - P(accept) * cost_per_acceptance; retention_lift = max(0, "
                   "P(stay | accepted) - P(stay | declined))",
        "assumptions": [
            {"name": "horizon_months", "value": cfg.horizon_months,
             "source": cfg.sources["horizon_months"],
             "text": f"Customer value = monthly {revenue_col} x {cfg.horizon_months} months."
             if unit == "revenue" else "No revenue column: values count customers saved."},
            {"name": "max_discount", "value": cfg.max_discount,
             "source": cfg.sources["max_discount"],
             "text": f"Offers above a {cfg.max_discount:.0%} discount are not recommended."},
            {"name": "decline_days", "value": cfg.decline_days,
             "source": cfg.sources["decline_days"],
             "text": f"An offer declined in the last {cfg.decline_days} days is not repeated."},
            {"name": "offer_cost", "value": None, "source": cost_source,
             "text": "Cost per acceptance = average cost among acceptors of each offer."
             if cost_source == "data" else "No cost column: offers are treated as free."},
            {"name": "retention_lift", "value": None, "source": "data",
             "text": "Only the extra retention of acceptors over decliners counts; acceptors "
                     "choose to accept, so this is an association, not a proven effect."},
            {"name": "p_churn", "value": None, "source": "data",
             "text": "P(churn) is the churn model's score (not yet calibrated; Phase 5d)."},
        ],
    })
    return table, summary
