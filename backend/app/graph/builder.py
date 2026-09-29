"""Builds the ChurnLens LangGraph (docs/SPEC.md "Edges").

ingest -> schema_agent -> human_review -> cleaning
  -> [eda, segmentation, hypothesis, survival (only with a time column)]
  -> modelling -> impact -> [offer (only with offer columns)] -> insight_agent
  -> recommendation_agent -> validator -> report -> END
validator sends failing agents back (max 2 retries each, decided by the validator).
Any node that records a fatal error routes to error_node -> END.
"""

from collections.abc import Callable
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.errors import GraphBubbleUp
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.errors import FatalNodeError
from app.graph.state import ChurnState, ErrorEntry, ProgressEntry
from app.graph.telemetry import traced

NodeFn = Callable[[ChurnState], dict[str, Any]]

INGEST = "ingest"
SCHEMA_AGENT = "schema_agent"
HUMAN_REVIEW = "human_review"
CLEANING = "cleaning"
EDA = "eda"
SEGMENTATION = "segmentation"
SURVIVAL = "survival"
HYPOTHESIS = "hypothesis"
MODELLING = "modelling"
IMPACT = "impact"
OFFER = "offer"
INSIGHT_AGENT = "insight_agent"
RECOMMENDATION_AGENT = "recommendation_agent"
VALIDATOR = "validator"
REPORT = "report"
ERROR_NODE = "error_node"

ALL_NODES = (
    INGEST, SCHEMA_AGENT, HUMAN_REVIEW, CLEANING, EDA, SEGMENTATION, SURVIVAL,
    HYPOTHESIS, MODELLING, IMPACT, OFFER, INSIGHT_AGENT, RECOMMENDATION_AGENT,
    VALIDATOR, REPORT, ERROR_NODE,
)
PARALLEL_ANALYSIS = (EDA, SEGMENTATION, HYPOTHESIS)


def safe_node(name: str, fn: NodeFn) -> NodeFn:
    """Wrap a node so it never crashes the graph (CLAUDE.md rule 8)."""

    def wrapped(state: ChurnState) -> dict[str, Any]:
        try:
            return fn(state)
        except GraphBubbleUp:
            raise  # interrupt() and other control flow must reach LangGraph
        except FatalNodeError as exc:
            return {
                "errors": [ErrorEntry(node=name, message=str(exc), fatal=True)],
                "progress": [ProgressEntry(node=name, status="failed", detail=str(exc))],
            }
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            return {
                "errors": [ErrorEntry(node=name, message=message, fatal=False)],
                "progress": [ProgressEntry(node=name, status="failed", detail=message)],
            }

    wrapped.__name__ = f"{name}_node"
    return wrapped


def stub(name: str) -> NodeFn:
    def node(state: ChurnState) -> dict[str, Any]:
        return {"progress": [ProgressEntry(node=name, status="done", detail="stub")]}

    return node


def _error_node(state: ChurnState) -> dict[str, Any]:
    fatal = [e for e in state.errors if e.fatal]
    message = fatal[0].message if fatal else "The analysis stopped because of an error."
    return {
        "final_error": message,
        "progress": [ProgressEntry(node=ERROR_NODE, status="done", detail=message)],
    }


# ---------------------------------------------------------------- routers


def _next_or_error(next_node: str) -> Callable[[ChurnState], str]:
    def route(state: ChurnState) -> str:
        return ERROR_NODE if state.has_fatal_error() else next_node

    route.__name__ = f"to_{next_node}_or_error"
    return route


def route_after_cleaning(state: ChurnState) -> list[str] | str:
    if state.has_fatal_error():
        return ERROR_NODE
    branches = list(PARALLEL_ANALYSIS)
    if state.time_column:
        branches.append(SURVIVAL)
    return branches


def route_after_impact(state: ChurnState) -> str:
    if state.has_fatal_error():
        return ERROR_NODE
    return OFFER if state.offer_columns else INSIGHT_AGENT


def route_after_validator(state: ChurnState) -> str:
    """The validator lists agents to retry; it already enforced the retry cap."""
    report = state.validation_report or {}
    retry = report.get("retry_agents") or []
    for agent in (INSIGHT_AGENT, RECOMMENDATION_AGENT):
        if agent in retry:
            return agent
    return REPORT


# ---------------------------------------------------------------- build


def build_graph(
    nodes: dict[str, NodeFn] | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Compile the graph. `nodes` overrides node functions (stubs by default)."""
    impl: dict[str, NodeFn] = {name: stub(name) for name in ALL_NODES}
    impl[ERROR_NODE] = _error_node
    impl.update(nodes or {})

    graph = StateGraph(ChurnState)
    for name in ALL_NODES:
        # traced is outermost so failed runs (caught by safe_node) are timed too.
        graph.add_node(name, traced(name, safe_node(name, impl[name])))

    graph.add_edge(START, INGEST)
    graph.add_conditional_edges(INGEST, _next_or_error(SCHEMA_AGENT), [SCHEMA_AGENT, ERROR_NODE])
    graph.add_conditional_edges(
        SCHEMA_AGENT, _next_or_error(HUMAN_REVIEW), [HUMAN_REVIEW, ERROR_NODE]
    )
    graph.add_conditional_edges(HUMAN_REVIEW, _next_or_error(CLEANING), [CLEANING, ERROR_NODE])
    graph.add_conditional_edges(
        CLEANING, route_after_cleaning, [*PARALLEL_ANALYSIS, SURVIVAL, ERROR_NODE]
    )
    # All branches finish in the same superstep, so modelling runs once.
    for branch in (*PARALLEL_ANALYSIS, SURVIVAL):
        graph.add_edge(branch, MODELLING)
    graph.add_conditional_edges(MODELLING, _next_or_error(IMPACT), [IMPACT, ERROR_NODE])
    graph.add_conditional_edges(IMPACT, route_after_impact, [OFFER, INSIGHT_AGENT, ERROR_NODE])
    graph.add_edge(OFFER, INSIGHT_AGENT)
    graph.add_edge(INSIGHT_AGENT, RECOMMENDATION_AGENT)
    graph.add_edge(RECOMMENDATION_AGENT, VALIDATOR)
    graph.add_conditional_edges(
        VALIDATOR, route_after_validator, [INSIGHT_AGENT, RECOMMENDATION_AGENT, REPORT]
    )
    graph.add_edge(REPORT, END)
    graph.add_edge(ERROR_NODE, END)

    return graph.compile(checkpointer=checkpointer)
