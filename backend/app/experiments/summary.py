"""Plain-English summary of an experiment analysis (runbook T5c.4).

The LLM (fast tier) sees only computed figures from the analysis, keyed by their
source_key; every figure it writes is checked against the analysis (app/validation.py),
it may not go beyond the decision helper, one retry with feedback, then a template.
"""

import json
import re
from typing import Any

from pydantic import BaseModel, Field

from app import llm
from app.graph.paths import PathNotFound, resolve
from app.prompts.loader import render_prompt
from app.validation import check_figure, check_text, numbers_in

PROMPT = ("experiment_summary", 1)
TIMEOUT_S = 30
SENTENCES = 5
# Figures the summary may use: source_key -> label.
FIGURES = {
    "itt.arms.treatment.rate": "treatment churn rate",
    "itt.arms.control.rate": "control churn rate",
    "itt.arms.treatment.n": "customers in treatment",
    "itt.arms.control.n": "customers in control",
    "itt.difference.value": "difference in churn rate (treatment - control)",
    "itt.difference.ci_low": "95% CI of the difference, lower bound",
    "itt.difference.ci_high": "95% CI of the difference, upper bound",
    "itt.difference.ci_level": "confidence level of the interval (0.95 = 95%)",
    "itt.relative_lift": "relative change in churn",
    "itt.p_value": "p-value (two-proportion z-test)",
    "itt.achieved_power": "power to detect the planned effect",
    "impact.customers_saved": "customers saved",
    "impact.saved_ci_low": "customers saved, lower bound",
    "impact.saved_ci_high": "customers saved, upper bound",
    "impact.acceptance_rate": "offer acceptance rate",
    "impact.customer_value": "value per saved customer (assumption)",
    "impact.offer_cost": "cost per accepted offer (assumption)",
    "impact.net_value": "net value",
    "srm.p_value": "sample ratio mismatch p-value",
    "guardrails.complaints.difference.value": "difference in complaints per customer",
    "guardrails.arpu.difference.value": "difference in revenue per customer",
}
NOT_SHIP = re.compile(r"\b(roll(ing)?[ -]?out|launch|ship(ping)?|go ahead|deploy)\b", re.I)


class Figure(BaseModel):
    source_key: str
    value: float
    display: str


class ExperimentSummary(BaseModel):
    sentences: list[str] = Field(min_length=SENTENCES, max_length=SENTENCES)
    figures: list[Figure] = Field(default_factory=list)


def facts(analysis: dict[str, Any], offer: str) -> dict[str, Any]:
    figures = {}
    for key, label in FIGURES.items():
        try:
            value = resolve(analysis, key)
        except PathNotFound:
            continue
        if isinstance(value, int | float) and not isinstance(value, bool):
            figures[key] = {"label": label, "value": value}
    helper = analysis["decision_helper"]
    return {"offer": offer, "verdict": helper["verdict"], "verdict_reasons": helper["reasons"],
            "figures": figures, "warnings": analysis.get("warnings", []),
            "guardrails_breached": helper["guardrails_breached"]}


def _check(analysis: dict[str, Any], figure: dict[str, Any]) -> list[str]:
    """check_figure, but a drop may be written as its size ("fell by 13.2%" for -0.132):
    the magnitude of a stored number is not a new number."""
    problems = check_figure(analysis, figure)
    if not problems:
        return []
    try:
        actual = resolve(analysis, figure.get("source_key", ""))
    except PathNotFound:
        return problems
    if isinstance(actual, int | float) and not isinstance(actual, bool) and actual < 0:
        claimed = figure.get("value")
        flipped = {**figure, "value": abs(claimed) if isinstance(claimed, int | float) else claimed,
                   "source_key": "magnitude"}
        if not check_figure({"magnitude": abs(actual)}, flipped):
            return []
    return problems


def validate_summary(summary: dict[str, Any], analysis: dict[str, Any], offer: str = ""
                     ) -> list[str]:
    figures = summary.get("figures", [])
    # Numbers written in the offer name ("1 month free") are part of its name.
    allowed = [*figures, *({"value": n, "display": ""} for n, _ in numbers_in(offer))]
    problems = [p for fig in figures for p in _check(analysis, fig)
                if fig.get("source_key") in FIGURES] + [
        f"source_key {fig.get('source_key')!r} is not one of the allowed figures"
        for fig in figures if fig.get("source_key") not in FIGURES]
    sentences = summary.get("sentences", [])
    if len(sentences) != SENTENCES:
        problems.append(f"write exactly {SENTENCES} sentences")
    for i, sentence in enumerate(sentences, 1):
        problems += [f"sentence {i}: {p}" for p in check_text(sentence, allowed)]
        verdict = analysis["decision_helper"]["verdict"]
        if verdict != "ship" and NOT_SHIP.search(sentence):
            problems.append(f"sentence {i} goes beyond the verdict ({verdict}): do not suggest "
                            "rolling out or shipping")
    return problems


def _pct(value: float | None) -> str:
    return "unknown" if value is None else f"{value * 100:.1f}%"


def template_summary(analysis: dict[str, Any], offer: str) -> dict[str, Any]:
    itt, impact, helper = analysis["itt"], analysis["impact"], analysis["decision_helper"]
    t, c, d = itt["arms"]["treatment"], itt["arms"]["control"], itt["difference"]
    net = impact["net_value"]
    breached = helper["guardrails_breached"]
    warnings = analysis.get("warnings", [])
    sentences = [
        f"Churn was {_pct(t['rate'])} with the offer ({offer}) and {_pct(c['rate'])} without "
        f"it.",
        f"The 95% confidence interval of the difference runs from {_pct(d['ci_low'])} to "
        f"{_pct(d['ci_high'])}.",
        f"About {impact['customers_saved']:,.1f} customers were saved; net value is "
        + ("unknown until the offer cost is entered." if net is None else f"{net:,.2f}."),
        ("Guardrails breached: " + ", ".join(breached) + ".") if breached
        else "No guardrail was breached.",
        warnings[0] if warnings else "No warnings.",
    ]
    return {"sentences": sentences, "figures": [], "source": "template",
            "verdict": helper["verdict"], "problems": []}


def generate(analysis: dict[str, Any], offer: str) -> dict[str, Any]:
    facts_json = json.dumps(facts(analysis, offer), ensure_ascii=False)
    feedback = ""
    problems: list[str] = []
    for _ in range(2):  # first try, then one retry with the problems as feedback
        prompt = render_prompt(*PROMPT, facts_json=facts_json, feedback=feedback)
        try:
            result = llm.structured_call("fast", 0.2, prompt, ExperimentSummary,
                                         timeout_s=TIMEOUT_S, max_attempts=2)
        except llm.LLMUnavailable as exc:
            return {**template_summary(analysis, offer), "problems": [f"AI unavailable: {exc}"]}
        summary = result.model_dump()
        problems = validate_summary(summary, analysis, offer)
        if not problems:
            return {**summary, "source": "ai",
                    "verdict": analysis["decision_helper"]["verdict"], "problems": []}
        feedback = "Fix these issues from your last answer:\n- " + "\n- ".join(problems)
    return {**template_summary(analysis, offer), "problems": problems}
