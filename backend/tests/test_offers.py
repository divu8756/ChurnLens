import numpy as np
import pandas as pd
import pytest

from app.schema_validation import ConfirmedSchema, validate_schema
from app.stats import profiling
from app.stats.common import feature_columns
from app.stats.offers import LONG_COLUMNS, offer_catalog, reshape_offers

# The same four customers in three layouts:
# C1 was shown Data pack and accepted it; C2 was shown Cashback and declined;
# C3 had no offer; C4 was shown Data pack and declined.
IDS = ["C1", "C2", "C3", "C4"]
DATES = ["2026-01-05", "2026-01-06", None, "2026-01-07"]
EXPECTED = pd.DataFrame({
    "customer_id": ["C1", "C2", "C4"],
    "offer": ["Data pack", "Cashback", "Data pack"],
    "accepted": [1, 0, 0],
    "offer_date": pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-07"]),
})


def single_column() -> tuple[pd.DataFrame, dict]:
    frame = pd.DataFrame({"id": IDS, "Offer": ["Data pack", " cashback", "", "data  pack "],
                          "Accepted": ["Yes", "No", None, "No"], "Sent": DATES})
    # "cashback" ties with "Cashback" (C5); ties go to the spelling that sorts first.
    frame.loc[len(frame)] = ["C5", "Cashback", "No", "2026-01-08"]
    return frame, {"shown": "Offer", "accepted": "Accepted", "date": "Sent"}


def delimited() -> tuple[pd.DataFrame, dict]:
    frame = pd.DataFrame({"id": IDS, "Offers": ["Data pack", "Cashback", None, "Data pack"],
                          "Taken": ["Data pack", "", "", ""], "Sent": DATES})
    return frame, {"shown": "Offers", "accepted": "Taken", "date": "Sent"}


def wide() -> tuple[pd.DataFrame, dict]:
    frame = pd.DataFrame({"id": IDS, "Data pack": [1, 0, 0, 1], "Cashback": [0, 1, 0, 0],
                          "Data pack taken": [1, 0, 0, 0], "Cashback taken": [0, 0, 0, 0],
                          "Sent": DATES})
    return frame, {"shown": ["Data pack", "Cashback"],
                   "accepted": ["Data pack taken", "Cashback taken"], "date": "Sent"}


def _core(long: pd.DataFrame) -> pd.DataFrame:
    return long[long["customer_id"].isin(IDS)].reset_index(drop=True)


@pytest.mark.parametrize("layout", [single_column, delimited, wide])
def test_every_layout_gives_the_same_long_table(layout):
    frame, cols = layout()
    long = _core(reshape_offers(frame, cols, id_column="id"))
    pd.testing.assert_frame_equal(long, EXPECTED, check_dtype=False)
    assert list(long.columns) == LONG_COLUMNS


def test_names_are_trimmed_and_case_unified():
    frame, cols = single_column()
    long = reshape_offers(frame, cols, id_column="id")
    assert set(long["offer"]) == {"Data pack", "Cashback"}  # never an invented name


def test_mixed_delimiters_and_lists_of_accepted_offers():
    frame = pd.DataFrame({"id": ["A", "B"],
                          "Offers": ["Data pack; Cashback", "Cashback|Data pack,OTT"],
                          "Taken": ["cashback", "OTT; Data pack"]})
    long = reshape_offers(frame, {"shown": "Offers", "accepted": "Taken"}, id_column="id")
    got = {(r.customer_id, r.offer): r.accepted for r in long.itertuples()}
    assert got == {("A", "Cashback"): 1, ("A", "Data pack"): 0, ("B", "Cashback"): 0,
                   ("B", "Data pack"): 1, ("B", "OTT"): 1}


def test_blank_cells_mean_no_offer_and_no_columns_skips_cleanly():
    frame = pd.DataFrame({"id": ["A"], "Offer": ["  "], "Accepted": ["Yes"]})
    assert reshape_offers(frame, {"shown": "Offer", "accepted": "Accepted"}, "id").empty
    empty = reshape_offers(frame, None, "id")
    assert empty.empty and list(empty.columns) == LONG_COLUMNS


def test_catalog_counts_only_offers_in_the_data():
    frame, cols = delimited()
    catalog = offer_catalog(reshape_offers(frame, cols, "id"), cols)
    assert catalog["offers"] == [
        {"offer": "Cashback", "customers_shown": 1, "accepted": 0},
        {"offer": "Data pack", "customers_shown": 2, "accepted": 1},
    ]
    assert catalog["customers_offered"] == 3


def test_telco_offer_columns_are_detected_and_excluded_from_features():
    frame = pd.read_csv(profiling.__file__.replace("app/stats/profiling.py",
                                                   "sample_data/telco_churn.csv"))
    schema = profiling.heuristic_schema(frame)
    offers = schema["offer_columns"]
    assert offers == {"shown": "OfferShown", "accepted": "OfferAccepted", "date": "OfferDate",
                      "cost": "OfferCost", "group": "CampaignGroup",
                      "other": ["OfferChannel", "OfferClicked"]}
    cols = feature_columns(frame, schema)
    used = set(cols["numeric"]) | set(cols["categorical"])
    assert not used & {"OfferShown", "OfferCost", "CampaignGroup", "OfferClicked"}
    long = reshape_offers(frame, offers, "customerID")
    assert long["offer"].nunique() == 6


def test_no_offer_names_means_no_proposal():
    frame = pd.DataFrame({"id": range(5), "tenure": np.arange(5),
                          "Churn": ["Yes", "No"] * 2 + ["No"]})
    assert profiling.likely_offer_columns(frame) is None


def test_confirmed_offer_columns_are_validated():
    frame = pd.DataFrame({"id": ["a", "b"], "Offer": ["x", ""], "Churn": ["Yes", "No"]})
    base = {"target_column": "Churn", "positive_label": "Yes", "id_columns": ["id"]}
    ok = ConfirmedSchema(**base, offer_columns={"shown": "Offer"})
    assert validate_schema(ok, frame) == []
    missing = ConfirmedSchema(**base, offer_columns={"shown": "Promo"})
    assert "Offer columns not found: Promo." in validate_schema(missing, frame)
    clash = ConfirmedSchema(**base, offer_columns={"shown": "Churn"})
    assert any("cannot also be the target" in p for p in validate_schema(clash, frame))
    uneven = ConfirmedSchema(**base,
                             offer_columns={"shown": ["Offer", "id"], "accepted": ["Offer"]})
    assert any("one accepted column per offer" in p for p in validate_schema(uneven, frame))
