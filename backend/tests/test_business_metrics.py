import textwrap

import numpy as np
import pandas as pd
import pytest

from app.catalog import (
    OFFERS_FILE,
    PRICING_FILE,
    CatalogueError,
    OfferSpec,
    load_catalogue,
    load_pricing,
)
from app.stats import business_metrics as bm

# 5 customers, hand-worked below (months_remaining = 12).
CUSTOMERS = pd.DataFrame({
    "customer_id": ["c1", "c2", "c3", "c4", "c5"],
    "risk_band": ["High", "Medium", "Low", "High", "Low"],
    "Contract": ["Month-to-month", "One year", "Month-to-month", "Month-to-month", "Two year"],
    "tenure": [3, 40, 10, 2, 60],
    "MonthlyCharges": [100.0, 50.0, 80.0, 10.0, 20.0],
})
P = np.array([0.8, 0.5, 0.2, 0.6, 0.05])
ARPU = CUSTOMERS["MonthlyCharges"].to_numpy()

SPECS = [
    OfferSpec(name="A", cost=10, assumed_acceptance_rate=0.5, assumed_save_rate=0.5),
    OfferSpec(name="B", cost=20, assumed_acceptance_rate=0.4, assumed_save_rate=0.8,
              eligible_segments=[{"column": "Contract", "in": ["Month-to-month"]}]),
    OfferSpec(name="C", cost=5, cost_basis="per_targeted", assumed_acceptance_rate=0.3,
              assumed_save_rate=0.5, eligible_segments=[{"risk_band": ["High"]}]),
]
# saving_A = 3 p ARPU - 5; saving_B = 3.84 p ARPU - 8 (M2M only); saving_C = 1.8 p ARPU - 5.
PA = P * ARPU  # [80, 25, 16, 6, 1]
EXPECTED = {
    "A": 3 * PA - 5,           # [235, 70, 43, 13, -2]
    "B": 3.84 * PA - 8,        # [299.2, (88), 53.44, 15.04, (-4.16)]
    "C": 1.8 * PA - 5,         # [139, ...,  5.8]
}


def terms():
    return bm.offer_terms(SPECS, {})


def test_revenue_at_risk_by_hand():
    values, summary = bm.revenue_at_risk(CUSTOMERS, P, "MonthlyCharges", 12)
    assert values == pytest.approx([960, 300, 192, 72, 12])
    assert summary["total"] == pytest.approx(1536)


def test_expected_saving_every_customer_and_offer():
    by_name = {o.name: o for o in terms()}
    for name, expected in EXPECTED.items():
        got = bm.expected_saving(P, ARPU, 12, by_name[name])
        assert got == pytest.approx(expected, abs=1e-9)
    assert EXPECTED["A"] == pytest.approx([235, 70, 43, 13, -2])
    assert EXPECTED["B"][[0, 2, 3]] == pytest.approx([299.2, 53.44, 15.04])
    assert EXPECTED["C"][[0, 3]] == pytest.approx([139, 5.8])


def test_next_best_offer_respects_eligibility_and_no_offer():
    table, warnings = bm.next_best_offer(CUSTOMERS, P, ARPU, terms(), 12)
    assert warnings == []
    assert table.best_offer.tolist() == ["B", "A", "B", "B", bm.NO_OFFER]
    assert table.expected_saving.tolist() == pytest.approx([299.2, 70, 53.44, 15.04, 0])
    assert table.runner_up.tolist() == ["A", None, "A", "A", None]
    # c2 is not month-to-month and not High: only A is eligible.
    assert table.eligible_offers.tolist() == [3, 1, 2, 3, 1]
    assert table.expected_cost.tolist() == pytest.approx([8, 5, 8, 8, 0])


def test_all_negative_savings_give_no_offer():
    pricey = bm.offer_terms([OfferSpec(name="X", cost=10_000, assumed_acceptance_rate=0.5)], {})
    table, _ = bm.next_best_offer(CUSTOMERS, P, ARPU, pricey, 12)
    assert (table.best_offer == bm.NO_OFFER).all() and (table.expected_saving == 0).all()


def test_rule_on_missing_column_skips_offer_with_warning():
    specs = [*SPECS, OfferSpec(name="D", cost=1, assumed_acceptance_rate=0.9,
                               eligible_segments=[{"column": "NPS", "min": 0, "max": 6}])]
    table, warnings = bm.next_best_offer(CUSTOMERS, P, ARPU, bm.offer_terms(specs, {}), 12)
    assert len(warnings) == 1 and "'D'" in warnings[0] and "NPS" in warnings[0]
    assert "D" not in set(table.best_offer)


def test_range_rule():
    specs = [OfferSpec(name="New", cost=0, assumed_acceptance_rate=0.5,
                       eligible_segments=[{"column": "tenure", "min": 0, "max": 12}])]
    masks, _ = bm.eligible_offers(CUSTOMERS, bm.offer_terms(specs, {}))
    assert masks["New"].tolist() == [True, False, True, True, False]


def test_simple_formula_is_a_special_case():
    offer = bm.offer_terms([OfferSpec(name="S", cost=7, cost_basis="per_targeted",
                                      assumed_acceptance_rate=0.3, assumed_save_rate=1.0)],
                           {})[0]
    got = bm.expected_saving(P, ARPU, 12, offer)
    assert got == pytest.approx(P * 0.3 * ARPU * 12 - 7, abs=1e-9)


def test_months_remaining_is_linear():
    offer = terms()[0]
    s6, s12, s24 = (bm.expected_saving(P, ARPU, m, offer) for m in (6, 12, 24))
    assert (s24 - s12) == pytest.approx(2 * (s12 - s6), abs=1e-9)
    with pytest.raises(ValueError):
        bm.revenue_at_risk(CUSTOMERS, P, "MonthlyCharges", 0)
    with pytest.raises(ValueError):
        bm.next_best_offer(CUSTOMERS, P, ARPU, terms(), 61)


