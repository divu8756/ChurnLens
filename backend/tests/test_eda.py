import json

import numpy as np
import pandas as pd
import pytest

from app.agents.analysis import eda_node
from app.graph.state import ChurnState
from app.stats import eda


def schema(**kw):
    base = {"target_column": "churn", "positive_label": "1", "id_columns": ["id"],
            "time_column": None, "columns": []}
    base.update(kw)
    return base


def known() -> pd.DataFrame:
    # plan A: 10 rows, 6 churn (0.6); plan B: 20 rows, 5 churn (0.25); plan C: 10 rows, 0
    plan = ["A"] * 10 + ["B"] * 20 + ["C"] * 10
    churn = [1] * 6 + [0] * 4 + [1] * 5 + [0] * 15 + [0] * 10
    return pd.DataFrame({
        "id": [f"c{i}" for i in range(40)],
        "plan": plan,
        "charges": [float(v) for v in range(40)],
        "months": [1, 3, 5, 7, 9, 11, 13, 20, 30, 50] * 4,
        "churn": churn,
    })


def test_churn_rate_by_category_is_exact_and_sorted():
    result = eda.run_eda(known(), schema())
    levels = result["categorical"]["plan"]["levels"]
    assert levels == [
        {"level": "A", "n": 10, "churned": 6, "churn_rate": 0.6},
        {"level": "B", "n": 20, "churned": 5, "churn_rate": 0.25},
        {"level": "C", "n": 10, "churned": 0, "churn_rate": 0.0},
    ]
    assert result["overview"] == {"rows": 40, "churned": 11, "churn_rate": 11 / 40}


def test_ids_and_target_are_excluded():
    result = eda.run_eda(known(), schema())
    assert "id" not in result["categorical"] and "churn" not in result["numeric"]


def test_numeric_churned_vs_retained():
    df = known()
    summary = eda.run_eda(df, schema())["numeric"]["charges"]
    churned = df.loc[df.churn == 1, "charges"]
    assert summary["churned"]["mean"] == pytest.approx(churned.mean(), abs=1e-12)
    assert summary["retained"]["n"] == 29
    assert summary["median"] == pytest.approx(19.5)
    assert sum(summary["histogram"]["counts"]) == 40


def test_correlation_numerics_only_with_target():
    df = known()
    corr = eda.run_eda(df, schema())["correlation"]
    assert corr["columns"] == ["charges", "months"]
    assert corr["matrix"][0][0] == pytest.approx(1.0)
    assert corr["with_target"]["charges"] == pytest.approx(df.charges.corr(df.churn))


def test_tenure_bands_only_with_time_column():
    assert eda.run_eda(known(), schema())["tenure_bands"] is None
    bands = eda.run_eda(known(), schema(time_column="months"))["tenure_bands"]["bands"]
    assert [b["band"] for b in bands] == ["0-6", "6-12", "12-24", "24-48", "48+"]
    assert sum(b["n"] for b in bands) == 40
    first = bands[0]  # months 1, 3, 5 in rows 0-2, 10-12, 20-22, 30-32
    assert first["n"] == 12 and first["churned"] == 3 + 3 + 0 + 0


def test_all_null_column_does_not_crash():
    df = known()
    df["empty"] = np.nan
    result = eda.run_eda(df, schema(columns=[{"name": "empty", "semantic_type": "numeric"}]))
    assert result["numeric"]["empty"]["mean"] is None
    assert "empty" not in result["correlation"]["columns"]


def test_single_numeric_column():
    df = pd.DataFrame({"x": np.arange(120, dtype=float), "churn": [0, 1] * 60})
    result = eda.run_eda(df, schema(id_columns=[]))
    assert list(result["numeric"]) == ["x"] and result["categorical"] == {}


def test_more_than_20_levels_fold_into_other():
    df = pd.DataFrame({"city": [f"city{i % 30}" for i in range(300)],
                       "churn": [i % 2 for i in range(300)]})
    result = eda.run_eda(df, schema(id_columns=[],
                                    columns=[{"name": "city", "semantic_type": "categorical"}]))
    cat = result["categorical"]["city"]
    assert len(cat["levels"]) == 20 and cat["levels_folded_into_other"] == 11
    assert sum(level["n"] for level in cat["levels"]) == 300


def test_output_is_strict_json():
    df = known()
    df["empty"] = np.nan
    json.dumps(eda.run_eda(df, schema(time_column="months")), allow_nan=False)


def test_eda_node(tmp_path):
    path = tmp_path / "clean.parquet"
    known().to_parquet(path, index=False)
    update = eda_node(ChurnState(session_id="s", clean_path=str(path),
                                 confirmed_schema=schema()))
    assert update["eda_results"]["overview"]["rows"] == 40
    assert update["progress"][0].node == "eda"
