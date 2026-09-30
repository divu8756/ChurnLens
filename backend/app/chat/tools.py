"""The chat agent's five tools (runbook T7.1). Every argument is validated with Pydantic;
data access is plain pandas indexing and comparisons, never exec / eval / df.query or
string-built code. Tools return small JSON-safe results; row-level data never leaves
this module except one customer's own score and reasons (get_customer_risk)."""

import json
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, ValidationError, model_validator

from app.graph.paths import PathNotFound, resolve
from app.stats.common import jsonable

ToolName = Literal["get_stat", "get_segment", "get_test_result", "get_customer_risk",
                   "filter_and_aggregate"]
Op = Literal["==", "!=", ">", ">=", "<", "<=", "in"]
Metric = Literal["count", "mean", "median", "sum", "churn_rate"]
MAX_FILTERS = 3
MAX_ROWS = 50
MAX_RESULT_CHARS = 3000
STAT_ROOTS = ("eda_results", "impact_estimates", "model_metrics", "model_metrics_v2",
              "segments", "survival_results", "hypothesis_results", "data_health",
              "offer_effectiveness", "feature_importance", "odds_ratios")
NOT_COMPUTED = "not computed"


class ToolError(ValueError):
    """The arguments are invalid; the message tells the agent what to fix."""


class Filter(BaseModel):
    column: str = Field(min_length=1, max_length=200)
    op: Op
    value: str | float | None = None
    values: list[str | float] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _shape(self) -> Filter:
        if self.op == "in" and not self.values:
            raise ValueError("op 'in' needs a non-empty values list")
        if self.op != "in" and self.value is None:
            raise ValueError(f"op '{self.op}' needs a value")
        return self


class AggregateArgs(BaseModel):
    filters: list[Filter] = Field(default_factory=list, max_length=MAX_FILTERS)
    group_by: str | None = Field(default=None, max_length=200)
    metric: Metric
    column: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _column_needed(self) -> AggregateArgs:
        if self.metric in ("mean", "median", "sum") and not self.column:
            raise ValueError(f"metric '{self.metric}' needs a numeric column")
        return self


def _cap(value: Any) -> Any:
    """Keep results small: large dicts/lists are summarised so the agent asks narrower."""
    value = jsonable(value)
    text = json.dumps(value, default=str)
    if len(text) <= MAX_RESULT_CHARS:
        return value
    if isinstance(value, dict):
        return {"too_large": True, "keys": list(value)[:40],
                "hint": "Ask for one of these keys, e.g. key + '.' + name."}
    if isinstance(value, list):
        return {"too_large": True, "length": len(value),
                "hint": "Ask for one item, e.g. key + '.0'."}
    return text[:MAX_RESULT_CHARS]


