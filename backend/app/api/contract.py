"""Response and SSE event models that form the typed contract with the frontend.

The frontend generates TypeScript from the OpenAPI schema (npm run gen:types),
so every shape the browser reads is declared here or on a router.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schema_validation import SemanticType

RunStatus = Literal["running", "awaiting_confirmation", "done", "failed", "interrupted"]
NodeStatus = Literal["started", "done", "skipped", "failed"]
RiskBand = Literal["High", "Medium", "Low"]


class ProposedColumn(BaseModel):
    name: str
    semantic_type: SemanticType
    confidence: float


class SchemaProposalOut(BaseModel):
    columns: list[ProposedColumn]
    target_column: str | None = None
    positive_label: str | None = None
    id_columns: list[str] = Field(default_factory=list)
    time_column: str | None = None
    revenue_column: str | None = None
    reasoning: str = ""
    source: Literal["ai+rules", "rules"]
    target_candidates: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------ SSE events
# Each model is the JSON in the `data:` line; the `event:` line carries the name
# (see StreamEvents). Heartbeats have data {}.

class NodeStartEvent(BaseModel):
    node: str


class NodeFinishEvent(BaseModel):
    node: str
    status: NodeStatus
    detail: str | None = None


class ErrorEvent(BaseModel):
    node: str | None = None
    message: str
    fatal: bool = False


class AwaitingConfirmationEvent(BaseModel):
    proposal: SchemaProposalOut | None = None


class DoneEvent(BaseModel):
    ok: bool
    final_error: str | None = None


class StreamEvents(BaseModel):
    """Documentation only: the payload type of each SSE event name."""

    node_start: NodeStartEvent
    node_finish: NodeFinishEvent
    error: ErrorEvent
    awaiting_confirmation: AwaitingConfirmationEvent
    resumed: dict[str, Any]
    heartbeat: dict[str, Any]
    done: DoneEvent


# --------------------------------------------------------------------- results

class PredictionsPage(BaseModel):
    available: bool
    page: int
    page_size: int
    total: int
    pages: int
    band: RiskBand | None = None
    items: list[dict[str, Any]]


class ResultsResponse(BaseModel):
    session_id: str
    status: RunStatus
    # Typed per dashboard tab as the tabs are built (T6.3).
    results: dict[str, Any]
    predictions: PredictionsPage


class HTTPErrorOut(BaseModel):
    detail: str


class SchemaProblems(BaseModel):
    message: str
    problems: list[str]


class SchemaProblemsOut(BaseModel):
    """Body of a 422 from POST /confirm-schema when the schema does not fit the data."""

    detail: SchemaProblems
