"""Response and SSE event models that form the typed contract with the frontend.

The frontend generates TypeScript from the OpenAPI schema (npm run gen:types),
so every shape the browser reads is declared here or on a router.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agents.llm_agents import Insight, Recommendation
from app.schema_validation import OfferColumns, SemanticType

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
    offer_columns: OfferColumns | None = None


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


class ConfusionMatrix(BaseModel):
    tn: int
    fp: int
    fn: int
    tp: int


class RocCurve(BaseModel):
    fpr: list[float]
    tpr: list[float]


class CvScores(Passthrough):
    name: str
    roc_auc_mean: float | None = None
    roc_auc_std: float | None = None
    pr_auc_mean: float | None = None
    pr_auc_std: float | None = None


class LeakageWarning(BaseModel):
    column: str
    measure: str
    value: float


class HeldOutMetrics(Passthrough):
    # None when undefined (e.g. no positive predictions); NaN becomes null in JSON.
    roc_auc: float | None = None
    pr_auc: float | None = None
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    n_test: int
    threshold: float | None = None
    confusion_matrix: ConfusionMatrix | None = None
    roc_curve: RocCurve | None = None


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
    selection_rule: str | None = None
    cv: dict[str, CvScores] = Field(default_factory=dict)
    leakage_warnings: list[LeakageWarning] = Field(default_factory=list)


class PermutationItem(BaseModel):
    feature: str
    importance_mean: float
    importance_std: float
    rank: int


class DriverImpactRow(BaseModel):
    feature: str
    permutation_rank: int | None = None
    permutation_importance: float | None = None
    mean_abs_shap: float | None = None
    odds_ratio: float | None = None
    or_ci_lower: float | None = None
    or_ci_upper: float | None = None
    or_label: str | None = None
    test_name: str | None = None
    p_adjusted: float | None = None
    significant: bool | None = None


class FeatureImportance(Passthrough):
    method: str | None = None
    features: list[PermutationItem] = Field(default_factory=list)
    driver_impact: list[DriverImpactRow] = Field(default_factory=list)


class ShapGlobal(BaseModel):
    feature: str
    mean_abs_shap: float


class ShapPoint(BaseModel):
    shap: float
    value: float | str | None = None


class ShapFeature(BaseModel):
    feature: str
    kind: str
    points: list[ShapPoint]


class ShapSummary(Passthrough):
    method: str | None = None
    explained_model: str | None = None
    scale: str | None = None
    n_rows: int | None = None
    global_: list[ShapGlobal] = Field(default_factory=list, alias="global")
    beeswarm: list[ShapFeature] = Field(default_factory=list)
    error: str | None = None


class OddsRatioTerm(Passthrough):
    feature: str
    kind: str
    label: str
    term: str
    level: str | None = None
    reference: str | None = None
    odds_ratio: float | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None
    p_value: float | None = None


class DroppedTerm(BaseModel):
    term: str
    reason: str


class OddsRatios(Passthrough):
    method: str | None = None
    n: int | None = None
    converged: bool | None = None
    pseudo_r2: float | None = None
    terms: list[OddsRatioTerm] = Field(default_factory=list)
    dropped: list[DroppedTerm] = Field(default_factory=list)
    error: str | None = None


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


class Assumption(BaseModel):
    name: str
    result: bool
    detail: str


class LabelledTable(BaseModel):
    rows: list[str]
    columns: list[str]
    values: list[list[float]]


class GroupStats(Passthrough):
    n: int
    mean: float | None = None
    median: float | None = None
    sd: float | None = None


class HypothesisInputs(Passthrough):
    observed: LabelledTable | None = None
    expected: LabelledTable | None = None
    cell_contributions: LabelledTable | None = None
    churn_rate_by_level: dict[str, float] | None = None
    groups: dict[str, GroupStats] | None = None
    n: int | None = None


class EffectSize(BaseModel):
    name: str
    value: float | None = None
    band: str


class CalculationStep(BaseModel):
    label: str
    formula: str  # LaTeX
    substituted: str  # LaTeX with the numbers filled in


class HypothesisTest(Passthrough):
    variable: str
    kind: Literal["categorical", "numeric", "offer"]
    offer: str | None = None  # kind "offer": the offer tested (accepted vs declined)
    test_name: str
    why: str
    h0: str
    h1: str
    assumptions: list[Assumption] = Field(default_factory=list)
    inputs: HypothesisInputs
    statistic: float | None = None
    statistic_name: str
    df: float | None = None  # Welch-Satterthwaite df is fractional
    p_value: float | None = None
    p_adjusted: float | None = None
    significant: bool
    effect_size: EffectSize
    steps: list[CalculationStep] = Field(default_factory=list)
    conclusion: str
    merged_levels: list[str] = Field(default_factory=list)


class SkippedTest(BaseModel):
    variable: str
    reason: str


class HypothesisResults(Passthrough):
    alpha: float
    correction: str
    n_tests: int
    n_significant: int
    tests: list[HypothesisTest] = Field(default_factory=list)
    skipped: list[SkippedTest] = Field(default_factory=list)


class GroupSummary(BaseModel):
    n: int
    mean: float | None = None
    median: float | None = None
    std: float | None = None


class Histogram(BaseModel):
    edges: list[float]
    counts: list[int]


class NumericSummary(Passthrough):
    count: int
    missing: int
    churned: GroupSummary
    retained: GroupSummary
    mean: float | None = None
    median: float | None = None
    histogram: Histogram


class LevelRate(BaseModel):
    level: str
    n: int
    churned: int
    churn_rate: float


class CategorySummary(BaseModel):
    levels: list[LevelRate]
    levels_folded_into_other: int = 0


class Correlation(BaseModel):
    columns: list[str] = Field(default_factory=list)
    matrix: list[list[float | None]] = Field(default_factory=list)
    with_target: dict[str, float | None] = Field(default_factory=dict)


class TenureBand(BaseModel):
    band: str
    n: int
    churned: int
    churn_rate: float


class TenureBands(Passthrough):
    bands: list[TenureBand] = Field(default_factory=list)


class EdaResults(Passthrough):
    overview: dict[str, float | int | None]
    numeric: dict[str, NumericSummary] = Field(default_factory=dict)
    categorical: dict[str, CategorySummary] = Field(default_factory=dict)
    correlation: Correlation = Field(default_factory=Correlation)
    tenure_bands: TenureBands | None = None


class Segment(Passthrough):
    segment: int
    label: str
    size: int
    pct_of_base: float
    churn_rate: float
    churn_lift: float | None = None
    feature_means: dict[str, float | None] = Field(default_factory=dict)
    feature_z: dict[str, float | None] = Field(default_factory=dict)


class Segments(Passthrough):
    skipped: bool
    reason: str | None = None
    k: int | None = None
    features: list[str] = Field(default_factory=list)
    overall_churn_rate: float | None = None
    segments: list[Segment] = Field(default_factory=list)


class SurvivalCurve(BaseModel):
    time: list[float]
    survival: list[float | None]
    ci_lower: list[float | None]
    ci_upper: list[float | None]


class KmSummary(Passthrough):
    label: str
    n: int
    events: int
    median_survival: float | None = None
    median_reached: bool
    survival_at: dict[str, float | None] = Field(default_factory=dict)
    curve: SurvivalCurve


class LogRank(BaseModel):
    statistic: float | None = None
    p_value: float | None = None
    df: int | None = None


class SurvivalGroup(Passthrough):
    column: str
    cramers_v: float | None = None
    logrank: LogRank
    curves: list[KmSummary]


class SurvivalResults(Passthrough):
    skipped: bool
    reason: str | None = None
    time_column: str | None = None
    overall: KmSummary | None = None
    by_group: list[SurvivalGroup] = Field(default_factory=list)


class ResultsPayload(BaseModel):
    """Keys the dashboard reads are typed; the rest pass through until their tab is built."""

    model_config = ConfigDict(extra="allow")

    target_column: str | None = None
    positive_label: str | None = None
    cleaning_log: list[CleaningStep] | None = None
    data_health: DataHealth | None = None
    model_metrics: ModelMetrics | None = None
    impact_estimates: ImpactEstimates | None = None
    feature_importance: FeatureImportance | None = None
    shap_summary: ShapSummary | None = None
    odds_ratios: OddsRatios | None = None
    hypothesis_results: HypothesisResults | None = None
    eda_results: EdaResults | None = None
    segments: Segments | None = None
    survival_results: SurvivalResults | None = None
    final_insights: list[Insight] | None = None
    final_recommendations: list[Recommendation] | None = None
    validation_report: ValidationReport | None = None
    final_error: str | None = None
    errors: list[ErrorEvent] = Field(default_factory=list)


class PredictionRow(BaseModel):
    customer_id: str
    churn_probability: float
    risk_band: RiskBand
    actual_churn: int
    reason_1: str | None = None
    reason_2: str | None = None
    reason_3: str | None = None
    # Next best offer (Phase 5b); null for Low-risk customers or without offer data.
    best_offer: str | None = None
    expected_value: float | None = None
    runner_up: str | None = None
    runner_up_value: float | None = None


class PredictionsResponse(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int
    band: RiskBand | None = None
    q: str | None = None
    items: list[PredictionRow]


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
