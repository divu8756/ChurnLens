"""Business metrics for one analysed session (SPEC v1.3), recomputed in Python on every
request so edited assumptions never touch the browser's maths (CLAUDE.md rule 21)."""

from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from app.catalog import OFFERS_FILE, load_catalogue
from app.experiments.data import NotAnalysed, plan_column, session_customers
from app.stats import business_metrics as bm
from app.stats.common import jsonable


class OfferOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")
    acceptance: float | None = Field(default=None, ge=0, le=1)
    save_rate: float | None = Field(default=None, ge=0, le=1)
    cost: float | None = Field(default=None, ge=0)


class BusinessAssumptions(BaseModel):
    """Edits from the Business Impact tab; omitted fields keep their defaults."""

    model_config = ConfigDict(extra="forbid")
    months_remaining: float | None = Field(default=None, ge=1, le=60)
    offers: dict[str, OfferOverride] = Field(default_factory=dict, max_length=50)
    relative_lift: float | None = Field(default=None, ge=0.01, le=0.9)
    alpha: float | None = Field(default=None, gt=0, le=0.2)
    power: float | None = Field(default=None, ge=0.5, lt=1)


def disabled(reason: str) -> dict[str, Any]:
    return {"enabled": False, "reason": reason}


def segment_labels(customers: pd.DataFrame, schema: dict[str, Any]) -> pd.Series:
    """Risk band x plan type (contract) when a plan column exists, else risk band."""
    plan = plan_column(schema, customers)
    if not plan:
        return customers["risk_band"].astype(str)
    return customers["risk_band"].astype(str) + " / " + customers[plan].astype(str)


def compute(values: dict[str, Any], evidence: dict[str, dict[str, Any]],
            assumptions: BusinessAssumptions | None = None) -> dict[str, Any]:
    """Business metrics for a session's graph state values."""
    a = assumptions or BusinessAssumptions()
    schema = values.get("confirmed_schema") or {}
    try:
        customers, _ = session_customers(values)
    except NotAnalysed as exc:
        return disabled(str(exc))
    arpu_col = schema.get("revenue_column")
    if not arpu_col or arpu_col not in customers.columns:
        return disabled("No monthly revenue (ARPU) column was confirmed, so revenue at risk "
                        "and offer savings cannot be computed. Model metrics still work; "
                        "confirm a revenue column to enable them.")
    months = a.months_remaining if a.months_remaining is not None else bm.DEFAULT_MONTHS
    months_source = "user" if a.months_remaining is not None else "default"

    p = customers["churn_probability"].to_numpy(dtype=float)
    arpu = pd.to_numeric(customers[arpu_col], errors="coerce").fillna(0.0).to_numpy(float)
    catalogue = load_catalogue(OFFERS_FILE)
    overrides = bm.data_overrides(values.get("offer_effectiveness"), evidence)
    user = {name: o.model_dump(exclude_none=True) for name, o in a.offers.items()}
    terms = bm.offer_terms(catalogue, overrides, user)

    _, risk = bm.revenue_at_risk(customers, p, arpu_col, months)
    table, warnings = bm.next_best_offer(customers, p, arpu, terms, months)
    unknown = sorted(set(a.offers) - {t.name for t in terms})
    if unknown:
        warnings.append(f"Assumptions for unknown offers were ignored: {', '.join(unknown)}.")
    roi = bm.offer_roi_by_segment(table, segment_labels(customers, schema))
    result = bm.summarise(table, risk, terms, roi, warnings, months, months_source)
    top = table.sort_values("expected_saving", ascending=False, kind="stable").head(50)
    result["next_best_offers"] = jsonable(top.to_dict("records"))
    targeted = (table["best_offer"] != bm.NO_OFFER).to_numpy()
    label = "customers with an offer" if targeted.any() else "all customers"
    outcomes = customers["actual_churn"].to_numpy()
    result["ab_plan"] = bm.ab_plan(outcomes[targeted] if targeted.any() else outcomes, label,
                                   a.relative_lift, a.alpha, a.power)
    result["assumptions"] += [x for x in result["ab_plan"]["assumptions"] if x["name"] != "p1"]
    return result
