import copy

import pytest

from app import llm
from app.agents.validator import validator_node
from app.graph import builder as b
from app.graph.state import ChurnState, ProgressEntry
from app.llm_fake import FakeLLM
from app.validation import (
    check_text,
    matches,
    numbers_in,
    validate_insight,
    validate_recommendation,
)

STATE = {
    "eda_results": {"categorical": {"Contract": {"levels": [
        {"level": "Month-to-month", "n": 3800, "churn_rate": 0.265}]}}},
    "hypothesis_results": {"tests": [{
        "variable": "Contract", "test_name": "Chi-square test of independence",
        "p_adjusted": 1.2e-50, "significant": True,
        "effect_size": {"name": "Cramér's V", "value": 0.37, "band": "medium"}}]},
    "impact_estimates": {"items": {"Contract=Month-to-month": {
        "customers": 3800, "scenarios": {"reduce_10pct": {"churners_saved": 100.7}}}}},
    "model_metrics": {"chosen_model_name": "Logistic regression"},
}
RATE = "eda_results.categorical.Contract.levels.0.churn_rate"
N = "eda_results.categorical.Contract.levels.0.n"
P = "hypothesis_results.tests.0.p_adjusted"
IMPACT = "impact_estimates.items.Contract=Month-to-month.scenarios.reduce_10pct.churners_saved"
CUSTOMERS = "impact_estimates.items.Contract=Month-to-month.customers"


def insight(text="Month-to-month customers churn at 26.5% (3,800 customers).", figures=None):
    return {"id": "I1", "title": "Monthly contracts churn most", "text": text,
            "figures": figures if figures is not None else [
                {"source_key": RATE, "value": 0.265, "display": "26.5%"},
                {"source_key": N, "value": 3800, "display": "3,800"}],
            "significant": True, "causality_note": ""}


def rec(**over):
    base = {"id": "R1", "problem": "Churn is 26.5% on monthly contracts.",
            "action": "Offer annual plans.", "target_segment": "Month-to-month customers",
            "customers_affected": {"source_key": CUSTOMERS, "value": 3800, "display": "3,800"},
            "impact": {"source_key": IMPACT, "value": 100.7, "assumption": "If churn fell 10%."},
            "effort": "low", "priority": 1, "group": "quick_win",
            "figures": [{"source_key": RATE, "value": 26.5, "display": "26.5%"}]}
    base.update(over)
    return base


# ---------------------------------------------------------------- unit rules


def test_correct_insight_passes():
    assert validate_insight(STATE, insight()) == []


def test_fraction_vs_percent_and_rounding_pass():
    assert matches(26.5, 0.265) and matches(0.265, 0.265) and matches(27, 0.2654)
    assert not matches(30, 0.265)
    figs = [{"source_key": RATE, "value": 26.5, "display": "26.5%"},
            {"source_key": N, "value": 3800, "display": "3,800"}]
    assert validate_insight(STATE, insight(figures=figs)) == []


def test_planted_wrong_number_fails():
    figs = [{"source_key": RATE, "value": 0.31, "display": "31%"},
            {"source_key": N, "value": 3800, "display": "3,800"}]
    problems = validate_insight(STATE, insight("Churn is 31% (3,800 customers).", figs))
    assert any("does not match" in p for p in problems)


def test_unlisted_number_in_text_fails():
    problems = validate_insight(STATE, insight(
        "Month-to-month customers churn at 26.5% (3,800 customers), up 12% on last year."))
    assert problems == ["number 12 in the text is not a declared figure"]


def test_missing_key_fails():
    figs = [{"source_key": "eda_results.nope", "value": 1, "display": "1"}]
    assert validate_insight(STATE, insight("One thing.", figs)) == [
        "source_key 'eda_results.nope' does not exist"]


def test_non_numeric_key_fails():
    figs = [{"source_key": "model_metrics.chosen_model_name", "value": 1, "display": "1"}]
    assert "is not a number" in validate_insight(STATE, insight("Model.", figs))[0]


def test_names_with_digits_are_not_numbers_and_small_p_values_are_accepted():
    assert numbers_in("5G handsets, Q1 offers and NetworkComplaints90d") == []
    assert numbers_in("costs ₹1,250 and 3x more") == [(1250.0, False), (3.0, False)]
    figs = [{"source_key": P, "value": 1.2e-50, "display": "< 0.001"}]
    assert check_text("significant (p < 0.001)", figs) == []
    assert validate_insight(STATE, insight("Significant (adjusted p < 0.001).", figs)) == []


def test_recommendation_rules():
    assert validate_recommendation(STATE, rec()) == []
    wrong_source = rec(impact={"source_key": RATE, "value": 0.265, "assumption": "x"})
    assert any("must come from impact_estimates" in p
               for p in validate_recommendation(STATE, wrong_source))
    invented = rec(action="Offer annual plans to save 500 customers.")
    assert "number 500 in the text is not a declared figure" in \
        validate_recommendation(STATE, invented)