def test_roi_by_segment():
    table, _ = bm.next_best_offer(CUSTOMERS, P, ARPU, terms(), 12)
    roi = {r["segment"]: r for r in bm.offer_roi_by_segment(table, CUSTOMERS["risk_band"])}
    assert roi["High"]["customers"] == 2
    assert roi["High"]["total_expected_saving"] == pytest.approx(299.2 + 15.04)
    assert roi["High"]["roi"] == pytest.approx((299.2 + 15.04) / 16)
    assert "Low" in roi and roi["Low"]["customers"] == 1  # c5 has no offer


def test_data_and_user_overrides_with_sources():
    effectiveness = {
        "offers": [{"offer": "a", "acceptance_rate": 0.2,
                    "acceptors": {"churn_rate": 0.2}, "decliners": {"churn_rate": 0.4}}],
        "next_best_offer": {"offer_costs": {"a": 12.0}},
    }
    evidence = {"b": {"retention_lift_per_acceptor": 0.1, "control_churn": 0.4,
                      "acceptance_rate": 0.45}}
    overrides = bm.data_overrides(effectiveness, evidence)
    assert overrides["a"] == {"label": "observational", "acceptance": 0.2, "save_rate": 0.5,
                              "cost": 12.0}
    assert overrides["b"]["save_rate"] == pytest.approx(0.25)
    assert overrides["b"]["label"] == "experiment-proven"
    t = {o.name: o for o in bm.offer_terms(SPECS, overrides, {"A": {"cost": 3.0}})}
    assert t["A"].acceptance == 0.2 and t["A"].sources["acceptance"] == "data"
    assert t["A"].cost == 3.0 and t["A"].sources["cost"] == "user"
    assert t["B"].acceptance == 0.45 and t["B"].sources["save_rate"] == "data"
    assert t["C"].sources == {"acceptance": "default", "save_rate": "default",
                              "cost": "default"}


def test_default_catalogue_and_pricing_load():
    offers = load_catalogue(OFFERS_FILE)
    assert 4 <= len(offers) <= 6
    pricing = load_pricing(PRICING_FILE)
    assert pricing.price("anything").input_per_1m == 0 and "free" in pricing.note


@pytest.mark.parametrize(("text", "message"), [
    ("- name: A\n  cost: 5\n  assumed_acceptance_rate: [oops\n", "invalid YAML"),
    ("name: A\n", "must be a list"),
    ("- name: A\n  cost: 5\n  assumed_acceptance_rate: 0.2\n"
     "- name: B\n  cost: -1\n  assumed_acceptance_rate: 0.2\n", "line 4"),
    ("- name: A\n  cost: 5\n  assumed_acceptance_rate: 1.5\n", "assumed_acceptance_rate"),
    ("- name: A\n  cost: 5\n  assumed_acceptance_rate: 0.2\n  eligible_segments:\n"
     "    - column: tenure\n", "line 1"),
    ("- name: A\n  cost: 5\n  assumed_acceptance_rate: 0.2\n"
     "- name: a\n  cost: 5\n  assumed_acceptance_rate: 0.2\n", "duplicate"),
])
def test_invalid_catalogue_gives_clear_error(tmp_path, text, message):
    path = tmp_path / "offers.yaml"
    path.write_text(textwrap.dedent(text))
    with pytest.raises(CatalogueError, match=message):
        load_catalogue(path)


# ---------------------------------------------------------------- session-level (Telco)


def test_business_metrics_on_telco():
    from pipeline import telco_state

    from app.business import BusinessAssumptions, OfferOverride, compute

    state = telco_state()
    base = compute(state, {})
    assert base["enabled"] and base["warnings"] == []
    k = base["kpis"]
    assert k["customers_scored"] == 7000 and 0 < k["customers_with_offer"] <= 7000
    assert k["revenue_at_risk"] == pytest.approx(base["revenue_at_risk"]["total"])
    assert any(" / " in r["segment"] for r in base["roi_by_segment"])  # band x Contract
    months = next(a for a in base["assumptions"] if a["name"] == "months_remaining")
    assert months == {**months, "value": 12, "source": "default"}

    edited = compute(state, {}, BusinessAssumptions(
        months_remaining=24, offers={"Free 10GB data booster": OfferOverride(cost=0.5),
                                     "Nope": OfferOverride(cost=1)}))
    # Revenue at risk is linear in months remaining.
    assert edited["kpis"]["revenue_at_risk"] == pytest.approx(2 * k["revenue_at_risk"])
    booster = next(o for o in edited["offers"] if o["name"] == "Free 10GB data booster")
    assert booster["cost"] == 0.5 and booster["sources"]["cost"] == "user"
    assert any("unknown offers" in w for w in edited["warnings"])


def test_business_metrics_disabled_without_revenue_column():
    from pipeline import telco_state

    from app.business import compute

    state = dict(telco_state())
    state["confirmed_schema"] = {**state["confirmed_schema"], "revenue_column": None}
    out = compute(state, {})
    assert out["enabled"] is False and "revenue" in out["reason"]



def test_numeric_in_rule_matches_floats():
    frame = CUSTOMERS.assign(Senior=[1.0, 0.0, 1.0, 0.0, 0.0])
    specs = [OfferSpec(name="Senior deal", cost=1, assumed_acceptance_rate=0.5,
                       eligible_segments=[{"column": "Senior", "in": [1]}])]
    masks, _ = bm.eligible_offers(frame, bm.offer_terms(specs, {}))
    assert masks["Senior deal"].tolist() == [True, False, True, False, False]
