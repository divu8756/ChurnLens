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


# ------------------------------------------------------------ effectiveness (T5b.2)

from scipy import stats  # noqa: E402

from app.schema_validation import OfferColumns  # noqa: E402
from app.stats.hypothesis import run_hypothesis_tests  # noqa: E402
from app.stats.offers import leakage_filter, offer_tests, run_offer_effectiveness  # noqa: E402


def tiny() -> tuple[pd.DataFrame, dict]:
    """10 customers: 6 shown "Cashback" (3 accepted), 4 never offered."""
    frame = pd.DataFrame({
        "id": [f"C{i}" for i in range(10)],
        "Offer": ["Cashback"] * 6 + [None] * 4,
        "Accepted": ["Yes", "Yes", "Yes", "No", "No", "No"] + [None] * 4,
        "OfferDate": ["2026-01-10"] * 5 + ["2026-07-15"] + [None] * 4,
        "Snapshot": ["2026-06-30"] * 10,
        "Churn": [0, 0, 1, 1, 1, 0, 0, 0, 0, 1],
    })
    schema = {"target_column": "Churn", "positive_label": "1", "id_columns": ["id"],
              "offer_columns": {"shown": "Offer", "accepted": "Accepted", "date": "OfferDate"}}
    return frame, schema


def test_rates_match_a_hand_count():
    frame, schema = tiny()
    frame["OfferDate"] = "2026-01-10"  # nothing dropped here
    frame.loc[6:, "OfferDate"] = None
    _, eff = run_offer_effectiveness(frame, schema)
    row = eff["offers"][0]
    # Accepted C0, C1, C2 -> churned C2 only; declined C3, C4, C5 -> churned C3, C4.
    assert row["shown"] == 6 and row["accepted"] == 3 and row["acceptance_rate"] == 0.5
    assert row["acceptors"] == {"n": 3, "churned": 1, "churn_rate": 1 / 3}
    assert row["decliners"] == {"n": 3, "churned": 2, "churn_rate": 2 / 3}
    assert eff["never_offered"] == {"n": 4, "churned": 1, "churn_rate": 0.25}
    assert eff["offered"] == {"n": 6, "churned": 3, "churn_rate": 0.5}


def test_leakage_filter_drops_offers_after_the_cutoff():
    frame, schema = tiny()
    offers = OfferColumns.model_validate(schema["offer_columns"])
    long = reshape_offers(frame, offers, "id")
    kept, info = leakage_filter(long, frame, schema, offers)
    assert info["cutoff_column"] == "Snapshot" and info["dropped_after_cutoff"] == 1
    assert "C5" not in set(kept["customer_id"]) and len(kept) == 5
    assert "dated after Snapshot" in info["warnings"][0]


def test_missing_offer_date_or_cutoff_is_warned_not_hidden():
    frame, schema = tiny()
    no_date = {**schema, "offer_columns": {"shown": "Offer", "accepted": "Accepted"}}
    _, eff = run_offer_effectiveness(frame, no_date)
    assert any("No offer date column" in w for w in eff["warnings"])
    _, eff = run_offer_effectiveness(frame.drop(columns="Snapshot"), schema)
    assert any("No observation date column" in w for w in eff["warnings"])


def test_selection_bias_warning_fires_only_when_offered_customers_were_riskier():
    frame, schema = tiny()
    risky = pd.Series([0.8] * 6 + [0.2] * 4, index=frame["id"])
    _, eff = run_offer_effectiveness(frame, schema, probabilities=risky)
    assert eff["selection_bias"]["flagged"] is True
    # C5's offer is after the cutoff, so C5 counts as never offered: 0.8 - (0.8 + 4 * 0.2) / 5
    assert eff["selection_bias"]["gap"] == pytest.approx(0.48)
    assert any("riskier to begin with" in w for w in eff["warnings"])
    even = pd.Series([0.3] * 10, index=frame["id"])
    _, eff = run_offer_effectiveness(frame, schema, probabilities=even)
    assert eff["selection_bias"]["flagged"] is False
    assert not any("riskier" in w for w in eff["warnings"])


def _offer_data(n: int = 400) -> tuple[pd.DataFrame, dict]:
    rng = np.random.default_rng(42)
    shown = rng.choice(["Cashback", "Data pack", ""], n, p=[0.4, 0.4, 0.2])
    accepted = np.where(shown == "", "", rng.choice(["Yes", "No"], n))
    churn = rng.binomial(1, np.where(accepted == "Yes", 0.15, 0.35))
    frame = pd.DataFrame({"id": [f"C{i}" for i in range(n)], "Offer": shown,
                          "Accepted": accepted, "tenure": rng.integers(1, 72, n),
                          "Churn": churn})
    schema = {"target_column": "Churn", "positive_label": "1", "id_columns": ["id"],
              "offer_columns": {"shown": "Offer", "accepted": "Accepted"}}
    return frame, schema


def test_offer_tests_match_scipy_and_join_the_bh_family():
    frame, schema = _offer_data()
    tests = offer_tests(frame, schema)
    assert [t["offer"] for t in tests] == ["Cashback", "Data pack"]
    for test in tests:
        shown = frame[frame["Offer"] == test["offer"]]
        table = pd.crosstab(shown["Accepted"] == "Yes", shown["Churn"]).to_numpy()
        chi2, p, _, _ = stats.chi2_contingency(table, correction=False)
        assert test["statistic"] == pytest.approx(chi2, abs=1e-9)
        assert test["p_value"] == pytest.approx(p, abs=1e-9)
        assert test["kind"] == "offer" and "accepted it" in test["h1"]
    result = run_hypothesis_tests(frame, schema)
    kinds = [t["kind"] for t in result["tests"]]
    assert kinds.count("offer") == 2 and result["n_tests"] == len(kinds)
    assert not any(t["variable"] in ("Offer", "Accepted") for t in result["tests"])


def test_no_offer_columns_skips_cleanly():
    frame, schema = _offer_data()
    schema = {**schema, "offer_columns": None}
    assert offer_tests(frame, schema) == []
    assert run_offer_effectiveness(frame, schema) is None
