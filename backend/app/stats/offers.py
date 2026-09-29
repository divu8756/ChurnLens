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
