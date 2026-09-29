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
    assert "features" in metrics  # untyped keys still pass through
    assert sum(metrics["risk_bands"]["band_counts"].values()) == metrics["risk_bands"]["total"]
    overall = results["impact_estimates"]["overall"]
    assert overall["id"] == "overall" and overall["customers"] > 0
    assert "items" in results["impact_estimates"]


def test_results_types_driver_keys(finished_session):
    client, sid = finished_session
    results = client.get(f"/results/{sid}").json()["results"]
    test = results["model_metrics"]["test"]
    cm = test["confusion_matrix"]
    assert cm["tn"] + cm["fp"] + cm["fn"] + cm["tp"] == test["n_test"]
    assert len(test["roc_curve"]["fpr"]) == len(test["roc_curve"]["tpr"])
    shap = results["shap_summary"]
    assert "global" in shap and "global_" not in shap  # served under its real name
    assert shap["global"][0]["mean_abs_shap"] >= shap["global"][-1]["mean_abs_shap"]
    assert results["feature_importance"]["driver_impact"][0]["feature"]
    assert all("odds_ratio" in t for t in results["odds_ratios"]["terms"])


def test_results_types_hypothesis_keys(finished_session):
    client, sid = finished_session
    hyp = client.get(f"/results/{sid}").json()["results"]["hypothesis_results"]
    assert hyp["alpha"] == 0.05 and hyp["n_tests"] == len(hyp["tests"])
    for test in hyp["tests"]:
        assert test["steps"] and all({"label", "formula", "substituted"} <= set(s)
                                     for s in test["steps"])
        assert test["significant"] == (test["p_adjusted"] < hyp["alpha"])
        if test["kind"] == "categorical":
            assert len(test["inputs"]["observed"]["values"]) == len(
                test["inputs"]["observed"]["rows"])
        else:
            assert set(test["inputs"]["groups"]) == {"churned", "retained"}


def test_results_types_customer_insight_keys(finished_session):
    client, sid = finished_session
    results = client.get(f"/results/{sid}").json()["results"]
    eda = results["eda_results"]
    assert eda["overview"]["rows"] == 350
    for summary in eda["categorical"].values():
        rates = [lvl["churn_rate"] for lvl in summary["levels"]]
        assert rates == sorted(rates, reverse=True)
    corr = eda["correlation"]
    assert len(corr["matrix"]) == len(corr["columns"])
    segments = results["segments"]
    assert segments["skipped"] or sum(s["size"] for s in segments["segments"]) == 350
    assert results["survival_results"] is None  # no time column: the graph skips the node


# ------------------------------------------------------------ /predictions


def test_predictions_endpoint_pages_filters_and_searches(finished_session):
    client, sid = finished_session
    body = client.get(f"/predictions/{sid}").json()
    assert body["total"] == 350 and body["page_size"] == 50 and body["pages"] == 7
    probs = [i["churn_probability"] for i in body["items"]]
    assert probs == sorted(probs, reverse=True)
    high = client.get(f"/predictions/{sid}", params={"band": "High"}).json()
    assert all(i["risk_band"] == "High" for i in high["items"])
    target = body["items"][3]["customer_id"]
    found = client.get(f"/predictions/{sid}", params={"q": target.lower()}).json()
    assert target in [i["customer_id"] for i in found["items"]]
    none = client.get(f"/predictions/{sid}", params={"q": "no-such-id"}).json()
    assert none["total"] == 0 and none["items"] == [] and none["pages"] == 1


def test_predictions_errors(finished_session):
    client, sid = finished_session
    assert client.get(f"/predictions/{'f' * 32}").status_code == 410
    assert client.get(f"/predictions/{sid}", params={"band": "Extreme"}).status_code == 422
    assert client.get(f"/predictions/{sid}", params={"q": "x" * 101}).status_code == 422


def test_predictions_csv_matches_the_filter(finished_session):
    import csv
    import io
    client, sid = finished_session
    response = client.get(f"/predictions/{sid}/csv", params={"band": "Low"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="churn_predictions_low.csv"' in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    page = client.get(f"/predictions/{sid}", params={"band": "Low"}).json()
    assert len(rows) == page["total"] and all(r["risk_band"] == "Low" for r in rows)
    assert rows[0]["customer_id"] == page["items"][0]["customer_id"]


def test_csv_safe_neutralises_formulas():
    from app.api.predictions import csv_safe
    assert csv_safe("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert csv_safe("+1") == "'+1" and csv_safe("@x") == "'@x" and csv_safe("-2") == "'-2"
    assert csv_safe("C00001") == "C00001" and csv_safe(0.5) == 0.5



def test_a_malformed_results_key_is_omitted_not_fatal():
    from app.api.results import validated_payload
    payload = {"data_health": {"health_score": "not a number"},
               "model_metrics": None, "target_column": "Churn", "errors": []}
    result = validated_payload(payload)
    assert result.data_health is None and result.target_column == "Churn"
    assert result.errors[-1].message == "'data_health' had an unexpected shape and was omitted."
