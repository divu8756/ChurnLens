import numpy as np
import pandas as pd
import pytest
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from app.stats import model_metrics as mm
from app.stats.modelling import train_and_evaluate

TOL = 1e-9

# 20 rows, 6 churners. Rows 1 and 2 tie at 0.85 across the top-10% cut (k = 2):
# the stable sort keeps row 1 (no churn) ahead of row 2 (churn).
Y20 = np.array([1, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0])
P20 = np.array([0.9, 0.85, 0.85, 0.7, 0.7, 0.6, 0.5, 0.5, 0.4, 0.4,
                0.35, 0.3, 0.3, 0.2, 0.2, 0.15, 0.1, 0.1, 0.05, 0.05])


def test_top_10pct_by_hand_with_ties():
    top = mm.at_top(Y20, P20)
    assert top["k"] == 2 and top["churners_in_top"] == 1
    assert top["precision"] == pytest.approx(0.5, abs=TOL)
    assert top["recall"] == pytest.approx(1 / 6, abs=TOL)


def test_deciles_by_hand():
    rows = mm.deciles(Y20, P20)
    assert [r["churners"] for r in rows] == [1, 2, 0, 1, 0, 1, 0, 0, 1, 0]
    assert all(r["n"] == 2 for r in rows)
    overall = 6 / 20
    assert rows[0]["lift"] == pytest.approx(0.5 / overall, abs=TOL)
    assert rows[1]["lift"] == pytest.approx(1.0 / overall, abs=TOL)
    gains = [r["cumulative_gain"] for r in rows]
    assert gains == pytest.approx([1/6, 3/6, 3/6, 4/6, 4/6, 5/6, 5/6, 5/6, 1, 1], abs=TOL)
    assert rows[-1]["cumulative_share"] == pytest.approx(1.0)


def _random(n=2000, seed=42):
    rng = np.random.default_rng(seed)
    p = rng.random(n)
    y = (rng.random(n) < p * 0.7).astype(int)
    return y, p


def test_scores_match_sklearn():
    y, p = _random()
    out = mm.evaluate(y, p)
    assert abs(out["roc_auc"] - roc_auc_score(y, p)) < TOL
    assert abs(out["pr_auc"] - average_precision_score(y, p)) < TOL
    assert abs(out["brier"] - brier_score_loss(y, p)) < TOL


def test_calibration_curve_matches_sklearn():
    y, p = _random()
    bins = mm.calibration(y, p)
    prob_true, prob_pred = calibration_curve(y, p, n_bins=10)
    filled = [b for b in bins if b["n"]]
    assert len(bins) == 10 and sum(b["n"] for b in bins) == len(y)
    assert np.allclose([b["observed_rate"] for b in filled], prob_true, atol=TOL, rtol=0)
    assert np.allclose([b["mean_predicted"] for b in filled], prob_pred, atol=TOL, rtol=0)


def test_empty_bins_are_kept_with_zero_count():
    bins = mm.calibration([0, 1, 1], [0.05, 0.95, 0.91])
    assert [b["n"] for b in bins] == [1, 0, 0, 0, 0, 0, 0, 0, 0, 2]
    assert bins[1]["observed_rate"] is None


def test_single_class_has_no_auc():
    out = mm.evaluate([0, 0, 0], [0.1, 0.2, 0.3])
    assert out["roc_auc"] is None and out["top_10pct"]["recall"] is None


def _data(n=1200, seed=5):
    rng = np.random.default_rng(seed)
    x1 = rng.normal(size=n)
    plan = rng.choice(["A", "B"], n)
    logit = 1.4 * x1 + np.where(plan == "A", 0.7, -0.7) - 1.0
    churn = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return pd.DataFrame({"id": [f"c{i}" for i in range(n)], "x1": x1, "plan": plan,
                         "churn": churn})


SCHEMA = {"target_column": "churn", "positive_label": "1", "id_columns": ["id"],
          "time_column": None, "columns": []}


def test_calibrator_never_sees_the_test_split(monkeypatch):
    frame = _data()
    _, _, artifacts = train_and_evaluate(frame, SCHEMA)
    seen = {}
    real_fit = CalibratedClassifierCV.fit

    def spy(self, x, y, **kw):
        seen["index"] = np.asarray(x.index)
        return real_fit(self, x, y, **kw)

    monkeypatch.setattr(CalibratedClassifierCV, "fit", spy)
    x = frame[artifacts.numeric + artifacts.categorical]
    metrics, calibrated, _ = mm.model_metrics_v2(artifacts, x, frame["churn"])
    assert np.intersect1d(seen["index"], artifacts.test_index).size == 0
    assert set(seen["index"]) == set(artifacts.train_index)
    assert len(calibrated) == len(frame) and ((calibrated >= 0) & (calibrated <= 1)).all()
    assert metrics["calibration_method"] == "sigmoid"  # 960 training rows < 1000
    assert metrics["raw"]["n"] == metrics["calibrated"]["n"] == len(artifacts.test_index)


def test_isotonic_from_1000_training_rows():
    frame = _data(n=1300)
    _, _, artifacts = train_and_evaluate(frame, SCHEMA)
    x = frame[artifacts.numeric + artifacts.categorical]
    metrics, _, _ = mm.model_metrics_v2(artifacts, x, frame["churn"])
    assert metrics["calibration_method"] == "isotonic"


def test_overlapping_splits_are_rejected():
    frame = _data(300)
    _, _, artifacts = train_and_evaluate(frame, SCHEMA)
    artifacts.test_index = artifacts.train_index[:10]
    with pytest.raises(ValueError, match="overlap"):
        mm.model_metrics_v2(artifacts, frame[["x1", "plan"]], frame["churn"])


def test_calibration_improves_brier_on_telco():
    from pipeline import telco_state

    state = telco_state()
    v2 = state["model_metrics_v2"]
    assert v2 is not None, state.get("errors")
    assert v2["calibration_method"] == "isotonic"
    assert v2["calibrated"]["brier"] <= v2["raw"]["brier"]
    # Ranking quality barely moves: calibration is (almost) monotone.
    assert abs(v2["calibrated"]["roc_auc"] - v2["raw"]["roc_auc"]) < 0.01
    preds = pd.read_parquet(state["predictions_path"])
    assert {"churn_probability", "churn_probability_raw"} <= set(preds.columns)
    assert state["model_metrics"]["risk_bands"]["probability"] == "calibrated"
