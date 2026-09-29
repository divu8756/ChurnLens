"""Validate the schema the user confirms before the graph resumes."""

from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field

from app.stats import profiling

SemanticType = Literal["id", "numeric", "categorical", "binary", "datetime", "text"]


class ConfirmedColumn(BaseModel):
    name: str
    semantic_type: SemanticType


class OfferColumns(BaseModel):
    """Which columns describe a retention offer/campaign (Phase 5b). They are treatments:
    analysed separately and kept out of the churn model, segments and trait tests."""

    # One column (an offer name, or a delimited list of names per row), or one 0/1
    # column per offer (the column name is the offer).
    shown: str | list[str]
    # Yes/No per row, a delimited list of accepted offer names, or 0/1 columns paired
    # by position with `shown` when that is a list.
    accepted: str | list[str] | None = None
    date: str | None = None
    cost: str | None = None
    group: str | None = None  # campaign arm, e.g. targeted / holdout (Phase 5c)
    other: list[str] = Field(default_factory=list)  # channel, clicked, ...

    def all_columns(self) -> list[str]:
        cols: list[str] = []
        for value in (self.shown, self.accepted, self.date, self.cost, self.group, self.other):
            if isinstance(value, str):
                cols.append(value)
            elif isinstance(value, list):
                cols.extend(value)
        return list(dict.fromkeys(cols))


def offer_column_names(offer_columns: dict | None) -> list[str]:
    """All offer/campaign column names in a confirmed schema's offer_columns (or [])."""
    if not offer_columns:
        return []
    return OfferColumns.model_validate(offer_columns).all_columns()


class ConfirmedSchema(BaseModel):
    columns: list[ConfirmedColumn] = Field(default_factory=list)
    target_column: str
    positive_label: str
    id_columns: list[str] = Field(default_factory=list)
    time_column: str | None = None
    revenue_column: str | None = None  # monthly revenue per customer (ARPU)
    offer_columns: OfferColumns | None = None  # Phase 5b; None = no offer analysis


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

    problems.extend(_offer_problems(schema, names))

    unknown = [c.name for c in schema.columns if c.name not in names]
    if unknown:
        problems.append(f"Unknown columns in the type list: {', '.join(unknown)}.")
    return problems


def _offer_problems(schema: ConfirmedSchema, names: set[str]) -> list[str]:
    offers = schema.offer_columns
    if offers is None:
        return []
    problems = []
    cols = offers.all_columns()
    missing = [c for c in cols if c not in names]
    if missing:
        problems.append(f"Offer columns not found: {', '.join(missing)}.")
    reserved = {schema.target_column, schema.time_column, schema.revenue_column,
                *schema.id_columns} - {None}
    clash = [c for c in cols if c in reserved]
    if clash:
        problems.append("Offer columns cannot also be the target, ID, time or revenue "
                        f"column: {', '.join(clash)}.")
    if (isinstance(offers.shown, list) and isinstance(offers.accepted, list)
            and len(offers.shown) != len(offers.accepted)):
        problems.append("With one column per offer, give one accepted column per offer "
                        "(same order).")
    return problems
