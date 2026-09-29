import numpy as np
import pandas as pd
import pytest

from app.agents.cleaning import cleaning_node
from app.config import BACKEND_DIR
from app.graph.errors import FatalNodeError
from app.graph.state import ChurnState
from app.stats import cleaning as c
from app.stats import profiling

TELCO = BACKEND_DIR / "sample_data" / "telco_churn.csv"


def schema(target="Churn", positive="Yes", ids=("id",), time=None, columns=()):
    return {"target_column": target, "positive_label": positive, "id_columns": list(ids),
            "time_column": time, "columns": [{"name": n, "semantic_type": t} for n, t in columns]}


def base(rows=120) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    return pd.DataFrame({
        "id": [f"C{i}" for i in range(rows)],
        "charges": rng.normal(50, 5, rows).round(2),
        "plan": rng.choice(["Basic", "Pro"], rows),
        "Churn": ["Yes" if i % 4 == 0 else "No" for i in range(rows)],
    })


def steps(result, step):
    return {e["column"]: e["rows_affected"] for e in result.log if e["step"] == step}


# ---------------------------------------------------------------- rules


def test_blank_strings_become_missing_then_numeric():
    df = base()
    df["charges"] = df["charges"].astype(str)
    df.loc[[1, 2], "charges"] = " "
    df.loc[3, "charges"] = "n/a"
    result = c.clean(df, schema(columns=[("charges", "numeric")]), min_rows=100)
    assert result.frame["charges"].dtype.kind == "f"
    assert result.frame["charges"].isna().sum() == 3
    assert steps(result, "blank_to_missing") == {"charges": 2}
    assert steps(result, "coerce_numeric") == {"charges": 1}
    assert steps(result, "missing_left_for_model") == {"charges": 3}


def test_whitespace_trimmed_and_case_unified_to_most_common_spelling():
    df = base()
    df.loc[0:9, "plan"] = "  basic "
    df.loc[10:14, "plan"] = "Pro  "
    result = c.clean(df, schema(), min_rows=100)
    assert set(result.frame["plan"]) == {"Basic", "Pro"}
    assert steps(result, "unify_case")["plan"] == 10
    assert steps(result, "trim_whitespace")["plan"] == 15


def test_exact_duplicates_removed_and_logged():
    df = pd.concat([base(), base().iloc[:5]], ignore_index=True)
    result = c.clean(df, schema(), min_rows=100)
    assert len(result.frame) == 120
    assert steps(result, "drop_duplicates") == {None: 5}
    assert result.health["duplicates_removed"] == 5


def test_missing_categoricals_become_unknown_numeric_left_missing():
    df = base()
    df.loc[[5, 6], "plan"] = np.nan
    df.loc[[7], "charges"] = np.nan
    result = c.clean(df, schema(), min_rows=100)
    assert (result.frame["plan"] == "Unknown").sum() == 2
    assert result.frame["charges"].isna().sum() == 1


def test_target_mapped_to_zero_one_and_missing_target_dropped():
    df = base(130)
    df.loc[0, "Churn"] = np.nan
    df.loc[1, "Churn"] = " Yes "
    result = c.clean(df, schema(), min_rows=100)
    assert set(result.frame["Churn"].unique()) == {0, 1}
    assert result.frame["Churn"].dtype.kind == "i"
    assert steps(result, "drop_missing_target") == {"Churn": 1}
    assert result.frame.loc[0, "Churn"] == 1  # " Yes " (old row 1) is positive


def test_outliers_flagged_not_deleted():
    df = base()
    df.loc[0, "charges"] = 500.0
    result = c.clean(df, schema(), min_rows=100)
    assert len(result.frame) == 120
    assert result.frame["charges"].max() == 500.0
    assert result.health["outliers_flagged"]["charges"]["iqr"] >= 1
    assert result.health["outliers_flagged"]["charges"]["zscore"] == 1


def test_outlier_masks_match_hand_calculation():
    s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 100], dtype=float)
    iqr, z = c.outlier_flags(s)
    q1, q3 = 3.0, 7.0  # pandas linear quantiles
    assert iqr.tolist() == [(v < q1 - 6 or v > q3 + 6) for v in s]
    assert z.tolist() == [abs(v - s.mean()) / s.std(ddof=0) > 3 for v in s]


