"""schema_agent: propose column types, target, ids and time column.

The LLM (fast tier, temperature 0) sees only the column profile: names,
dtypes, 5 sample values, null % and unique counts. Python heuristics run
first; they win on ID columns and are the fallback if the LLM fails.
"""

import json
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, Field

from app import llm
from app.graph.errors import FatalNodeError
from app.graph.state import ChurnState, ErrorEntry, ProgressEntry
from app.prompts.loader import render_prompt
from app.stats import profiling

PROMPT = ("schema_agent", 1)
TIMEOUT_S = 30
# The rules are a good fallback, so fail fast instead of making the user wait.
MAX_ATTEMPTS = 2

SemanticType = Literal["id", "numeric", "categorical", "binary", "datetime", "text"]


class ColumnProposal(BaseModel):
    name: str
    semantic_type: SemanticType
    confidence: float = Field(ge=0, le=1)


class SchemaProposal(BaseModel):
    columns: list[ColumnProposal]
    target_column: str | None = None
    positive_label: str | None = None
    id_columns: list[str] = Field(default_factory=list)
    time_column: str | None = None
    reasoning: str = ""


def build_prompt(frame: pd.DataFrame) -> str:
    profile = profiling.profile_columns(frame)
    return render_prompt(*PROMPT, profile_json=json.dumps(profile, ensure_ascii=False))


def merge(frame: pd.DataFrame, heur: dict[str, Any], proposal: SchemaProposal) -> dict[str, Any]:
    """Heuristics win on IDs; the LLM proposes the rest if it is valid for this data."""
    names = [str(c) for c in frame.columns]
    heur_ids = set(heur["id_columns"])
    by_name = {c.name: c for c in proposal.columns if c.name in names}

    columns = []
    for h in heur["columns"]:
        name = h["name"]
        if name in heur_ids:
            columns.append({"name": name, "semantic_type": "id", "confidence": 0.95})
        elif name in by_name:
            columns.append(by_name[name].model_dump())
        else:
            columns.append(h)

    llm_ids = [c for c in proposal.id_columns if c in names]
    id_columns = [n for n in names if n in heur_ids or n in llm_ids]
    for col in columns:
        if col["name"] in id_columns:
            col["semantic_type"] = "id"

    target, positive = heur["target_column"], heur["positive_label"]
    notes = []
    if proposal.target_column and proposal.target_column in names:
        values = profiling.binary_values(frame[proposal.target_column])
        if values is not None and proposal.target_column not in id_columns:
            target = proposal.target_column
            positive = (proposal.positive_label if proposal.positive_label in values
                        else profiling.guess_positive_label(values, frame[target]))
        else:
            notes.append(f"AI target '{proposal.target_column}' is not binary; kept the rule.")
    elif proposal.target_column:
        notes.append(f"AI target '{proposal.target_column}' is not a column; kept the rule.")

    time_column = heur["time_column"]
    if proposal.time_column in names and profiling.heuristic_type(
            frame[proposal.time_column], False) == "numeric":
        time_column = proposal.time_column

    return {
        "columns": columns,
        "target_column": target,
        "positive_label": positive,
        "id_columns": id_columns,
        "time_column": time_column,
        "reasoning": " ".join([proposal.reasoning, *notes]).strip(),
        "source": "ai+rules",
    }


def schema_agent_node(state: ChurnState) -> dict[str, Any]:
    if not state.raw_path:
        raise FatalNodeError("No uploaded data to describe.")
    frame = pd.read_parquet(state.raw_path)
    heur = profiling.heuristic_schema(frame)
    errors: list[ErrorEntry] = []
    try:
        proposal = llm.structured_call("fast", 0, build_prompt(frame), SchemaProposal,
                                       timeout_s=TIMEOUT_S, max_attempts=MAX_ATTEMPTS)
        result = merge(frame, heur, proposal)
        detail = "AI proposal merged with rules"
    except llm.LLMUnavailable as exc:
        result = {**heur, "source": "rules"}
        detail = "AI unavailable; proposal from rules only"
        errors.append(ErrorEntry(node="schema_agent", message=f"LLM fallback: {exc}"))

    result["target_candidates"] = profiling.likely_targets(frame)
    return {
        "schema_proposal": result,
        "errors": errors,
        "progress": [ProgressEntry(node="schema_agent", status="done", detail=detail)],
    }