# ---------------------------------------------------------------- node + routing


def node_state(insights, recs, retries=None):
    return ChurnState(session_id="s", insights=insights, recommendations=recs,
                      retry_counts=retries or {}, **copy.deepcopy(
                          {k: v for k, v in STATE.items() if k != "model_metrics"}),
                      model_metrics=STATE["model_metrics"])


def test_node_passes_and_finalises():
    update = validator_node(node_state([insight()], [rec()]))
    report = update["validation_report"]
    assert (report["checked"], report["passed"], report["retry_agents"]) == (2, 2, [])
    assert update["final_insights"][0]["id"] == "I1" and update["validator_feedback"] == {}


def test_node_requests_retry_with_feedback():
    bad = insight("Churn is 99%.", [])
    update = validator_node(node_state([bad, insight()], [rec()]))
    assert update["validation_report"]["retry_agents"] == ["insight_agent"]
    assert update["retry_counts"] == {"insight_agent": 1}
    assert "I1: number 99 in the text" in update["validator_feedback"]["insight_agent"][0]


def test_retry_limit_drops_items_and_stops_loop():
    bad = {**insight("Churn is 99%.", []), "id": "I9"}
    update = validator_node(node_state([bad, insight()], [rec()], {"insight_agent": 2}))
    report = update["validation_report"]
    assert report["retry_agents"] == [] and report["dropped"] == 1 and report["final"]
    assert [i["id"] for i in update["final_insights"]] == ["I1"]


def test_routing_goes_back_to_the_failing_agent(monkeypatch):
    """Full loop in the graph: recommendations fail once, then pass."""
    fake = FakeLLM(fixtures={
        "InsightList": {"insights": [insight()]},
        "RecommendationList": [{"recommendations": [rec(problem="Churn is 77%.")]},
                               {"recommendations": [rec()]}],
    })
    llm.set_model_factory(fake)
    monkeypatch.setattr(llm, "_sleep", lambda s: None)
    llm.reset_throttle()
    try:
        from app.agents.llm_agents import insight_agent_node, recommendation_agent_node

        def seed(state):  # stands in for the analysis nodes
            return {**copy.deepcopy(STATE),
                    "progress": [ProgressEntry(node="impact", status="done")]}
        graph = b.build_graph(nodes={b.IMPACT: seed, b.INSIGHT_AGENT: insight_agent_node,
                                     b.RECOMMENDATION_AGENT: recommendation_agent_node,
                                     b.VALIDATOR: validator_node})
        result = graph.invoke({"session_id": "s"})
    finally:
        llm.set_model_factory(None)
    schemas = [c["schema"] for c in fake.calls]
    assert schemas == ["InsightList", "RecommendationList", "RecommendationList"]
    assert "Fix these issues" in fake.calls[2]["prompt"] and "77" in fake.calls[2]["prompt"]
    assert result["retry_counts"] == {"recommendation_agent": 1}
    assert len(result["final_recommendations"]) == 1 and result["validation_report"]["final"]


@pytest.mark.parametrize("first_bad", ["insight", "recommendation"])
def test_router_picks_the_right_agent(first_bad):
    report = {"retry_agents": ["insight_agent"] if first_bad == "insight"
              else ["recommendation_agent"]}
    state = ChurnState(session_id="s", validation_report=report)
    expected = b.INSIGHT_AGENT if first_bad == "insight" else b.RECOMMENDATION_AGENT
    assert b.route_after_validator(state) == expected


def test_scientific_notation_is_one_number():
    assert numbers_in("adjusted p = 1.171e-202") == [(1.171e-202, False)]
    figs = [{"source_key": P, "value": 1.2e-50, "display": "1.2e-50"}]
    assert validate_insight(STATE, insight("Adjusted p = 1.2e-50.", figs)) == []


def test_impact_must_belong_to_the_targeted_group():
    state = copy.deepcopy(STATE)
    state["impact_estimates"]["items"]["segment_0"] = {
        "customers": 1022, "scenarios": {"reduce_10pct": {"churners_saved": 39.4}}}
    state["segments"] = {"segments": [{"segment": 0, "size": 1022}]}
    mismatch = rec(customers_affected={"source_key": "segments.segments.0.size",
                                       "value": 1022, "display": "1,022"})
    assert any("different" in p or "use the impact of the targeted group" in p
               for p in validate_recommendation(state, mismatch))
    matched = rec(customers_affected={"source_key": "segments.segments.0.size",
                                      "value": 1022, "display": "1,022"},
                  impact={"source_key": "impact_estimates.items.segment_0.scenarios."
                                        "reduce_10pct.churners_saved",
                          "value": 39.4, "assumption": "If churn fell 10%."})
    assert validate_recommendation(state, matched) == []
