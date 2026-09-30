"""Ask the Data agent (runbook T7.1): a small LangGraph ReAct loop.

agent -> (call_tool -> tools -> agent)* -> answer | refuse
Each LLM step returns a structured ChatStep through the Gemini wrapper (CLAUDE.md rules 5
and 16); tools are whitelisted (app/chat/tools.py). At most MAX_TOOL_CALLS per question.
The final answer's numbers must come from this question's tool results (rule 4): one
retry with feedback, then a safe message instead of unverified numbers.
"""

import json
import operator
from typing import Annotated, Any, Literal

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from app import llm
from app.chat.tools import STAT_ROOTS, ChatData, Filter, Metric, ToolName, run_tool
from app.prompts.loader import render_prompt
from app.validation import check_text, numbers_in

PROMPT = ("chat_agent", 1)
MAX_TOOL_CALLS = 6
MAX_ANSWER_RETRIES = 1
HISTORY_MESSAGES = 10
TIMEOUT_S = 45
UNVERIFIED = ("I could not back every number in my draft answer with the analysis, so I "
              "won't show it. Try a more specific question, for example about one column or "
              "segment.")
LIMIT = (f"I reached the limit of {MAX_TOOL_CALLS} lookups for one question without a "
         "complete answer. Try asking something narrower.")
UNAVAILABLE = "The AI service is not available right now. Please try again in a minute."
TOOL_ARGS = {
    "get_stat": ("key",), "get_segment": ("segment_id",), "get_test_result": ("variable",),
    "get_customer_risk": ("customer_id",),
    "filter_and_aggregate": ("filters", "group_by", "metric", "column"),
}


class ChatStep(BaseModel):
    """One ReAct step. Flat on purpose (Gemini-friendly structured output)."""

    action: Literal["call_tool", "answer", "refuse"]
    tool: ToolName | None = None
    key: str | None = None
    segment_id: int | None = None
    variable: str | None = None
    customer_id: str | None = None
    filters: list[Filter] = Field(default_factory=list)
    group_by: str | None = None
    metric: Metric | None = None
    column: str | None = None
    answer: str | None = None


class ChatState(TypedDict, total=False):
    question: str
    history: list[dict[str, str]]
    steps: Annotated[list[dict[str, Any]], operator.add]
    pending: dict[str, Any] | None
    feedback: str
    answer_retries: int
    answer: str
    status: str


def _numbers(value: Any) -> list[float]:
    """Every number inside a tool result (the only numbers an answer may use)."""
    if isinstance(value, bool) or value is None:
        return []
    if isinstance(value, int | float):
        return [float(value)]
    if isinstance(value, dict):
        return [n for v in value.values() for n in _numbers(v)]
    if isinstance(value, list):
        return [n for v in value for n in _numbers(v)]
    if isinstance(value, str):
        return [n for n, _ in numbers_in(value)]
    return []


def check_answer(answer: str, question: str, steps: list[dict[str, Any]]) -> list[str]:
    allowed = [{"value": n} for s in steps for n in _numbers(s["result"])]
    allowed += [{"value": n} for n, _ in numbers_in(question)]
    return check_text(answer, allowed)


def build_chat_graph(data: ChatData) -> Any:
    columns = ", ".join(data.columns())[:3000] or "(no columns available)"

    def agent(state: ChatState) -> dict[str, Any]:
        steps = state.get("steps", [])
        prompt = render_prompt(
            *PROMPT, max_tools=str(MAX_TOOL_CALLS),
            calls_left=str(MAX_TOOL_CALLS - len(steps)), stat_roots=", ".join(STAT_ROOTS),
            columns=columns, feedback=state.get("feedback", ""),
            history="\n".join(f"{m['role']}: {m['text']}" for m in state.get("history", []))
            or "(none)",
            steps=json.dumps(steps, ensure_ascii=False, default=str) if steps else "(none)",
            question=state["question"])
        try:
            step = llm.structured_call("pro", 0.0, prompt, ChatStep, timeout_s=TIMEOUT_S,
                                       max_attempts=2)
        except llm.LLMUnavailable:
            return {"answer": UNAVAILABLE, "status": "unavailable", "pending": None}
        if step.action == "refuse":
            return {"answer": step.answer or "I can only answer questions about this "
                    "dataset.", "status": "refused", "pending": None}
        if step.action == "answer":
            text = (step.answer or "").strip()
            problems = check_answer(text, state["question"], steps) if text else ["empty"]
            if not problems:
                return {"answer": text, "status": "answered", "pending": None}
            if state.get("answer_retries", 0) < MAX_ANSWER_RETRIES:
                feedback = ("Your last answer used numbers that are not in the tool results: "
                            + "; ".join(problems) + ". Use only tool-result numbers, or call "
                            "a tool to get them.")
                return {"feedback": feedback, "pending": None,
                        "answer_retries": state.get("answer_retries", 0) + 1}
            return {"answer": UNVERIFIED, "status": "unverified", "pending": None}
        if len(steps) >= MAX_TOOL_CALLS:
            return {"answer": LIMIT, "status": "limit", "pending": None}
        args = {k: v for k in TOOL_ARGS.get(step.tool or "", ())
                if (v := getattr(step, k)) not in (None, [])}
        if step.tool == "filter_and_aggregate":
            args["filters"] = [f.model_dump(exclude_none=True) for f in step.filters]
        return {"pending": {"tool": step.tool, "args": args}}

    def tools(state: ChatState) -> dict[str, Any]:
        call = state["pending"] or {}
        result = run_tool(data, str(call.get("tool")), call.get("args") or {})
        return {"steps": [{"tool": call.get("tool"), "args": call.get("args"),
                           "result": result}], "pending": None}

    def route(state: ChatState) -> str:
        if state.get("status"):
            return END
        return "tools" if state.get("pending") else "agent"

    graph = StateGraph(ChatState)
    graph.add_node("agent", agent)
    graph.add_node("tools", tools)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route, ["tools", "agent", END])
    graph.add_edge("tools", "agent")
    return graph.compile()


def ask(values: dict[str, Any], question: str, history: list[dict[str, str]]
        ) -> dict[str, Any]:
    """Answer one question. Returns answer, status and the tools used."""
    graph = build_chat_graph(ChatData(values))
    # Each tool call is 2 steps and each answer retry 1; keep a safety margin.
    final = graph.invoke({"question": question, "history": history[-HISTORY_MESSAGES:],
                          "steps": [], "answer_retries": 0, "feedback": ""},
                         {"recursion_limit": 4 * MAX_TOOL_CALLS + 10})
    steps = final.get("steps", [])
    return {"answer": final.get("answer", UNAVAILABLE), "status": final.get("status", "error"),
            "tools_used": [{"tool": s["tool"], "args": s["args"],
                            "error": s["result"].get("error")
                            if isinstance(s["result"], dict) else None} for s in steps]}
