"""Validate the schema the user confirms before the graph resumes."""

from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field

from app.stats import profiling

SemanticType = Literal["id", "numeric", "categorical", "binary", "datetime", "text"]


class ConfirmedColumn(BaseModel):
    name: str
    semantic_type: SemanticType


class ConfirmedSchema(BaseModel):
    columns: list[ConfirmedColumn] = Field(default_factory=list)
    target_column: str
    positive_label: str
    id_columns: list[str] = Field(default_factory=list)
    time_column: str | None = None
    revenue_column: str | None = None  # monthly revenue per customer (ARPU)


def validate_schema(schema: ConfirmedSchema, frame: pd.DataFrame) -> list[str]:
    """Return plain-English problems; an empty list means the schema is usable."""
    names = {str(c) for c in frame.columns}
    problems: list[str] = []

    target = schema.target_column
    if target not in names:
        problems.append(f"Target column '{target}' does not exist.")
    else:
        values = profiling.binary_values(frame[target])
        if values is None:
            count = frame[target].nunique(dropna=True)
            problems.append(
                f"Target column '{target}' must have exactly two values (it has {count})."
            )
        elif schema.positive_label not in values:
            problems.append(
                f"Positive label '{schema.positive_label}' is not a value of '{target}' "
                f"(values: {', '.join(values)})."
            )

    missing_ids = [c for c in schema.id_columns if c not in names]
    if missing_ids:
        problems.append(f"ID columns not found: {', '.join(missing_ids)}.")
    if target in schema.id_columns:
        problems.append("The target column cannot also be an ID column.")

    if schema.time_column is not None:
        if schema.time_column not in names:
            problems.append(f"Time column '{schema.time_column}' does not exist.")
        elif profiling.heuristic_type(frame[schema.time_column], False) != "numeric":
            problems.append(f"Time column '{schema.time_column}' must be numeric.")
        if schema.time_column == target:
            problems.append("The time column cannot be the target column.")

    if schema.revenue_column is not None:
        if schema.revenue_column not in names:
            problems.append(f"Revenue column '{schema.revenue_column}' does not exist.")
        elif profiling.heuristic_type(frame[schema.revenue_column], False) != "numeric":
            problems.append(f"Revenue column '{schema.revenue_column}' must be numeric.")
        if schema.revenue_column == target:
            problems.append("The revenue column cannot be the target column.")

    unknown = [c.name for c in schema.columns if c.name not in names]
    if unknown:
        problems.append(f"Unknown columns in the type list: {', '.join(unknown)}.")
    return problems
