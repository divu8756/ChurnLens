import json

import numpy as np
import pandas as pd
import pytest

from app.agents.analysis import segmentation_node
from app.graph.state import ChurnState
from app.stats import segmentation as seg

SCHEMA = {"target_column": "churn", "positive_label": "1", "id_columns": ["id"],
          "time_column": None, "columns": []}


def blobs(n_per=150) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    centres = [(0, 0), (10, 10), (0, 10)]
    churn_rates = [0.1, 0.5, 0.9]
    parts = []
    for (cx, cy), rate in zip(centres, churn_rates, strict=True):
        parts.append(pd.DataFrame({
            "a": rng.normal(cx, 0.5, n_per), "b": rng.normal(cy, 0.5, n_per),
            "churn": (rng.random(n_per) < rate).astype(int),
        }))
    df = pd.concat(parts, ignore_index=True)
    df.insert(0, "id", [f"c{i}" for i in range(len(df))])
    return df


def test_three_obvious_blobs_give_k3():
    result, labels = seg.run_segmentation(blobs(), SCHEMA)
    assert result["k"] == 3
    assert sorted(s["size"] for s in result["segments"]) == [150, 150, 150]
    assert len(labels) == 450
    assert result["silhouette_by_k"]["3"] == max(result["silhouette_by_k"].values())


def test_segments_sorted_by_churn_with_profiles_and_labels():
    result, _ = seg.run_segmentation(blobs(), SCHEMA)
    rates = [s["churn_rate"] for s in result["segments"]]
    assert rates == sorted(rates, reverse=True)
    top = result["segments"][0]  # centre (0, 10): low a, high b
    assert top["label"] in ("High b, Low a", "Low a, High b")
    assert top["pct_of_base"] == pytest.approx(1 / 3)
    assert set(top["feature_means"]) == {"a", "b"}


def test_results_are_reproducible():
    first, labels1 = seg.run_segmentation(blobs(), SCHEMA)
    second, labels2 = seg.run_segmentation(blobs(), SCHEMA)
    assert first == second and np.array_equal(labels1, labels2)


def test_skips_with_fewer_than_two_numeric_features():
    df = blobs().drop(columns="b")
    result, labels = seg.run_segmentation(df, SCHEMA)
    assert result["skipped"] is True and labels is None
    assert "at least 2" in result["reason"]


def test_time_column_and_constant_columns_excluded():
    df = blobs()
    df["tenure"] = np.arange(len(df))
    df["const"] = 1.0
    result, _ = seg.run_segmentation(df, {**SCHEMA, "time_column": "tenure"})
    assert result["features"] == ["a", "b"]


def test_missing_values_are_imputed():
    df = blobs()
    df.loc[:20, "a"] = np.nan
    result, _ = seg.run_segmentation(df, SCHEMA)
    assert result["k"] == 3
    json.dumps(result, allow_nan=False)


def test_segmentation_node_saves_assignments(tmp_path):
    path = tmp_path / "clean.parquet"
    blobs().to_parquet(path, index=False)
    update = segmentation_node(ChurnState(session_id="s", clean_path=str(path),
                                          confirmed_schema=SCHEMA))
    saved = pd.read_parquet(update["segments"]["assignments_path"])
    assert len(saved) == 450 and update["progress"][0].status == "done"


def test_segmentation_node_skip_path(tmp_path):
    path = tmp_path / "clean.parquet"
    blobs().drop(columns="b").to_parquet(path, index=False)
    update = segmentation_node(ChurnState(session_id="s", clean_path=str(path),
                                          confirmed_schema=SCHEMA))
    assert update["progress"][0].status == "skipped"
