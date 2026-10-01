"""Typed responses for /metrics and /telemetry (Phase 5d); they feed frontend/openapi.json."""

from typing import Any, Literal

from pydantic import BaseModel, Field

Source = Literal["default", "user", "data"]


# ---------------------------------------------------------------- model metrics


class TopShare(BaseModel):
    share: float
    k: int
    churners_in_top: int
    precision: float
    recall: float | None = None


class Decile(BaseModel):
    decile: int
    n: int
    churners: int
    churn_rate: float | None = None
    lift: float | None = None
    cumulative_gain: float | None = None
    cumulative_share: float


class CalibrationBin(BaseModel):
    bin: int
    low: float
    high: float
    n: int
    mean_predicted: float | None = None
    observed_rate: float | None = None


class RocCurve(BaseModel):
    fpr: list[float]
    tpr: list[float]


class PrCurve(BaseModel):
    recall: list[float]
    precision: list[float]


class ScoreSet(BaseModel):
    n: int
    churn_rate: float
    roc_auc: float | None = None
    pr_auc: float | None = None
    brier: float
    top_10pct: TopShare
    deciles: list[Decile]
    calibration: list[CalibrationBin]
    roc_curve: RocCurve | None = None
    pr_curve: PrCurve | None = None


class ModelMetricsV2(BaseModel):
    split: str
    n_train: int
    n_test: int
    raw: ScoreSet
    calibrated: ScoreSet
    calibration_method: Literal["isotonic", "sigmoid"]
    calibration_note: str
    definitions: dict[str, str] = Field(default_factory=dict)
    chosen_model_name: str | None = None


# ---------------------------------------------------------------- business metrics


class BusinessAssumption(BaseModel):
    name: str
    value: float | None = None
    unit: str
    source: Source
    meaning: str


class RevenueAtRisk(BaseModel):
    total: float
    customers: int
    months_remaining: float
    arpu_column: str
    formula: str


class BusinessKpis(BaseModel):
    revenue_at_risk: float
    expected_saving: float
    customers_with_offer: int
    customers_scored: int
    overall_roi: float | None = None


class OfferTotals(BaseModel):
    offer: str
    customers: int
    expected_saving: float
    expected_cost: float


class SegmentRoi(BaseModel):
    segment: str
    customers: int
    total_expected_saving: float
    total_expected_cost: float
    roi: float | None = None


class OfferUsed(BaseModel):
    name: str
    acceptance: float
    save_rate: float
    cost: float
    cost_basis: Literal["per_accepted", "per_targeted"]
    sources: dict[str, Source]


class NboRow(BaseModel):
    customer_id: str
    risk_band: str
    p_churn: float
    arpu: float
    best_offer: str
    expected_saving: float
    expected_cost: float
    eligible_offers: int
    runner_up: str | None = None
    runner_up_saving: float | None = None


class AbPlan(BaseModel):
    available: bool
    segment: str
    reason: str | None = None
    segment_customers: int | None = None
    p1: float | None = None
    p2: float | None = None
    relative_lift: float | None = None
    cohens_h: float | None = None
    alpha: float | None = None
    power: float | None = None
    z_alpha: float | None = None
    z_beta: float | None = None
    n_per_arm: int | None = None
    n_second_arm: int | None = None
    total_n: int | None = None
    formula_latex: str | None = None
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[BusinessAssumption] = Field(default_factory=list)


class BusinessMetrics(BaseModel):
    enabled: bool
    reason: str | None = None
    revenue_at_risk: RevenueAtRisk | None = None
    kpis: BusinessKpis | None = None
    by_offer: list[OfferTotals] = Field(default_factory=list)
    roi_by_segment: list[SegmentRoi] = Field(default_factory=list)
    offers: list[OfferUsed] = Field(default_factory=list)
    formula: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[BusinessAssumption] = Field(default_factory=list)
    next_best_offers: list[NboRow] = Field(default_factory=list)
    ab_plan: AbPlan | None = None
    # True when every assumption is at its default (the AI explanation still matches).
    defaults_only: bool = True


class ExplanationFigure(BaseModel):
    source_key: str
    value: float
    display: str


class BusinessExplanation(BaseModel):
    sentences: list[str]
    figures: list[ExplanationFigure]
    source: Literal["ai", "template"]
    problems: list[str]
    assumptions_hash: str
    cached: bool


# ---------------------------------------------------------------- telemetry


class ValidatorCounts(BaseModel):
    checked: int
    passed: int
    failed: int
    dropped: int
    figures_caught: int
    pass_rate: float | None = None


class Retries(BaseModel):
    validator: dict[str, int]
    llm_by_node: dict[str, int]


class Correction(BaseModel):
    field: str
    proposed: Any = None
    confirmed: Any = None


class SchemaCorrections(BaseModel):
    count: int
    fields: list[Correction]
    available: bool


class NodeLatency(BaseModel):
    node: str
    latency_ms: float
    runs: int
    status: str


class Latency(BaseModel):
    by_node: list[NodeLatency]
    total_node_time: float
    wall_clock: float


class TokenCount(BaseModel):
    input_tokens: int
    output_tokens: int


class Tokens(BaseModel):
    by_model: dict[str, TokenCount]
    input: int
    output: int


class CostEstimate(BaseModel):
    label: Literal["ESTIMATE"]
    currency: str
    note: str
    total: float
    by_model: dict[str, float]


class RunSummaryOut(BaseModel):
    session_id: str | None = None
    status: str
    validator: ValidatorCounts
    retries: Retries
    schema_corrections: SchemaCorrections
    latency_ms: Latency
    tokens: Tokens
    cost: CostEstimate
    events: int
    created_at: str | None = None
