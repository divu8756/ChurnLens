"""Run telemetry (SPEC v1.3, runbook T5d.4).

- traced(name, fn): wraps a node so every run appends one event to state.telemetry_events
  (an operator.add list, so parallel branches never clash): node, started_at, latency_ms,
  status, retries, input_tokens, output_tokens, model.
- Tokens come from the Gemini wrapper's usage records (app/llm.py listeners). A context
  variable ties each LLM call to the node run that made it, also under the parallel
  fan-out. Prompt text is never recorded.
- summarise_run(values, pricing): validator results, retries, schema corrections, latency,
  tokens and an ESTIMATED cost from app/config/pricing.yaml.
"""

import time
from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from langgraph.errors import GraphBubbleUp

from app import llm
from app.catalog import Pricing

NodeFn = Any  # Callable[[ChurnState], dict[str, Any]]; kept loose to avoid an import cycle


@dataclass
class _Usage:
    calls: int = 0
    retries: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    models: list[str] = field(default_factory=list)


_current: ContextVar[_Usage | None] = ContextVar("churnlens_node_usage", default=None)


def _record(call: llm.CallRecord) -> None:
    usage = _current.get()
    if usage is None:
        return
    usage.calls += 1
    usage.retries += max(0, call.attempts - 1)
    usage.input_tokens += call.input_tokens
    usage.output_tokens += call.output_tokens
    if call.model not in usage.models:
        usage.models.append(call.model)


llm.add_usage_listener(_record)


def _status(name: str, update: dict[str, Any]) -> str:
    progress = [p for p in update.get("progress", [])
                if getattr(p, "node", None) == name or (isinstance(p, dict)
                                                        and p.get("node") == name)]
    statuses = [p.status if hasattr(p, "status") else p.get("status") for p in progress]
    for status in ("failed", "skipped"):
        if status in statuses:
            return status
    return "done"


def traced(name: str, fn: NodeFn) -> NodeFn:
    """Outermost node wrapper: time the run, collect LLM usage, append one event."""

    def wrapped(state: Any) -> dict[str, Any]:
        usage = _Usage()
        token = _current.set(usage)
        started = datetime.now(UTC)
        clock = time.perf_counter()
        try:
            update = fn(state)
        except GraphBubbleUp:
            raise  # an interrupt pauses the node; it is timed when it runs again
        finally:
            _current.reset(token)
        event = {
            "node": name,
            "started_at": started.isoformat(),
            "latency_ms": round((time.perf_counter() - clock) * 1000, 1),
            "status": _status(name, update),
            "retries": usage.retries,
            "llm_calls": usage.calls,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "model": ", ".join(usage.models) or None,
        }
        return {**update, "telemetry_events": [event]}

    wrapped.__name__ = getattr(fn, "__name__", f"{name}_node")
    return wrapped


# ---------------------------------------------------------------- run summary

SCHEMA_FIELDS = ("target_column", "positive_label", "time_column", "revenue_column")


def schema_corrections(proposal: dict[str, Any] | None, confirmed: dict[str, Any] | None
                       ) -> dict[str, Any]:
    """Fields where the human's confirmed schema differs from the AI's proposal."""
    if not proposal or not confirmed:
        return {"count": 0, "fields": [], "available": False}
    fields: list[dict[str, Any]] = []
    for key in SCHEMA_FIELDS:
        if proposal.get(key) != confirmed.get(key):
            fields.append({"field": key, "proposed": proposal.get(key),
                           "confirmed": confirmed.get(key)})
    if sorted(proposal.get("id_columns") or []) != sorted(confirmed.get("id_columns") or []):
        fields.append({"field": "id_columns", "proposed": proposal.get("id_columns") or [],
                       "confirmed": confirmed.get("id_columns") or []})
    if (proposal.get("offer_columns") or None) != (confirmed.get("offer_columns") or None):
        fields.append({"field": "offer_columns", "proposed": proposal.get("offer_columns"),
                       "confirmed": confirmed.get("offer_columns")})
    proposed_types = {c["name"]: c.get("semantic_type") for c in proposal.get("columns", [])}
    for col in confirmed.get("columns", []):
        before = proposed_types.get(col["name"])
        if before is not None and before != col.get("semantic_type"):
            fields.append({"field": f"columns.{col['name']}", "proposed": before,
                           "confirmed": col.get("semantic_type")})
    return {"count": len(fields), "fields": fields, "available": True}


def estimate_cost(tokens: dict[str, dict[str, int]], pricing: Pricing) -> dict[str, Any]:
    by_model = {}
    for model, t in tokens.items():
        price = pricing.price(model)
        by_model[model] = (t["input_tokens"] * price.input_per_1m
                           + t["output_tokens"] * price.output_per_1m) / 1_000_000
    return {"label": "ESTIMATE", "currency": pricing.currency, "note": pricing.note,
            "total": sum(by_model.values()), "by_model": by_model}


def summarise_run(values: dict[str, Any], pricing: Pricing) -> dict[str, Any]:
    events = values.get("telemetry_events") or []
    latency: dict[str, float] = defaultdict(float)
    runs: dict[str, int] = defaultdict(int)
    statuses: dict[str, str] = {}
    tokens: dict[str, dict[str, int]] = {}
    llm_retries: dict[str, int] = defaultdict(int)
    for e in events:
        latency[e["node"]] += e["latency_ms"]
        runs[e["node"]] += 1
        statuses[e["node"]] = e["status"]
        llm_retries[e["node"]] += e.get("retries", 0)
        for model in (e.get("model") or "").split(", "):
            if not model:
                continue
            t = tokens.setdefault(model, {"input_tokens": 0, "output_tokens": 0})
            # A node that used several models (fallback) reports combined tokens; they are
            # attributed to its first model.
            if model == e["model"].split(", ")[0]:
                t["input_tokens"] += e.get("input_tokens", 0)
                t["output_tokens"] += e.get("output_tokens", 0)
    starts = [datetime.fromisoformat(e["started_at"]) for e in events]
    ends = [datetime.fromisoformat(e["started_at"]).timestamp() + e["latency_ms"] / 1000
            for e in events]
    report = values.get("validation_report") or {}
    details = report.get("details") or []
    return {
        "session_id": values.get("session_id"),
        "status": "failed" if values.get("final_error") else "done",
        "validator": {"checked": report.get("checked", 0), "passed": report.get("passed", 0),
                      "failed": report.get("failed", 0), "dropped": report.get("dropped", 0),
                      "figures_caught": sum(len(d.get("problems") or []) for d in details)},
        "retries": {"validator": dict(values.get("retry_counts") or {}),
                    "llm_by_node": {k: v for k, v in llm_retries.items() if v}},
        "schema_corrections": schema_corrections(values.get("schema_proposal"),
                                                 values.get("confirmed_schema")),
        "latency_ms": {
            "by_node": [{"node": n, "latency_ms": latency[n], "runs": runs[n],
                         "status": statuses[n]} for n in latency],
            "total_node_time": sum(latency.values()),
            "wall_clock": (max(ends) - min(starts).timestamp()) * 1000 if events else 0.0,
        },
        "tokens": {"by_model": tokens,
                   "input": sum(t["input_tokens"] for t in tokens.values()),
                   "output": sum(t["output_tokens"] for t in tokens.values())},
        "cost": estimate_cost(tokens, pricing),
        "events": len(events),
    }
