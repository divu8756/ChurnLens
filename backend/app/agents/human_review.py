"""human_review: pause the graph until the user confirms the schema.

This node re-runs from the top when the graph resumes, so it must do nothing
before interrupt(): no LLM calls, no file writes. The API validates the
user's answer before resuming (app/schema_validation.py).
"""

from typing import Any

from langgraph.types import interrupt

from app.graph.state import ChurnState, ProgressEntry


def human_review_node(state: ChurnState) -> dict[str, Any]:
    confirmed: dict[str, Any] = interrupt({"proposal": state.schema_proposal})
    return {
        "confirmed_schema": confirmed,
        "target_column": confirmed["target_column"],
        "positive_label": confirmed["positive_label"],
        "target_confirmed": True,
        "id_columns": confirmed.get("id_columns", []),
        "time_column": confirmed.get("time_column"),
        "offer_columns": confirmed.get("offer_columns"),
        "progress": [ProgressEntry(node="human_review", status="done",
                                   detail="schema confirmed")],
    }