class ChatData:
    """Read-only access to one analysed session's results and files."""

    def __init__(self, values: dict[str, Any]) -> None:
        self.values = values
        self.schema = values.get("confirmed_schema") or {}
        self._frame: pd.DataFrame | None = None
        self._preds: pd.DataFrame | None = None

    # ------------------------------------------------------------ data
    def predictions(self) -> pd.DataFrame | None:
        path = self.values.get("predictions_path")
        if self._preds is None and path and Path(path).exists():
            self._preds = pd.read_parquet(path)
        return self._preds

    def frame(self) -> pd.DataFrame:
        """Cleaned data with the target as 0/1 and, when scored, risk_band and
        churn_probability joined on the customer ID."""
        if self._frame is None:
            path = self.values.get("clean_path")
            if not path or not Path(path).exists():
                raise ToolError("The cleaned data is not available for this session.")
            frame = pd.read_parquet(path)
            preds = self.predictions()
            ids = [c for c in self.schema.get("id_columns", []) if c in frame.columns]
            if preds is not None and ids:
                extra = preds[["customer_id", "churn_probability", "risk_band"]]
                extra = extra.drop_duplicates("customer_id").set_index("customer_id")
                key = frame[ids[0]].astype(str)
                frame["churn_probability"] = key.map(extra["churn_probability"]).to_numpy()
                frame["risk_band"] = key.map(extra["risk_band"]).to_numpy()
            self._frame = frame
        return self._frame

    def columns(self) -> list[str]:
        """Column names the agent may use (IDs excluded)."""
        ids = set(self.schema.get("id_columns", []))
        try:
            return [str(c) for c in self.frame().columns if c not in ids]
        except ToolError:
            return []

    # ------------------------------------------------------------ tools
    def get_stat(self, key: str) -> dict[str, Any]:
        root = key.split(".", 1)[0]
        if root not in STAT_ROOTS:
            raise ToolError(f"Unknown stat root '{root}'. Use one of: {', '.join(STAT_ROOTS)}.")
        if "path" in key.rsplit(".", 1)[-1]:
            raise ToolError("File paths are not available.")
        try:
            value = resolve(self.values, key)
        except PathNotFound:
            return {"key": key, "status": NOT_COMPUTED}
        if value is None:
            return {"key": key, "status": NOT_COMPUTED}
        return {"key": key, "value": _cap(value)}

    def get_segment(self, segment_id: int) -> dict[str, Any]:
        segs = (self.values.get("segments") or {}).get("segments") or []
        for seg in segs:
            if seg.get("segment") == segment_id:
                return {"segment": _cap(seg)}
        if not segs:
            return {"segment_id": segment_id, "status": NOT_COMPUTED}
        return {"segment_id": segment_id, "status": "no such segment",
                "available": [s.get("segment") for s in segs]}

    def get_test_result(self, variable: str) -> dict[str, Any]:
        tests = (self.values.get("hypothesis_results") or {}).get("tests") or []
        for test in tests:
            if str(test.get("variable", "")).casefold() == variable.casefold():
                keep = ("variable", "test_name", "statistic_name", "statistic", "p_value",
                        "p_adjusted", "significant", "effect_size", "df", "h0", "h1")
                return {"test": _cap({k: test.get(k) for k in keep if k in test})}
        return {"variable": variable, "status": NOT_COMPUTED,
                "tested": [t.get("variable") for t in tests][:40]}

    def get_customer_risk(self, customer_id: str) -> dict[str, Any]:
        preds = self.predictions()
        if preds is None:
            return {"customer_id": customer_id, "status": NOT_COMPUTED}
        row = preds[preds["customer_id"].astype(str) == str(customer_id)]
        if row.empty:
            return {"customer_id": customer_id, "status": "unknown customer"}
        r = row.iloc[0]
        keep = ("customer_id", "churn_probability", "risk_band", "reason_1", "reason_2",
                "reason_3")
        return {"customer": jsonable({k: r[k] for k in keep if k in r.index})}

    def filter_and_aggregate(self, args: AggregateArgs) -> dict[str, Any]:
        frame = self.frame()
        allowed = set(self.columns())
        named = [f.column for f in args.filters] + [c for c in (args.group_by, args.column) if c]
        missing = [c for c in named if c not in allowed]
        if missing:
            raise ToolError(f"Unknown column(s): {', '.join(sorted(set(missing)))}. "
                            f"Columns: {', '.join(sorted(allowed))[:1500]}.")
        mask = pd.Series(True, index=frame.index)
        for f in args.filters:
            mask &= _compare(frame[f.column], f)
        data = frame[mask]
        target = self.schema.get("target_column")
        if args.metric in ("mean", "median", "sum"):
            values = pd.to_numeric(data[args.column], errors="coerce")
            if values.notna().sum() == 0 and len(data):
                raise ToolError(f"Column '{args.column}' is not numeric.")
            data = data.assign(_value=values)
        if args.metric == "churn_rate":
            if not target or target not in data.columns:
                raise ToolError("The churn column is not available.")
            data = data.assign(_value=pd.to_numeric(data[target], errors="coerce"))

        def compute(part: pd.DataFrame) -> float | None:
            if args.metric == "count":
                return float(len(part))
            series = part["_value"].dropna()
            if series.empty:
                return None
            return float({"mean": series.mean, "median": series.median, "sum": series.sum,
                          "churn_rate": series.mean}[args.metric]())

        result: dict[str, Any] = {"metric": args.metric, "column": args.column,
                                  "filters": [f.model_dump(exclude_none=True)
                                              for f in args.filters],
                                  "rows_matched": int(len(data))}
        if args.group_by:
            groups = data.groupby(data[args.group_by].astype(str), sort=True, dropna=False)
            rows = [{"group": str(name), "n": int(len(part)), "value": compute(part)}
                    for name, part in groups]
            result["groups_total"] = len(rows)
            result["rows"] = rows[:MAX_ROWS]
            result["truncated"] = len(rows) > MAX_ROWS
        else:
            result["value"] = compute(data)
        return jsonable(result)


def _compare(series: pd.Series, f: Filter) -> pd.Series:
    if f.op == "in":
        return series.astype(str).isin([_text(v) for v in f.values])
    numeric = pd.to_numeric(series, errors="coerce")
    number = _number(f.value)
    if f.op in ("==", "!="):
        if number is not None and numeric.notna().any():
            hit = numeric == number
        else:
            hit = series.astype(str) == _text(f.value)
        return hit if f.op == "==" else ~hit & series.notna()
    if number is None:
        raise ToolError(f"Filter '{f.column} {f.op}' needs a number.")
    if numeric.notna().sum() == 0:
        raise ToolError(f"Column '{f.column}' is not numeric, so '{f.op}' cannot be used.")
    return {">": numeric.gt, ">=": numeric.ge, "<": numeric.lt, "<=": numeric.le}[f.op](
        number).fillna(False)


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def _text(value: Any) -> str:
    """1.0 from JSON still matches the text '1'."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def run_tool(data: ChatData, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    """Validate and run one tool call. Invalid arguments come back as an error result the
    agent can read and correct, never as an exception."""
    try:
        if tool == "get_stat":
            return data.get_stat(str(args.get("key") or ""))
        if tool == "get_segment":
            return data.get_segment(int(args.get("segment_id")))
        if tool == "get_test_result":
            return data.get_test_result(str(args.get("variable") or ""))
        if tool == "get_customer_risk":
            return data.get_customer_risk(str(args.get("customer_id") or ""))
        if tool == "filter_and_aggregate":
            return data.filter_and_aggregate(AggregateArgs.model_validate(args))
        return {"error": f"Unknown tool '{tool}'."}
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                             for e in exc.errors())
        return {"error": f"Invalid arguments: {problems}"}
    except (ToolError, TypeError, ValueError) as exc:
        return {"error": str(exc)}
