"""Plain-English explanation of the business metrics (SPEC v1.3 "Regenerate explanation").

The LLM (fast tier) sees only computed figures keyed by source_key; every figure it writes
is checked against the same computed metrics (app/validation.py). One retry with
feedback, then a template. Cached per session and assumptions (hash), so the same
numbers never cost a second call.
"""

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app import llm
from app.graph.paths import PathNotFound, resolve
from app.prompts.loader import render_prompt
from app.validation import check_figure, check_text, numbers_in

PROMPT = ("business_explanation", 1)
TIMEOUT_S = 30
SENTENCES = 3
CACHE_FILE = "business_explanations.json"
_lock = threading.Lock()
FIGURES = {
    "kpis.revenue_at_risk": "revenue at risk",
    "revenue_at_risk.months_remaining": "months of revenue counted (assumption)",
    "kpis.expected_saving": "expected saving from the recommended offers",
    "kpis.customers_with_offer": "customers with a recommended offer",
    "kpis.customers_scored": "customers scored",
    "kpis.overall_roi": "net saving per unit of offer cost",
    "ab_plan.n_per_arm": "customers needed per test group",
    "ab_plan.total_n": "customers needed in total for the test",
    "ab_plan.relative_lift": "relative drop in churn the test detects (assumption)",
    "ab_plan.p1": "churn rate of the targeted customers",
}


class Figure(BaseModel):
    source_key: str
    value: float
    display: str


class Explanation(BaseModel):
    sentences: list[str] = Field(min_length=SENTENCES, max_length=SENTENCES)
    figures: list[Figure] = Field(default_factory=list)


def assumptions_hash(assumptions: dict[str, Any]) -> str:
    canonical = json.dumps(assumptions, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def facts(metrics: dict[str, Any]) -> dict[str, Any]:
    figures = {}
    for key, label in FIGURES.items():
        try:
            value = resolve(metrics, key)
        except PathNotFound:
            continue
        if isinstance(value, int | float) and not isinstance(value, bool):
            figures[key] = {"label": label, "value": value}
    for i, row in enumerate(metrics.get("by_offer") or []):
        figures[f"by_offer.{i}.expected_saving"] = {
            "label": f"expected saving from '{row['offer']}'", "value": row["expected_saving"]}
        figures[f"by_offer.{i}.customers"] = {
            "label": f"customers offered '{row['offer']}'", "value": row["customers"]}
    return {"figures": figures, "offers": [o["name"] for o in metrics.get("offers") or []],
            "warnings": metrics.get("warnings") or [],
            "assumptions": [{k: a[k] for k in ("name", "value", "source")}
                            for a in metrics.get("assumptions") or []]}


def validate(explanation: dict[str, Any], metrics: dict[str, Any]) -> list[str]:
    allowed_keys = set(facts(metrics)["figures"])
    figures = explanation.get("figures", [])
    problems = [p for fig in figures for p in check_figure(metrics, fig)
                if fig.get("source_key") in allowed_keys]
    problems += [f"source_key {fig.get('source_key')!r} is not one of the allowed figures"
                 for fig in figures if fig.get("source_key") not in allowed_keys]
    names = " ".join(o["name"] for o in metrics.get("offers") or [])
    allowed = [*figures, *({"value": n, "display": ""} for n, _ in numbers_in(names))]
    sentences = explanation.get("sentences", [])
    if len(sentences) != SENTENCES:
        problems.append(f"write exactly {SENTENCES} sentences")
    for i, sentence in enumerate(sentences, 1):
        problems += [f"sentence {i}: {p}" for p in check_text(sentence, allowed)]
    return problems


def template(metrics: dict[str, Any]) -> dict[str, Any]:
    k = metrics["kpis"]
    months = metrics["revenue_at_risk"]["months_remaining"]
    roi = k.get("overall_roi")
    plan = metrics.get("ab_plan") or {}
    third = (f"An A/B test would need about {plan['n_per_arm']:,} customers per group to "
             "confirm the effect." if plan.get("available") else
             (metrics.get("warnings") or ["No A/B plan is available for these customers."])[0])
    return {"sentences": [
        f"About {k['revenue_at_risk']:,.0f} of revenue is at risk over the next "
        f"{months:g} months.",
        f"The recommended offers for {k['customers_with_offer']:,} customers are estimated "
        f"to save {k['expected_saving']:,.0f}"
        + (f", about {roi:,.2f} per unit of offer cost." if roi is not None else "."),
        third], "figures": [], "source": "template"}


def generate(metrics: dict[str, Any]) -> dict[str, Any]:
    facts_json = json.dumps(facts(metrics), ensure_ascii=False)
    feedback = ""
    problems: list[str] = []
    for _ in range(2):
        prompt = render_prompt(*PROMPT, facts_json=facts_json, feedback=feedback)
        try:
            result = llm.structured_call("fast", 0.2, prompt, Explanation,
                                         timeout_s=TIMEOUT_S, max_attempts=2)
        except llm.LLMUnavailable as exc:
            return {**template(metrics), "problems": [f"AI unavailable: {exc}"]}
        answer = result.model_dump()
        problems = validate(answer, metrics)
        if not problems:
            return {**answer, "source": "ai", "problems": []}
        feedback = "Fix these issues from your last answer:\n- " + "\n- ".join(problems)
    return {**template(metrics), "problems": problems}


def cached_explanation(session_dir: Path, key: str, metrics: dict[str, Any]
                       ) -> tuple[dict[str, Any], bool]:
    path = session_dir / CACHE_FILE
    with _lock:
        cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if key in cache:
            return cache[key], True
    result = generate(metrics)
    with _lock:
        cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        cache.setdefault(key, result)
        path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        return cache[key], False
