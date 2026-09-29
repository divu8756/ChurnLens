import json

import pytest
from pipeline import telco_state

from app import llm
from app.agents.llm_agents import (
    InsightList,
    RecommendationList,
    insight_agent_node,
    recommendation_agent_node,
)
from app.graph.state import ChurnState
from app.llm_fake import FakeLLM, FakeResponse

INSIGHT = {"id": "I1", "title": "Monthly contracts churn most",
           "text": "Month-to-month customers churn at 42.7%.",
           "figures": [{"source_key": "eda_results.categorical.Contract.levels.0.churn_rate",
                        "value": 0.427, "display": "42.7%"}],
           "significant": True, "causality_note": "Associated with, not caused by."}
REC = {"id": "R1", "problem": "Monthly churn is 42.7%.", "action": "Offer annual plans.",
       "target_segment": "Month-to-month customers",
       "customers_affected": {"source_key": "impact_estimates.items.Contract=Month-to-month."
                                            "customers", "value": 3800, "display": "3,800"},
       "impact": {"source_key": "impact_estimates.items.Contract=Month-to-month.scenarios."
                                "reduce_10pct.churners_saved", "value": 153.7,
                  "assumption": "If churn fell 10%."},
       "effort": "low", "priority": 1, "group": "quick_win", "figures": []}


@pytest.fixture
def fake(monkeypatch):
    fake_llm = FakeLLM()
    llm.set_model_factory(fake_llm)
    monkeypatch.setattr(llm, "_sleep", lambda s: None)
    llm.reset_throttle()
    yield fake_llm
    llm.set_model_factory(None)


@pytest.fixture
def state() -> ChurnState:
    return ChurnState(**telco_state())


def test_insight_agent_uses_pro_tier_temp_0_and_digest(fake, state):
    fake.fixtures = {"InsightList": {"insights": [INSIGHT]}}
    update = insight_agent_node(state)
    assert update["insights"][0]["id"] == "I1"
    call = fake.calls[0]
    assert (call["model"], call["temperature"]) == ("test-pro-model", 0)
    assert "impact_estimates.items.Contract=Month-to-month" in call["prompt"]
    assert "8944-YQZDP" not in call["prompt"]  # no customer rows
    assert "Fix these issues" not in call["prompt"]


def test_feedback_is_included_on_retry(fake, state):
    fake.fixtures = {"InsightList": {"insights": [INSIGHT]}}
    retry_state = state.model_copy(update={"validator_feedback": {
        "insight_agent": ["I3: 55% is not in figures[]", "I4: key x.y does not exist"]}})
    insight_agent_node(retry_state)
    prompt = fake.calls[0]["prompt"]
    assert "Fix these issues" in prompt and "I3: 55% is not in figures[]" in prompt


def test_malformed_response_is_rejected_then_empty(fake, state):
    bad = {"insights": [{**INSIGHT, "significant": "maybe", "figures": "none"}]}
    fake.fixtures = {"InsightList": [bad]}
    update = insight_agent_node(state)
    assert update["insights"] == [] and len(fake.calls) == 2  # retried once
    assert update["progress"][0].status == "failed"


def test_failure_path_returns_empty_without_crashing(fake, state):
    fake.fixtures = {"RecommendationList": [FakeResponse(parsed=None, finish_reason="SAFETY")]}
    update = recommendation_agent_node(state)
    assert update["recommendations"] == []
    assert "LLM unavailable" in update["errors"][0].message
    assert update["errors"][0].fatal is False


def test_recommendation_agent_temp_and_ordering(fake, state):
    second = {**REC, "id": "R2", "priority": 3}
    fake.fixtures = {"RecommendationList": {"recommendations": [second, REC]}}
    update = recommendation_agent_node(state.model_copy(update={"insights": [INSIGHT]}))
    assert [r["id"] for r in update["recommendations"]] == ["R1", "R2"]
    call = fake.calls[0]
    assert call["temperature"] == 0.3
    assert json.dumps([INSIGHT])[:40] in call["prompt"]


def test_schemas_reject_bad_enums_and_limits():
    with pytest.raises(ValueError):
        RecommendationList.model_validate({"recommendations": [{**REC, "effort": "tiny"}]})
    with pytest.raises(ValueError):
        RecommendationList.model_validate({"recommendations": [{**REC, "priority": 9}]})
    with pytest.raises(ValueError):
        InsightList.model_validate({"insights": [INSIGHT] * 11})
