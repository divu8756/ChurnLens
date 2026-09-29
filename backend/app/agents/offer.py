"""offer_node (Phase 5b): offer catalogue and effectiveness, Python only.

Runs after impact_node, only when offer columns were confirmed. Reads the churn
probabilities from the predictions table for the selection-bias check."""

from pathlib import Path
from typing import Any

import pandas as pd

from app.agents.modelling import treatment_columns
from app.config import get_settings
from app.graph.errors import FatalNodeError
from app.graph.state import ChurnState, ErrorEntry, ProgressEntry
from app.stats.nbo import NboConfig, score_next_best_offers
from app.stats.offers import prepare, run_offer_effectiveness

NBO_FILE = "next_best_offers.parquet"


def nbo_config() -> NboConfig:
    settings = get_settings()
    return NboConfig(horizon_months=settings.NBO_HORIZON_MONTHS,
                     max_discount=settings.NBO_MAX_DISCOUNT,
                     decline_days=settings.NBO_DECLINE_DAYS)


def _probabilities(path: str | None) -> pd.Series | None:
    if not path or not Path(path).exists():
        return None
    table = pd.read_parquet(path, columns=["customer_id", "churn_probability"])
    return table.drop_duplicates("customer_id").set_index("customer_id")["churn_probability"]


def offer_node(state: ChurnState) -> dict[str, Any]:
    if not state.clean_path or not state.confirmed_schema:
        raise FatalNodeError("Offer analysis needs cleaned data and a confirmed schema.")
    frame = pd.read_parquet(state.clean_path)
    labels = None
    assignments = (state.segments or {}).get("assignments_path")
    if assignments and Path(assignments).exists():
        labels = pd.read_parquet(assignments)["segment"].to_numpy()
    result = run_offer_effectiveness(frame, state.confirmed_schema, labels, state.segments,
                                     _probabilities(state.predictions_path),
                                     state.hypothesis_results)
    if result is None:
        return {"progress": [ProgressEntry(node="offer", status="skipped",
                                           detail="no offer columns")]}
    catalog, effectiveness = result
    update: dict[str, Any] = {"offer_catalog": catalog}
    errors: list[ErrorEntry] = []

    # Next best offer (T5b.3). Useful but not essential: a failure is recorded, not fatal.
    if state.predictions_path and Path(state.predictions_path).exists():
        try:
            prepared = prepare(frame, state.confirmed_schema)
            long = prepared[0] if prepared else pd.DataFrame()
            predictions = pd.read_parquet(state.predictions_path,
                                          columns=["customer_id", "churn_probability",
                                                   "risk_band"])
            table, summary = score_next_best_offers(
                frame, state.confirmed_schema, long, predictions, labels,
                exclude=treatment_columns(state), cfg=nbo_config())
            path = Path(state.clean_path).with_name(NBO_FILE)
            table.to_parquet(path, index=False)
            update["offer_recommendations_path"] = str(path)
            effectiveness["next_best_offer"] = summary
        except Exception as exc:  # noqa: BLE001 - reported to the user, run continues
            errors.append(ErrorEntry(node="offer", message=f"Next best offer failed: {exc}"))

    update["offer_effectiveness"] = effectiveness
    scored = (effectiveness.get("next_best_offer") or {}).get("customers_scored")
    detail = (f"{catalog['n_offers']} offers, {catalog['customers_offered']} customers offered"
              + (f", {scored} customers scored" if scored is not None else "")
              + (f", {len(effectiveness['warnings'])} warnings" if effectiveness["warnings"]
                 else ""))
    update["errors"] = errors
    update["progress"] = [ProgressEntry(node="offer", status="done", detail=detail)]
    return update
