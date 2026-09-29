import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from app import llm
from app.api import results as results_api
from app.graph.builder import build_graph
from app.graph.checkpointer import make_serde
from app.graph.nodes import default_nodes
from app.llm_fake import FakeLLM
from app.main import create_app
from app.runs import RunManager
from app.stats import modelling as m
from app.stats import predictions as p

SCHEMA = {"target_column": "churn", "positive_label": "1", "id_columns": ["id"],
          "time_column": None, "columns": []}


def data(n=500, seed=8) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    x1 = rng.normal(size=n)
    plan = rng.choice(["A", "B"], n)
    logit = 1.5 * x1 + np.where(plan == "A", 0.8, -0.8) - 0.5
    churn = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return pd.DataFrame({"id": [f"c{i}" for i in range(n)], "x1": x1,
                         "x2": rng.normal(size=n), "plan": plan, "churn": churn})


@pytest.fixture(scope="module")
def scored():
    df = data()
    _, _, artifacts = m.train_and_evaluate(df, SCHEMA)
    table, summary = p.score_customers(artifacts, df, SCHEMA, high=0.6, medium=0.3)
    return df, artifacts, table, summary


def test_every_customer_scored_with_three_reasons(scored):
    df, _, table, _ = scored
    assert len(table) == len(df) and set(table.customer_id) == set(df.id)
    assert table[["reason_1", "reason_2", "reason_3"]].notna().all().all()
    assert table.churn_probability.between(0, 1).all()
    assert (table.churn_probability == table.churn_probability.round(3)).all()
    assert table.churn_probability.is_monotonic_decreasing


def test_fewer_reasons_when_fewer_features():
    df = data()[["id", "x1", "churn"]]
    _, _, artifacts = m.train_and_evaluate(df, SCHEMA)
    table, _ = p.score_customers(artifacts, df, SCHEMA, 0.6, 0.3)
    assert table.reason_1.notna().all() and table.reason_2.isna().all()


def test_band_counts_sum_to_total_and_follow_thresholds(scored):
    _, _, table, summary = scored
    counts = summary["band_counts"]
    assert sum(counts.values()) == summary["total"] == len(table)
    assert counts["High"] == int((table.churn_probability >= 0.6).sum())
    high = table[table.risk_band == "High"].churn_probability
    low = table[table.risk_band == "Low"].churn_probability
    assert (high >= 0.6).all() and (low < 0.3).all()


def test_reasons_are_plain_english_and_ordered(scored):
    _, _, table, _ = scored
    first = table.iloc[0]
    assert "(" in first.reason_1 and first.reason_1.rstrip(")").split("(")[-1][0] in "+-"
    contribs = [float(first[f"reason_{i}"].rsplit("(", 1)[1].rstrip(")")) for i in (1, 2, 3)]
    assert contribs == sorted(contribs, reverse=True)
    assert any(r.startswith("plan: ") for r in table.reason_1) or \
        any(r.startswith("x1 = ") for r in table.reason_1)


def test_describe_formats():
    assert p.describe("Contract", "Month-to-month", 0.1834, False) == \
        "Contract: Month-to-month (+0.18)"
    assert p.describe("tenure", 2.0, -0.456, True) == "tenure = 2 (-0.46)"
    assert p.describe("NPS", float("nan"), 0.2, True) == "NPS = missing (+0.20)"


def test_invalid_thresholds_rejected():
    with pytest.raises(ValueError):
        p.risk_band(np.array([0.5]), high=0.3, medium=0.6)


# ---------------------------------------------------------------- /results endpoint


@pytest.fixture
def finished_session(monkeypatch):
    llm.set_model_factory(FakeLLM(fixtures={"SchemaProposal": [TimeoutError("no llm")]}))
    monkeypatch.setattr(llm, "_sleep", lambda s: None)
    llm.reset_throttle()
    app = create_app()
    app.state.runs = RunManager(
        lambda: build_graph(nodes=default_nodes(), checkpointer=InMemorySaver(serde=make_serde())))
    with TestClient(app) as client:
        df = data(350).drop(columns="x2")
        df["churn"] = np.where(df["churn"] == 1, "Yes", "No")
        sid = client.post("/upload", files={"file": ("d.csv", df.to_csv(index=False))}).json()[
            "session_id"]
        client.post(f"/analyze/{sid}")
        run = client.app.state.runs.get(sid)
        import time
        for _ in range(500):
            if run.status == "awaiting_confirmation":
                break
            time.sleep(0.02)
        schema = {"target_column": "churn", "positive_label": "Yes", "id_columns": ["id"],
                  "time_column": None,
                  "columns": [{"name": "plan", "semantic_type": "categorical"}]}
        assert client.post(f"/confirm-schema/{sid}", json=schema).status_code == 200
        for _ in range(1500):
            if run.status in ("done", "failed"):
                break
            time.sleep(0.02)
        assert run.status == "done", [e.data for e in run.events if e.event == "error"]
        yield client, sid
    llm.set_model_factory(None)


def test_results_endpoint_paginates_and_filters(finished_session, monkeypatch):
    client, sid = finished_session
    monkeypatch.setattr(results_api, "PAGE_SIZE", 100)
    body = client.get(f"/results/{sid}").json()
    preds = body["predictions"]
    assert body["status"] == "done" and preds["available"]
    assert preds["total"] == 350 and preds["pages"] == 4 and len(preds["items"]) == 100
    last = client.get(f"/results/{sid}?page=4").json()["predictions"]
    assert len(last["items"]) == 50
    counts = body["results"]["model_metrics"]["risk_bands"]["band_counts"]
    high = client.get(f"/results/{sid}?band=High").json()["predictions"]
    assert high["total"] == counts["High"]
    assert all(item["risk_band"] == "High" for item in high["items"])


def test_results_hide_server_paths(finished_session):
    client, sid = finished_session
    text = client.get(f"/results/{sid}").text
    assert "model_path" not in text and ".parquet" not in text and ".joblib" not in text


def test_results_errors_for_bad_requests(finished_session):
    client, sid = finished_session
    assert client.get(f"/results/{'f' * 32}").status_code == 410
    assert client.get(f"/results/{sid}?band=Extreme").status_code == 422
    assert client.get(f"/results/{sid}?page=0").status_code == 422


def test_results_types_data_health_and_keeps_other_keys(finished_session):
    client, sid = finished_session
    results = client.get(f"/results/{sid}").json()["results"]
    health = results["data_health"]
    assert 0 <= health["health_score"] <= 100
    assert set(health["class_balance"]) == {"positive", "negative", "positive_rate",
                                            "positive_label"}
    assert all({"step", "rows_affected", "detail"} <= set(s) for s in results["cleaning_log"])
    assert "model_metrics" in results and "hypothesis_results" in results


def test_results_types_overview_keys(finished_session):
    client, sid = finished_session
    results = client.get(f"/results/{sid}").json()["results"]
    metrics = results["model_metrics"]
    assert 0 <= metrics["test"]["roc_auc"] <= 1 and metrics["chosen_model_name"]
    assert "confusion_matrix" in metrics["test"]  # untyped keys still pass through
    assert sum(metrics["risk_bands"]["band_counts"].values()) == metrics["risk_bands"]["total"]
    overall = results["impact_estimates"]["overall"]
    assert overall["id"] == "overall" and overall["customers"] > 0
    assert "items" in results["impact_estimates"]
