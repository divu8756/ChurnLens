"""Retention offers (Phase 5b): reshape any offer layout into one long table.

Supported layouts (see OfferColumns in app/schema_validation.py):
1. one offer column (an offer name per row) + one accepted column (Yes/No),
2. one column holding a delimited list of offers ("Data pack; Cashback") and an
   accepted column that is either Yes/No or a delimited list of accepted offers,
3. one 0/1 column per offer (the column name is the offer), with accepted 0/1
   columns paired by position.
Blank cells mean no offer. Offer names come only from the data; none are invented.
"""

import re
from typing import Any

import numpy as np
import pandas as pd

from app.schema_validation import OfferColumns
from app.stats.common import jsonable

LONG_COLUMNS = ["customer_id", "offer", "accepted", "offer_date"]
DELIMITERS = re.compile(r"\s*[;,|\n]\s*")
TRUE_VALUES = {"1", "1.0", "yes", "y", "true", "t", "accepted", "redeemed"}
FALSE_VALUES = {"0", "0.0", "no", "n", "false", "f"}


def _clean_name(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value is pd.NA:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _flag(value: Any) -> bool | None:
    """True/False for yes-no style cells, None when the cell is not a flag."""
    name = _clean_name(value)
    if name is None:
        return None
    lowered = name.lower()
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    return None


def _split(value: Any) -> list[str]:
    name = _clean_name(value)
    if name is None:
        return []
    return [part for part in (_clean_name(p) for p in DELIMITERS.split(name)) if part]


def _is_flag_column(series: pd.Series) -> bool:
    values = [v for v in series.tolist() if _clean_name(v) is not None]
    return bool(values) and all(_flag(v) is not None for v in values)


def _canonical_names(names: pd.Series) -> pd.Series:
    """Unify spellings that differ only in case: the most common spelling wins, and a tie
    goes to the one that sorts first (capitalised before lower case), so it is stable."""
    counts = names.value_counts()
    canonical: dict[str, str] = {}
    for name in sorted(counts.index, key=lambda n: (-counts[n], n)):
        canonical.setdefault(name.casefold(), name)
    return names.map(lambda n: canonical[n.casefold()])


def reshape_offers(frame: pd.DataFrame, offer_columns: dict[str, Any] | OfferColumns | None,
                   id_column: str | None = None) -> pd.DataFrame:
    """One row per (customer, offer shown): customer_id, offer, accepted (0/1), offer_date."""
    if not offer_columns:
        return pd.DataFrame(columns=LONG_COLUMNS)
    cols = OfferColumns.model_validate(offer_columns) if isinstance(offer_columns, dict) \
        else offer_columns
    ids = (frame[id_column].astype(str) if id_column and id_column in frame.columns
           else pd.Series(frame.index.astype(str), index=frame.index))
    dates = (pd.to_datetime(frame[cols.date], errors="coerce") if cols.date
             else pd.Series(pd.NaT, index=frame.index))

    rows: list[tuple[str, str, int, Any]] = []
    if isinstance(cols.shown, list):  # layout 3: one 0/1 column per offer
        accepted_cols: list[str | None] = (list(cols.accepted) if isinstance(cols.accepted, list)
                                           else [None] * len(cols.shown))
        for shown_col, accepted_col in zip(cols.shown, accepted_cols, strict=True):
            offer = _clean_name(shown_col) or shown_col
            for idx, value in frame[shown_col].items():
                if _flag(value) is not True:
                    continue
                took = accepted_col is not None and _flag(frame.at[idx, accepted_col]) is True
                rows.append((ids[idx], offer, int(took), dates[idx]))
    else:  # layouts 1 and 2: names (possibly a delimited list) in one column
        accepted = frame[cols.accepted] if isinstance(cols.accepted, str) else None
        flag_style = accepted is not None and _is_flag_column(accepted)
        for idx, value in frame[cols.shown].items():
            offers = _split(value)
            if not offers:
                continue
            if accepted is None:
                taken: set[str] = set()
            elif flag_style:
                taken = set(offers) if _flag(accepted[idx]) is True else set()
            else:
                taken = {o.casefold() for o in _split(accepted[idx])}
            for offer in dict.fromkeys(offers):
                took = offer in taken or offer.casefold() in taken
                rows.append((ids[idx], offer, int(took), dates[idx]))

    long = pd.DataFrame(rows, columns=LONG_COLUMNS)
    if long.empty:
        return pd.DataFrame(columns=LONG_COLUMNS)
    long["offer"] = _canonical_names(long["offer"])
    long["accepted"] = long["accepted"].astype(int)
    long = long.drop_duplicates(["customer_id", "offer"], keep="first")
    return long.sort_values(["customer_id", "offer"], kind="stable").reset_index(drop=True)


def offer_catalog(long: pd.DataFrame, offer_columns: dict[str, Any] | None) -> dict[str, Any]:
    """Offers that exist in the data, with how often each was shown and accepted."""
    offers = []
    for offer, group in long.groupby("offer", sort=True):
        offers.append({"offer": str(offer), "customers_shown": int(len(group)),
                       "accepted": int(group["accepted"].sum())})
    return jsonable({"offers": offers, "n_offers": len(offers),
                     "customers_offered": int(long["customer_id"].nunique()),
                     "source_columns": offer_columns})


# ------------------------------------------------------------------ effectiveness (T5b.2)

CUTOFF_NAME = re.compile(r"snapshot|as_?of|cutoff|observation|extract", re.I)
MIN_TEST_SHOWN = 20  # customers shown an offer before we test accepted x churned
BIAS_GAP = 0.05  # absolute gap in mean predicted churn risk that triggers the warning


def id_column(schema: dict[str, Any]) -> str | None:
    ids = schema.get("id_columns") or []
    return ids[0] if ids else None


def customer_ids(frame: pd.DataFrame, schema: dict[str, Any]) -> pd.Series:
    """The same customer keys reshape_offers() and the predictions table use."""
    col = id_column(schema)
    if col and col in frame.columns:
        return frame[col].astype(str)
    return pd.Series(frame.index.astype(str), index=frame.index)


def cutoff_column(frame: pd.DataFrame, schema: dict[str, Any]) -> str | None:
    """A date column that marks when the data was observed (snapshot, as-of, cutoff)."""
    offers = set(OfferColumns.model_validate(schema["offer_columns"]).all_columns()) \
        if schema.get("offer_columns") else set()
    for col in frame.columns:
        if str(col) in offers or not CUTOFF_NAME.search(str(col)):
            continue
        parsed = pd.to_datetime(frame[col], errors="coerce")
        if parsed.notna().mean() > 0.95:
            return str(col)
    return None


def leakage_filter(long: pd.DataFrame, frame: pd.DataFrame, schema: dict[str, Any],
                   offers: OfferColumns) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Keep only offers sent on or before the observation cutoff; explain what was checked."""
    info: dict[str, Any] = {"offer_date_column": offers.date, "cutoff_column": None,
                            "dropped_after_cutoff": 0, "warnings": []}
    if not offers.date:
        info["warnings"].append(
            "No offer date column: the analysis cannot check that offers were sent before "
            "churn was measured, so an offer sent after a customer left could look effective.")
        return long, info
    cutoff = cutoff_column(frame, schema)
    if cutoff is None:
        info["warnings"].append(
            "No observation date column (snapshot, as-of or cutoff) was found, so offers sent "
            "after churn was measured cannot be ruled out.")
        return long, info
    info["cutoff_column"] = cutoff
    cutoffs = pd.Series(pd.to_datetime(frame[cutoff], errors="coerce").to_numpy(),
                        index=customer_ids(frame, schema).to_numpy())
    cutoffs = cutoffs[~cutoffs.index.duplicated()]
    limit = long["customer_id"].map(cutoffs)
    late = long["offer_date"].notna() & limit.notna() & (long["offer_date"] > limit)
    info["dropped_after_cutoff"] = int(late.sum())
    if late.any():
        info["warnings"].append(
            f"{int(late.sum())} offers dated after {cutoff} were left out (they could not "
            "have influenced the churn being measured).")
    return long[~late].reset_index(drop=True), info


def prepare(frame: pd.DataFrame, schema: dict[str, Any]
            ) -> tuple[pd.DataFrame, dict[str, Any]] | None:
    """Long offer table after the leakage filter, or None when there are no offer columns."""
    if not schema.get("offer_columns"):
        return None
    offers = OfferColumns.model_validate(schema["offer_columns"])
    long = reshape_offers(frame, offers, id_column(schema))
    return leakage_filter(long, frame, schema, offers)


def offer_tests(frame: pd.DataFrame, schema: dict[str, Any]) -> list[dict[str, Any]]:
    """Accepted vs declined x churned, per offer, among customers shown it.

    Returned untested for BH: run_hypothesis_tests adds them to its family."""
    from app.stats.hypothesis import categorical_test  # avoid an import cycle

    prepared = prepare(frame, schema)
    if prepared is None:
        return []
    long, _ = prepared
    y = pd.Series(frame[schema["target_column"]].astype(int).to_numpy(),
                  index=customer_ids(frame, schema).to_numpy())
    y = y[~y.index.duplicated()]
    tests = []
    for offer, group in long.groupby("offer", sort=True):
        churn = group["customer_id"].map(y)
        if len(group) < MIN_TEST_SHOWN or group["accepted"].nunique() < 2 or churn.nunique() < 2:
            continue
        accepted = pd.Series(np.where(group["accepted"] == 1, "Accepted", "Declined"),
                             index=group.index)
        test = categorical_test(accepted, churn.astype(int), f"Offer: {offer}")
        test.update({
            "kind": "offer",
            "offer": str(offer),
            "h0": f"Among customers shown {offer}, churn is the same whether they accepted "
                  "it or not.",
            "h1": f"Among customers shown {offer}, churn differs between those who accepted "
                  "it and those who did not.",
        })
        tests.append(test)
    return tests


def _cell(churn: pd.Series) -> dict[str, Any]:
    n = int(churn.notna().sum())
    churned = int(churn.sum()) if n else 0
    return {"n": n, "churned": churned, "churn_rate": churned / n if n else None}


def _offer_row(group: pd.DataFrame, churn: pd.Series) -> dict[str, Any]:
    took = group["accepted"] == 1
    shown = int(len(group))
    return {
        "shown": shown,
        "accepted": int(took.sum()),
        "acceptance_rate": float(took.mean()) if shown else None,
        "acceptors": _cell(churn[took.to_numpy()]),
        "decliners": _cell(churn[~took.to_numpy()]),
    }


def run_offer_effectiveness(frame: pd.DataFrame, schema: dict[str, Any],
                            segment_labels: np.ndarray | None = None,
                            segments: dict[str, Any] | None = None,
                            probabilities: pd.Series | None = None,
                            hypothesis_results: dict[str, Any] | None = None
                            ) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """(offer_catalog, offer_effectiveness), or None when there are no offer columns."""
    prepared = prepare(frame, schema)
    if prepared is None:
        return None
    long, leakage = prepared
    ids = customer_ids(frame, schema)
    y = pd.Series(frame[schema["target_column"]].astype(int).to_numpy(), index=ids.to_numpy())
    y = y[~y.index.duplicated()]
    offered = set(long["customer_id"])
    never = ~ids.isin(offered).to_numpy()
    churn_all = frame[schema["target_column"]].astype(int).to_numpy()

    seg_of = None
    labels: dict[int, str] = {}
    if segment_labels is not None and len(segment_labels) == len(frame):
        seg_of = pd.Series(segment_labels, index=ids.to_numpy())
        seg_of = seg_of[~seg_of.index.duplicated()]
        labels = {int(s["segment"]): s["label"] for s in (segments or {}).get("segments", [])}

    tests = {t.get("offer"): t for t in (hypothesis_results or {}).get("tests", [])
             if t.get("kind") == "offer"}
    rows = []
    for offer, group in long.groupby("offer", sort=True):
        churn = group["customer_id"].map(y)
        row = {"offer": str(offer), **_offer_row(group, churn)}
        test = tests.get(str(offer))
        row["test"] = ({"test_name": test["test_name"], "p_value": test["p_value"],
                        "p_adjusted": test["p_adjusted"], "significant": test["significant"],
                        "variable": test["variable"]} if test else None)
        if seg_of is not None:
            seg = group["customer_id"].map(seg_of)
            row["segments"] = [
                {"segment": int(s), "label": labels.get(int(s), f"Segment {int(s) + 1}"),
                 **_offer_row(group[(seg == s).to_numpy()], churn[(seg == s).to_numpy()])}
                for s in sorted(seg.dropna().unique())]
        rows.append(row)

    warnings = list(leakage["warnings"])
    bias = None
    if probabilities is not None and offered and never.any():
        risk = probabilities.reindex(ids.to_numpy()).to_numpy(dtype=float)
        offered_risk = float(np.nanmean(risk[~never]))
        never_risk = float(np.nanmean(risk[never]))
        gap = offered_risk - never_risk
        bias = {"offered_mean_risk": offered_risk, "never_offered_mean_risk": never_risk,
                "gap": gap, "threshold": BIAS_GAP, "flagged": bool(gap >= BIAS_GAP)}
        if gap >= BIAS_GAP:
            warnings.append(
                f"Offered customers were riskier to begin with (mean predicted churn "
                f"{offered_risk:.1%} vs {never_risk:.1%} for customers never offered), so raw "
                "comparisons with never-offered customers understate the offers' effect. "
                "Compare acceptors with decliners, or use a holdout group.")

    effectiveness = jsonable({
        "offers": rows,
        "never_offered": _cell(pd.Series(churn_all[never])),
        "offered": _cell(pd.Series(churn_all[~never])),
        "leakage": leakage,
        "selection_bias": bias,
        "warnings": warnings,
        "note": "Acceptors chose to accept, so their lower churn is an association, not proof "
                "the offer caused it. A randomised holdout (Phase 5c) measures the effect.",
    })
    return offer_catalog(long, schema.get("offer_columns")), effectiveness