def test_few_negatives_in_never_negative_column_become_missing():
    df = base(400)
    df.loc[0, "charges"] = -12.0
    result = c.clean(df, schema(), min_rows=100)
    assert steps(result, "invalid_negative") == {"charges": 1}
    assert np.isnan(result.frame.loc[0, "charges"])


def test_signed_columns_keep_negatives():
    df = base(400)
    df["UsageChangePct"] = 5.0
    df.loc[0, "UsageChangePct"] = -12.0
    result = c.clean(df, schema(), min_rows=100)
    assert "UsageChangePct" not in steps(result, "invalid_negative")


def test_single_class_target_is_fatal():
    df = base()
    df["Churn"] = "No"
    with pytest.raises(c.CleaningFatal, match="only one class"):
        c.clean(df, schema(), min_rows=100)


def test_too_few_rows_after_cleaning_is_fatal():
    df = pd.concat([base(60)] * 2, ignore_index=True)  # 60 unique rows
    with pytest.raises(c.CleaningFatal, match="Only 60 rows"):
        c.clean(df, schema(), min_rows=100)


def test_health_score_formula():
    assert c.health_score(100, 0, {"a": 0.0}, [0.0], 0.5) == 100
    # m=0.1 -> 4, d=min(1, 10*5/100)=0.5 -> 10, o=min(1, 5*0.02)=0.1 -> 2,
    # b=(0.5-0.2)/0.45 -> 13.33; 100-4-10-2-13.33 = 70.67 -> 71
    assert c.health_score(100, 5, {"a": 10.0, "b": 10.0}, [0.02], 0.2) == 71


def test_health_report_contents():
    result = c.clean(base(), schema(), min_rows=100)
    health = result.health
    assert health["rows_before"] == health["rows_after"] == 120
    assert health["class_balance"] == {"positive": 30, "negative": 90, "positive_rate": 0.25,
                                       "positive_label": "Yes"}
    assert 0 <= health["health_score"] <= 100
    assert "health = 100" in health["score_formula"]


# ---------------------------------------------------------------- telco + node


def telco_schema(frame: pd.DataFrame) -> dict:
    heur = profiling.heuristic_schema(frame)
    return {**heur, "columns": [{"name": x["name"], "semantic_type": x["semantic_type"]}
                                for x in heur["columns"]]}


def test_telco_sample_cleaning():
    raw = pd.read_csv(TELCO)
    result = c.clean(raw, telco_schema(raw), min_rows=100)
    df = result.frame
    assert df["TotalCharges"].dtype.kind == "f"
    assert steps(result, "blank_to_missing")["TotalCharges"] == 11
    assert df["TotalCharges"].isna().sum() == 11
    assert result.health["duplicates_removed"] == 14 and len(df) == 7000
    assert set(df["InternetService"]) == {"Fiber optic", "DSL", "No"}
    assert steps(result, "unify_case")["InternetService"] > 0
    assert df["PaymentMethod"].nunique() == 4
    assert steps(result, "invalid_negative")["AvgMonthlyCallMinutes"] == 5
    assert "DataUsageChange3mPct" not in steps(result, "invalid_negative")
    assert result.health["class_balance"]["positive"] + \
        result.health["class_balance"]["negative"] == 7000


def test_cleaning_node_writes_clean_parquet(tmp_path):
    raw = pd.read_csv(TELCO)
    raw_path = tmp_path / "raw.parquet"
    raw.to_parquet(raw_path, index=False)
    state = ChurnState(session_id="s", raw_path=str(raw_path),
                       confirmed_schema=telco_schema(raw))
    update = cleaning_node(state)
    assert update["clean_path"].endswith("clean.parquet")
    assert len(pd.read_parquet(update["clean_path"])) == 7000
    assert update["data_health"]["rows_after"] == 7000
    assert update["cleaning_log"]


def test_cleaning_node_routes_fatal(tmp_path):
    df = base()
    df["Churn"] = "No"
    path = tmp_path / "raw.parquet"
    df.to_parquet(path, index=False)
    with pytest.raises(FatalNodeError, match="only one class"):
        cleaning_node(ChurnState(session_id="s", raw_path=str(path), confirmed_schema=schema()))
