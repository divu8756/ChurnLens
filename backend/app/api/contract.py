"""Response and SSE event models that form the typed contract with the frontend.

The frontend generates TypeScript from the OpenAPI schema (npm run gen:types),
so every shape the browser reads is declared here or on a router.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agents.llm_agents import Insight, Recommendation
from app.schema_validation import SemanticType

RunStatus = Literal["running", "awaiting_confirmation", "done", "failed", "interrupted"]
NodeStatus = Literal["started", "done", "skipped", "failed"]
RiskBand = Literal["High", "Medium", "Low"]


class ProposedColumn(BaseModel):
    name: str
    semantic_type: SemanticType
    confidence: float


class LabelOption(BaseModel):
    column: str
    values: list[str]


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
    label_options: list[LabelOption] = Field(default_factory=list)


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


class CleaningStep(BaseModel):
    step: str
    column: str | None = None
    rows_affected: int
    detail: str


class OutlierCounts(BaseModel):
    iqr: int
    zscore: int


class ClassBalance(BaseModel):
    positive: int
    negative: int
    positive_rate: float
    positive_label: str


class DataHealth(BaseModel):
    rows_before: int
    rows_after: int
    columns: int
    duplicates_removed: int
    missing_pct_before: dict[str, float]
    missing_pct_after: dict[str, float]
    outliers_flagged: dict[str, OutlierCounts]
    class_balance: ClassBalance
    health_score: int
    score_formula: str


class Passthrough(BaseModel):
    """Typed fields the dashboard reads; other keys pass through untouched."""

    model_config = ConfigDict(extra="allow")


class HeldOutMetrics(Passthrough):
    # None when undefined (e.g. no positive predictions); NaN becomes null in JSON.
    roc_auc: float | None = None
    pr_auc: float | None = None
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    n_test: int


class RiskBands(Passthrough):
    thresholds: dict[str, float]
    band_counts: dict[str, int]
    total: int


class ModelMetrics(Passthrough):
    chosen_model: str
    chosen_model_name: str
    test: HeldOutMetrics
    n_train: int
    n_test: int
    risk_bands: RiskBands | None = None


class ImpactGroup(Passthrough):
    id: str
    label: str
    customers: int
    churners: int
    churn_rate: float
    monthly_revenue_at_risk: float | None = None


class ImpactEstimates(Passthrough):
    overall: ImpactGroup
    revenue_column: str | None = None
    revenue_note: str | None = None


class ValidationReport(Passthrough):
    checked: int
    passed: int
    failed: int
    dropped: int
    final: bool


class ResultsPayload(BaseModel):
    """Keys the dashboard reads are typed; the rest pass through until their tab is built."""

    model_config = ConfigDict(extra="allow")

    target_column: str | None = None
    positive_label: str | None = None
    cleaning_log: list[CleaningStep] | None = None
    data_health: DataHealth | None = None
    model_metrics: ModelMetrics | None = None
    impact_estimates: ImpactEstimates | None = None
    final_insights: list[Insight] | None = None
    final_recommendations: list[Recommendation] | None = None
    validation_report: ValidationReport | None = None
    final_error: str | None = None
    errors: list[ErrorEvent] = Field(default_factory=list)


class ResultsResponse(BaseModel):
    session_id: str
    status: RunStatus
    results: ResultsPayload
    predictions: PredictionsPage


class HTTPErrorOut(BaseModel):
    detail: str


class SchemaProblems(BaseModel):
    message: str
    problems: list[str]


class SchemaProblemsOut(BaseModel):
    """Body of a 422 from POST /confirm-schema when the schema does not fit the data."""

    detail: SchemaProblems
