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


class DesignInputs(BaseModel):
    """What the sample size depends on; POST /experiments/design previews it live."""

    source_recommendation_id: str | None = Field(default=None, max_length=100)
    session_id: str | None = Field(default=None, pattern=SESSION_ID)
    segment_definition: SegmentDefinition = Field(default_factory=SegmentDefinition)
    # None = measured churn rate of the segment in the session's data.
    baseline_rate: float | None = Field(default=None, gt=0, lt=1)
    mde: float = Field(gt=0)
    mde_type: Literal["absolute", "relative"] = "absolute"
    alpha: float = 0.05
    power: float = 0.8
    control_share: float = 0.5
    monthly_volume: int | None = Field(default=None, gt=0)
    preregistered_segments: list[NamedSegment] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def _check_inputs(self) -> Self:
        names = [s.name for s in self.preregistered_segments]
        if len(names) != len(set(names)):
            raise ValueError("Pre-registered segment names must be unique.")
        if self.baseline_rate is None and self.session_id is None:
            raise ValueError("Give a baseline_rate or a session_id to measure it from.")
        return self


class ExperimentDesignFields(DesignInputs):
    name: str = Field(min_length=1, max_length=200)
    hypothesis: str = Field(min_length=1, max_length=2000)
    offer: str = Field(min_length=1, max_length=200)
    outcome_window_days: int = Field(default=90, ge=1, le=730)
    guardrail_metrics: list[Guardrail] = Field(default_factory=lambda: ["complaints", "arpu"])
    planned_start: date | None = None
    planned_end: date | None = None

    @model_validator(mode="after")
    def _check_dates(self) -> Self:
        if self.planned_start and self.planned_end and self.planned_end < self.planned_start:
            raise ValueError("planned_end must be on or after planned_start.")
        return self


class SegmentColumn(BaseModel):
    column: str
    kind: Literal["numeric", "categorical"]
    levels: list[str] = Field(default_factory=list)  # most common first (categorical only)
    min: float | None = None
    max: float | None = None


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


class DemoRequest(BaseModel):
    session_id: str = Field(pattern=SESSION_ID)


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
    demo: bool = False


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
    design: DesignOut | None
    preregistered_segments: list[NamedSegment] | None
    analysis: AnalysisOut | None
    results_uploaded_at: datetime | None
    assignment_summary: AssignmentSummaryOut | None
    audit: list[AuditEntryOut] = Field(default_factory=list)


# ---------------------------------------------------------------- design and analysis
# Typed views of stats/experiment_design.sample_size and stats/experiment_analysis.analyse.


class Assumption(BaseModel):
    name: str
    value: float | None
    source: Literal["default", "user", "data"]


class DesignInputsEcho(BaseModel):
    baseline_rate: float
    mde: float
    mde_type: Literal["absolute", "relative"]
    alpha: float
    power: float
    control_share: float
    alternative: str
    n_available: int | None = None
    monthly_volume: int | None = None


class DetectableEffect(BaseModel):
    treatment_rate: float
    absolute: float
    relative: float
    effect_size_h: float


class DesignOut(BaseModel):
    inputs: DesignInputsEcho
    treatment_rate: float
    absolute_mde: float
    relative_mde: float
    effect_size_h: float
    n_treatment: int
    n_control: int
    n_total: int
    formula: str
    feasible: bool | None = None
    detectable_with_available: DetectableEffect | None = None
    duration_months: float | None = None
    duration_days: int | None = None
    warnings: list[str] = Field(default_factory=list)
    measured_segment_churn: float | None = None
    assumptions: list[Assumption] = Field(default_factory=list)


class ArmRate(BaseModel):
    n: int
    churned: int
    rate: float
    ci_low: float
    ci_high: float


class ArmRates(BaseModel):
    treatment: ArmRate
    control: ArmRate


class RateDifference(BaseModel):
    value: float
    ci_low: float
    ci_high: float
    method: str
    ci_level: float


class RateComparison(BaseModel):
    arms: ArmRates | None = None
    difference: RateDifference | None = None
    relative_lift: float | None = None
    z: float | None = None
    p_value: float | None = None
    significant: bool = False


class IttOut(RateComparison):
    achieved_power: float | None = None
    label: str


class PerProtocolOut(RateComparison):
    label: str
    available: bool


class SegmentResultOut(RateComparison):
    n: int
    skipped: str | None = None
    p_adjusted: float | None = None


class SegmentsOut(BaseModel):
    label: str
    method: str
    items: dict[str, SegmentResultOut]


class ArmCounts(BaseModel):
    treatment: int
    control: int


class ArmShares(BaseModel):
    treatment: float
    control: float


class SrmOut(BaseModel):
    observed: ArmCounts
    expected: ArmShares
    planned_control_share: float
    observed_control_share: float | None
    chi2: float
    p_value: float
    threshold: float
    failed: bool


class ImpactOut(BaseModel):
    customers_saved: float
    saved_ci_low: float
    saved_ci_high: float
    acceptors: int
    acceptance_rate: float | None
    customer_value: float | None
    offer_cost: float | None
    total_offer_cost: float | None
    net_value: float | None
    net_value_ci_low: float | None
    net_value_ci_high: float | None
    formula: str
    assumptions: list[Assumption]


class MeanCI(BaseModel):
    n: int
    mean: float | None
    ci_low: float | None
    ci_high: float | None


class ArmMeans(BaseModel):
    treatment: MeanCI
    control: MeanCI


class MeanDifference(BaseModel):
    value: float
    ci_low: float | None
    ci_high: float | None


class GuardrailOut(BaseModel):
    arms: ArmMeans
    bad_direction: Literal["up", "down"]
    tolerance: float
    breached: bool
    difference: MeanDifference | None = None


class DecisionHelperOut(BaseModel):
    verdict: Literal["ship", "dont_ship", "inconclusive", "untrustworthy"]
    reasons: list[str]
    guardrails_breached: list[str]
    extra_sample_needed: ArmCounts | None
    note: str


class UploadInfo(BaseModel):
    rows: int
    file_sha256: str
    uploaded_by: str
    early_look: bool
    warnings: list[str]


class AnalysisOut(BaseModel):
    srm: SrmOut
    itt: IttOut
    impact: ImpactOut
    per_protocol: PerProtocolOut
    guardrails: dict[str, GuardrailOut]
    segments: SegmentsOut | None = None
    assumptions: list[Assumption]
    decision_helper: DecisionHelperOut
    upload: UploadInfo | None = None
    warnings: list[str] = Field(default_factory=list)
    assumption_inputs: AnalysisAssumptions | None = None
    summary: ExperimentSummaryOut | None = None


ExperimentOut.model_rebuild()
