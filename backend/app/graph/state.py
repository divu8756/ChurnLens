"""Graph state (docs/SPEC.md "State"). One key per producer node.

Large data (dataframes, predictions) lives in files under DATA_DIR; the state
holds paths and small JSON-serialisable results only. Lists written by
parallel nodes use the operator.add reducer.
"""

import operator
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

JsonDict = dict[str, Any]


class ErrorEntry(BaseModel):
    node: str
    message: str
    fatal: bool = False


class ProgressEntry(BaseModel):
    node: str
    status: Literal["started", "done", "skipped", "failed"]
    detail: str | None = None


class ChurnState(BaseModel):
    # ingest_node
    session_id: str
    sheet_name: str | None = None
    raw_path: str | None = None

    # schema_agent (proposal) and human_review (confirmed answer).
    # SPEC calls this "schema"; split in two so each key has one producer and
    # to avoid shadowing BaseModel.schema.
    schema_proposal: JsonDict | None = None
    confirmed_schema: JsonDict | None = None
    target_column: str | None = None
    positive_label: str | None = None
    target_confirmed: bool = False
    id_columns: list[str] = Field(default_factory=list)
    time_column: str | None = None
    offer_columns: JsonDict | None = None  # Phase 5b

    # cleaning_node
    clean_path: str | None = None
    cleaning_log: list[JsonDict] = Field(default_factory=list)
    data_health: JsonDict | None = None

    # parallel analysis nodes
    eda_results: JsonDict | None = None
    segments: JsonDict | None = None
    survival_results: JsonDict | None = None
    hypothesis_results: JsonDict | None = None

    # modelling_node
    model_metrics: JsonDict | None = None
    feature_importance: JsonDict | None = None
    shap_summary: JsonDict | None = None
    odds_ratios: JsonDict | None = None
    predictions_path: str | None = None

    # impact_node / offer_node (5b)
    impact_estimates: JsonDict | None = None
    offer_catalog: JsonDict | None = None
    offer_effectiveness: JsonDict | None = None
    offer_recommendations_path: str | None = None

    # LLM agents, validator, report
    insights: list[JsonDict] = Field(default_factory=list)
    recommendations: list[JsonDict] = Field(default_factory=list)
    validation_report: JsonDict | None = None
    validator_feedback: JsonDict = Field(default_factory=dict)
    retry_counts: dict[str, int] = Field(default_factory=dict)
    # validator output: the agents' items that passed (failing items dropped)
    final_insights: list[JsonDict] = Field(default_factory=list)
    final_recommendations: list[JsonDict] = Field(default_factory=list)
    report_paths: JsonDict | None = None

    # error_node
    final_error: str | None = None

    # shared, appended to by any node (parallel-safe reducers)
    errors: Annotated[list[ErrorEntry], operator.add] = Field(default_factory=list)
    progress: Annotated[list[ProgressEntry], operator.add] = Field(default_factory=list)
    telemetry_events: Annotated[list[JsonDict], operator.add] = Field(default_factory=list)

    def has_fatal_error(self) -> bool:
        return any(e.fatal for e in self.errors)
