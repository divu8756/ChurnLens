"""insight_agent and recommendation_agent (docs/SPEC.md nodes 11-12).

Both read only the compact digest (app/graph/results_digest.py), use
structured output, cite a source_key for every figure, and include the
validator's feedback on a retry. If Gemini fails, the node records an error
and returns an empty list so the dashboard still renders.
"""

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from app import llm
from app.graph.results_digest import build_digest
from app.graph.state import ChurnState, ErrorEntry, ProgressEntry
from app.prompts.loader import render_prompt

TIMEOUT_S = 60
MAX_INSIGHTS = 10
MAX_RECOMMENDATIONS = 8


class Figure(BaseModel):
    source_key: str
    value: float
    display: str


class Insight(BaseModel):
    id: str
    title: str
    text: str
    figures: list[Figure] = Field(default_factory=list)
    significant: bool
    causality_note: str = ""


class InsightList(BaseModel):
    insights: list[Insight] = Field(max_length=MAX_INSIGHTS)


class Impact(BaseModel):
    source_key: str
    value: float
    assumption: str


class Recommendation(BaseModel):
    id: str
    problem: str
    action: str
    target_segment: str
    customers_affected: Figure
    impact: Impact
    effort: Literal["low", "medium", "high"]
    priority: int = Field(ge=1, le=5)
    group: Literal["quick_win", "medium_term", "strategic"]
    figures: list[Figure] = Field(default_factory=list)


class RecommendationList(BaseModel):
    recommendations: list[Recommendation] = Field(max_length=MAX_RECOMMENDATIONS)


def feedback_text(state: ChurnState, agent: str) -> str:
    issues = (state.validator_feedback or {}).get(agent) or []
    if not issues:
        return ""
    lines = "\n".join(f"- {issue}" for issue in issues)
    return f"\nFix these issues from the previous attempt:\n{lines}\n"


def _digest(state: ChurnState) -> str:
    return json.dumps(build_digest(state.model_dump(mode="json")), ensure_ascii=False)


def insight_agent_node(state: ChurnState) -> dict[str, Any]:
    prompt = render_prompt("insight_agent", 1, digest_json=_digest(state),
                           feedback=feedback_text(state, "insight_agent"))
    try:
        result = llm.structured_call("pro", 0, prompt, InsightList, timeout_s=TIMEOUT_S)
    except llm.LLMUnavailable as exc:
        # On a retry, keep the previous answer so only its failing items get dropped.
        return {"insights": state.insights,
                "errors": [ErrorEntry(node="insight_agent", message=f"LLM unavailable: {exc}")],
                "progress": [ProgressEntry(node="insight_agent", status="failed",
                                           detail="AI insights unavailable")]}
    insights = [i.model_dump() for i in result.insights]
    return {"insights": insights,
            "progress": [ProgressEntry(node="insight_agent", status="done",
                                       detail=f"{len(insights)} insights")]}


def recommendation_agent_node(state: ChurnState) -> dict[str, Any]:
    prompt = render_prompt(
        "recommendation_agent", 1, digest_json=_digest(state),
        insights_json=json.dumps(state.insights, ensure_ascii=False),
        feedback=feedback_text(state, "recommendation_agent"))
    try:
        result = llm.structured_call("pro", 0.3, prompt, RecommendationList, timeout_s=TIMEOUT_S)
    except llm.LLMUnavailable as exc:
        return {"recommendations": state.recommendations,
                "errors": [ErrorEntry(node="recommendation_agent",
                                      message=f"LLM unavailable: {exc}")],
                "progress": [ProgressEntry(node="recommendation_agent", status="failed",
                                           detail="AI recommendations unavailable")]}
    recs = sorted((r.model_dump() for r in result.recommendations),
                  key=lambda r: (r["priority"], r["id"]))
    return {"recommendations": recs,
            "progress": [ProgressEntry(node="recommendation_agent", status="done",
                                       detail=f"{len(recs)} recommendations")]}
