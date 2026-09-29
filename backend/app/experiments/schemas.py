"""API models for /experiments (they feed frontend/openapi.json)."""

from datetime import date, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.experiments.segments import SegmentDefinition, SegmentFilter

Guardrail = Literal["complaints", "arpu"]
SESSION_ID = r"^[0-9a-f]{32}$"


class NamedSegment(BaseModel):
    """A segment registered before approval, analysed separately (exploratory)."""

    name: str = Field(min_length=1, max_length=100)
    filters: list[SegmentFilter] = Field(min_length=1, max_length=20)


class ExperimentDesignFields(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    hypothesis: str = Field(min_length=1, max_length=2000)
    source_recommendation_id: str | None = Field(default=None, max_length=100)
    session_id: str | None = Field(default=None, pattern=SESSION_ID)
    segment_definition: SegmentDefinition = Field(default_factory=SegmentDefinition)
    offer: str = Field(min_length=1, max_length=200)
    outcome_window_days: int = Field(default=90, ge=1, le=730)
    guardrail_metrics: list[Guardrail] = Field(default_factory=lambda: ["complaints", "arpu"])
    # None = measured churn rate of the segment in the session's data.
    baseline_rate: float | None = Field(default=None, gt=0, lt=1)
    mde: float = Field(gt=0)
    mde_type: Literal["absolute", "relative"] = "absolute"
    alpha: float = 0.05
    power: float = 0.8
    control_share: float = 0.5
    monthly_volume: int | None = Field(default=None, gt=0)
    planned_start: date | None = None
    planned_end: date | None = None
    preregistered_segments: list[NamedSegment] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def _check(self) -> Self:
        names = [s.name for s in self.preregistered_segments]
        if len(names) != len(set(names)):
            raise ValueError("Pre-registered segment names must be unique.")
        if self.planned_start and self.planned_end and self.planned_end < self.planned_start:
            raise ValueError("planned_end must be on or after planned_start.")
        if self.baseline_rate is None and self.session_id is None:
            raise ValueError("Give a baseline_rate or a session_id to measure it from.")
        return self


class ExperimentCreate(ExperimentDesignFields):
    created_by: str = Field(min_length=1, max_length=100)


class ExperimentUpdate(BaseModel):
    """Fields to change while the experiment is a draft; omitted fields stay as they are."""

    model_config = ConfigDict(extra="forbid")
    actor: str = Field(min_length=1, max_length=100)
    name: str | None = None
    hypothesis: str | None = None
    source_recommendation_id: str | None = None
    session_id: str | None = None
    segment_definition: SegmentDefinition | None = None
    offer: str | None = None
    outcome_window_days: int | None = None
    guardrail_metrics: list[Guardrail] | None = None
    baseline_rate: float | None = None
    mde: float | None = None
    mde_type: Literal["absolute", "relative"] | None = None
    alpha: float | None = None
    power: float | None = None
    control_share: float | None = None
    monthly_volume: int | None = None
    planned_start: date | None = None
    planned_end: date | None = None
    preregistered_segments: list[NamedSegment] | None = None


class ApproveRequest(BaseModel):
    approver: str = Field(min_length=1, max_length=100)
    cost_and_eligibility_reviewed: bool
    note: str | None = Field(default=None, max_length=2000)


class AssignRequest(BaseModel):
    session_id: str = Field(pattern=SESSION_ID)
    actor: str = Field(min_length=1, max_length=100)


class AnalysisAssumptions(BaseModel):
    """Money and guardrail assumptions for the results analysis. customer_value
    defaults to the data estimate made at assignment (mean monthly revenue x horizon)."""

    customer_value: float | None = Field(default=None, ge=0)
    offer_cost: float | None = Field(default=None, ge=0)
    arpu_tolerance: float = Field(default=0.05, ge=0, le=1)


class DecideRequest(BaseModel):
    decision: Literal["ship", "dont_ship", "extend"]
    decider: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=1, max_length=2000)
    # Only for "extend": when the longer test should end.
    new_planned_end: date | None = None


class OfferEvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    experiment_id: int
    offer: str
    segment_description: str | None
    decision: str
    decided_at: datetime
    n_treatment: int
    n_control: int
    treatment_churn: float
    control_churn: float
    itt_difference: float
    ci_low: float
    ci_high: float
    acceptance_rate: float | None
    retention_lift_per_acceptor: float | None


class SummaryFigure(BaseModel):
    source_key: str
    value: float
    display: str


class ExperimentSummaryOut(BaseModel):
    sentences: list[str]
    figures: list[SummaryFigure]
    source: Literal["ai", "template"]
    verdict: str
    problems: list[str]


class ReanalyseRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=100)
    assumptions: AnalysisAssumptions


class AuditEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    at: datetime
    actor: str
    action: str
    from_status: str | None
    to_status: str | None
    note: str | None
    details: dict[str, Any] | None


class BalanceRow(BaseModel):
    covariate: str
    level: str | None
    smd: float | None
    treatment_mean: float | None
    control_mean: float | None
    flagged: bool


class BalanceOut(BaseModel):
    threshold: float
    n_treatment: int
    n_control: int
    covariates: list[BalanceRow]
    balanced: bool
    flagged: list[str]


class AssignmentSummaryOut(BaseModel):
    segment_customers: int
    excluded_other_experiments: int
    assigned: int
    n_treatment: int
    n_control: int
    required_treatment: int
    required_control: int
    messages_attached: int
    customer_value_estimate: float | None = None
    data_snapshot_hash: str
    balance: BalanceOut
    warnings: list[str]


class ExperimentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    offer: str
    status: str
    created_by: str
    created_at: datetime
    decision: str | None


class ExperimentOut(ExperimentSummary):
    hypothesis: str
    source_recommendation_id: str | None
    source_session_id: str | None
    segment_definition: SegmentDefinition
    primary_metric: str
    outcome_window_days: int
    guardrail_metrics: list[str]
    baseline_rate: float
    mde: float
    mde_type: str
    alpha: float
    power: float
    control_share: float
    n_required_treatment: int
    n_required_control: int
    planned_start: date | None
    planned_end: date | None
    approved_by: str | None
    approved_at: datetime | None
    decision_note: str | None
    data_snapshot_hash: str | None
    design: dict[str, Any] | None
    preregistered_segments: list[NamedSegment] | None
    analysis: dict[str, Any] | None
    results_uploaded_at: datetime | None
    assignment_summary: AssignmentSummaryOut | None
    audit: list[AuditEntryOut] = Field(default_factory=list)
