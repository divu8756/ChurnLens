import numpy as np
import pandas as pd
import pytest

from app.stats.nbo import (
    NO_OFFER,
    NboConfig,
    expected_value,
    offer_discount,
    score_next_best_offers,
    smoothed,
)
from app.stats.offers import reshape_offers


def test_expected_value_by_hand():
    # 0.6 churn x 0.5 accept x 0.2 lift x 1,200 value - 0.5 accept x 20 cost = 72 - 10
    assert expected_value(0.6, 0.5, 0.2, 1200, 20) == pytest.approx(62.0)
    assert expected_value(0.1, 0.5, 0.5, 10, 20) == pytest.approx(0.25 - 10)


def test_laplace_smoothing_keeps_small_cells_off_0_and_1():
    assert smoothed(0, 0, 1) == 0.5
    assert smoothed(3, 3, 1) == pytest.approx(0.8)
    assert smoothed(0, 3, 1) == pytest.approx(0.2)


def test_discount_is_read_from_the_offer_name():
    assert offer_discount("10% loyalty discount (3 mo)") == pytest.approx(0.10)
    assert offer_discount("25% off for 6 months") == pytest.approx(0.25)
    assert offer_discount("Free 10GB data booster") is None


def data(n: int = 600, cost: float = 5.0, seed: int = 42):
    rng = np.random.default_rng(seed)
    tenure = rng.integers(1, 72, n)
    shown = rng.choice(["Cashback", "Data pack", "30% off", ""], n, p=[0.3, 0.3, 0.1, 0.3])
    accepted = np.where(shown == "", "", np.where(rng.random(n) < 0.4 + tenure / 300, "Yes", "No"))
    churn = rng.binomial(1, np.where(accepted == "Yes", 0.15, 0.35))
    frame = pd.DataFrame({
        "id": [f"C{i:04d}" for i in range(n)], "tenure": tenure,
        "MonthlyCharges": rng.normal(70, 15, n).round(2), "Offer": shown, "Accepted": accepted,
        "OfferCost": np.where(accepted == "Yes", cost, 0.0), "Churn": churn})
    schema = {"target_column": "Churn", "positive_label": "1", "id_columns": ["id"],
              "revenue_column": "MonthlyCharges",
              "offer_columns": {"shown": "Offer", "accepted": "Accepted", "cost": "OfferCost"}}
    predictions = pd.DataFrame({"customer_id": frame["id"],
                                "churn_probability": rng.uniform(0, 1, n).round(3)})
    predictions["risk_band"] = np.select([predictions["churn_probability"] >= 0.6,
                                          predictions["churn_probability"] >= 0.3],
                                         ["High", "Medium"], "Low")
    return frame, schema, predictions


def run(frame, schema, predictions, **cfg):
    long = reshape_offers(frame, schema["offer_columns"], "id")
    exclude = ["Offer", "Accepted", "OfferCost"]
    return score_next_best_offers(frame, schema, long, predictions, None, exclude,
                                  NboConfig(**cfg))


def test_scores_medium_and_high_risk_customers_with_catalogue_offers_only():
    frame, schema, predictions = data()
    table, summary = run(frame, schema, predictions)
    at_risk = predictions[predictions["risk_band"].isin(["High", "Medium"])]
    assert len(table) == len(at_risk) == summary["customers_scored"]
    assert set(table["best_offer"]) <= {"Cashback", "Data pack", NO_OFFER}  # 30% off > 20% cap
    assert summary["excluded_by_discount"] == ["30% off"]
    assert summary["value_unit"] == "revenue"
    assert {a["source"] for a in summary["assumptions"]} <= {"default", "user", "data"}
    model = summary["offer_models"]["Cashback"]
    assert model["low_data"] is False and 0 <= model["roc_auc"] <= 1


def test_expected_value_matches_its_inputs():
    frame, schema, predictions = data()
    table, _ = run(frame, schema, predictions)
    row = table[table["best_offer"] != NO_OFFER].iloc[0]
    value = frame.loc[frame["id"] == row["customer_id"], "MonthlyCharges"].iloc[0] * 12
    lift = row["p_stay_if_accepted"] - row["p_stay_if_declined"]
    assert row["retention_lift"] == pytest.approx(max(0.0, lift))
    ev = expected_value(row["p_churn"], row["p_accept"], row["retention_lift"], value,
                        row["offer_cost"])
    assert row["expected_value"] == pytest.approx(ev, abs=1e-3)
    assert row["customer_value"] == pytest.approx(value, abs=0.01)


def test_no_offer_when_every_offer_is_negative():
    frame, schema, predictions = data(cost=100_000.0)
    table, summary = run(frame, schema, predictions)
    assert (table["best_offer"] == NO_OFFER).all()
    assert (table["expected_value"] == 0).all()
    assert table["no_offer_reason"].str.contains("negative").all()
    assert summary["by_offer"] == [{"offer": NO_OFFER, "customers": len(table),
                                    "expected_value": 0.0}]


def test_an_offer_the_customer_declined_is_not_repeated():
    frame, schema, predictions = data()
    declined = frame[(frame["Offer"] == "Cashback") & (frame["Accepted"] == "No")]["id"]
    table, _ = run(frame, schema, predictions)
    picked = table.set_index("customer_id").reindex(declined).dropna(subset=["best_offer"])
    assert len(picked) > 0
    assert (picked["best_offer"] != "Cashback").all()
    assert (picked["runner_up"].fillna("") != "Cashback").all()


def test_results_are_reproducible():
    frame, schema, predictions = data()
    first, _ = run(frame, schema, predictions)
    second, _ = run(frame, schema, predictions)
    pd.testing.assert_frame_equal(first, second)


def test_small_offers_fall_back_to_the_segment_rate():
    frame, schema, predictions = data()
    _, summary = run(frame, schema, predictions, min_exposures=10_000)
    assert all(m["low_data"] for m in summary["offer_models"].values())


def test_an_offer_with_no_retention_effect_is_never_recommended():
    frame, schema, predictions = data()
    # Make "Data pack" useless: acceptors churn exactly like decliners.
    shown = frame["Offer"] == "Data pack"
    rng = np.random.default_rng(7)
    frame.loc[shown, "Churn"] = rng.binomial(1, 0.3, shown.sum())
    frame.loc[shown & (frame["Accepted"] == "Yes"), "Churn"] = 1  # acceptors even worse
    table, _ = run(frame, schema, predictions)
    assert "Data pack" not in set(table["best_offer"])


def test_confirmed_offer_columns_with_no_offers_do_not_crash():
    from app.stats.offers import offer_tests, run_offer_effectiveness
    frame, schema, predictions = data()
    frame["Offer"] = ""
    frame["Accepted"] = ""
    assert offer_tests(frame, schema) == []
    catalog, eff = run_offer_effectiveness(frame, schema, probabilities=predictions.set_index(
        "customer_id")["churn_probability"])
    assert catalog["n_offers"] == 0 and eff["offers"] == [] and eff["selection_bias"] is None
    assert eff["never_offered"]["n"] == len(frame)
    table, summary = run(frame, schema, predictions)
    assert (table["best_offer"] == NO_OFFER).all()
    assert table["no_offer_reason"].eq("no eligible offers").all()
    assert summary["by_offer"][0]["offer"] == NO_OFFER
