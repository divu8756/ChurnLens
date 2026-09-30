import numpy as np
import pandas as pd
import pytest

from app.experiments.assignment import assign_groups, balance_check, hash_unit, snapshot_hash
from app.experiments.data import plan_column
from app.experiments.segments import SegmentError, apply_segment

IDS = [f"cust-{i}" for i in range(10_000)]


def test_hash_unit_is_in_unit_interval_and_stable():
    values = [hash_unit(7, cid) for cid in IDS[:1000]]
    assert all(0 <= v < 1 for v in values)
    assert values == [hash_unit(7, cid) for cid in IDS[:1000]]


def test_assignment_is_reproducible_and_depends_on_experiment():
    first = assign_groups(3, IDS, 0.5)
    assert first == assign_groups(3, IDS, 0.5)
    # Order does not matter: each customer's group depends only on (experiment, customer).
    reversed_groups = assign_groups(3, IDS[::-1], 0.5)[::-1]
    assert first == reversed_groups
    assert first != assign_groups(4, IDS, 0.5)


@pytest.mark.parametrize("control_share", [0.5, 0.2])
def test_split_within_one_point_of_target(control_share):
    groups = assign_groups(11, IDS, control_share)
    share = groups.count("control") / len(groups)
    assert abs(share - control_share) < 0.01


def _customers(n=4000, seed=42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "customer_id": [f"c{i}" for i in range(n)],
        "churn_probability": rng.random(n),
        "tenure": rng.integers(1, 72, n),
        "MonthlyCharges": rng.normal(65, 20, n),
        "Contract": rng.choice(["Month-to-month", "One year", "Two year"], n),
    })


COVARIATES = {"churn_probability": "numeric", "tenure": "numeric",
              "MonthlyCharges": "numeric", "Contract": "categorical"}


def test_random_split_is_balanced():
    frame = _customers()
    frame["group"] = assign_groups(1, frame["customer_id"].tolist(), 0.5)
    out = balance_check(frame, COVARIATES)
    assert out["balanced"] and out["flagged"] == []
    assert out["n_treatment"] + out["n_control"] == len(frame)
    contract_rows = [r for r in out["covariates"] if r["covariate"] == "Contract"]
    assert len(contract_rows) == 3


def test_skewed_split_is_flagged():
    frame = _customers()
    # Long-tenure customers all go to treatment: a broken randomisation.
    frame["group"] = np.where(frame["tenure"] > 30, "treatment", "control")
    out = balance_check(frame, COVARIATES)
    assert not out["balanced"] and "tenure" in out["flagged"]
    tenure = next(r for r in out["covariates"] if r["covariate"] == "tenure")
    t, c = frame[frame.group == "treatment"].tenure, frame[frame.group == "control"].tenure
    expected = (t.mean() - c.mean()) / np.sqrt((t.var(ddof=1) + c.var(ddof=1)) / 2)
    assert abs(tenure["smd"] - expected) < 1e-9


def test_skewed_plan_type_is_flagged():
    frame = _customers()
    frame["group"] = np.where(frame["Contract"] == "Two year", "treatment",
                              assign_groups(1, frame["customer_id"].tolist(), 0.5))
    out = balance_check(frame, COVARIATES)
    assert "Contract=Two year" in out["flagged"]


def test_snapshot_hash_ignores_row_order():
    frame = _customers(200)
    assert snapshot_hash(frame) == snapshot_hash(frame.sample(frac=1, random_state=42))
    changed = frame.copy()
    changed.loc[0, "tenure"] += 1
    assert snapshot_hash(frame) != snapshot_hash(changed)


def test_segment_filters():
    frame = _customers(1000)
    seg = apply_segment(frame, {"filters": [
        {"column": "Contract", "op": "eq", "value": "Month-to-month"},
        {"column": "tenure", "op": "lte", "value": 12},
        {"column": "churn_probability", "op": "gt", "value": 0.3}]})
    assert len(seg) > 0
    assert (seg.Contract == "Month-to-month").all() and (seg.tenure <= 12).all()
    assert (seg.churn_probability > 0.3).all()
    inn = apply_segment(frame, {"filters": [
        {"column": "Contract", "op": "in", "value": ["One year", "Two year"]}]})
    assert set(inn.Contract) == {"One year", "Two year"}
    assert len(apply_segment(frame, {"filters": []})) == 1000


@pytest.mark.parametrize("bad", [
    {"column": "nope", "op": "eq", "value": "x"},
    {"column": "tenure", "op": "gt", "value": "abc"},
    {"column": "Contract", "op": "gt", "value": 3},
    {"column": "tenure", "op": "eq", "value": [1, 2]},
])
def test_bad_segment_filters(bad):
    with pytest.raises(SegmentError):
        apply_segment(_customers(50), {"filters": [bad]})


def test_plan_column_detection():
    frame = _customers(20)
    assert plan_column({"columns": []}, frame) == "Contract"
    assert plan_column({"columns": []}, frame.drop(columns="Contract")) is None
    # A location tier listed first must not beat the contract type.
    tiered = frame.assign(CityTier="Tier 1")[["CityTier", *frame.columns]]
    assert plan_column({"columns": []}, tiered) == "Contract"
    assert plan_column({"columns": []}, tiered.drop(columns="Contract")) == "CityTier"
