"""Checks that every number the LLM writes comes from computed state (runbook T5.4).

1. Every figure's source_key must resolve in state.
2. The figure's value (and its display text) must match the state value:
   relative 1% or absolute 0.005, accepting fraction vs percent
   (0.265 == 26.5%) and rounding.
3. Every number in the text fields must match a declared figure. Numbers
   glued to letters ("5G", "Q1", "90d") are part of names and ignored.
   "< 0.001" is accepted when a declared figure is below 0.001.
4. Recommendation impact must come from impact_estimates keys.
"""

import math
import re
from typing import Any

from app.graph.paths import PathNotFound, resolve

REL_TOL = 0.01
ABS_TOL = 0.005
IMPACT_PREFIX = "impact_estimates."
NUMBER = re.compile(
    r"(?P<lt><\s*|less than\s+)?"
    r"(?<![A-Za-z0-9_.])[$₹£€]?"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"\s*(?P<unit>%|×|x\b)?"
    r"(?![A-Za-z0-9])",
    re.IGNORECASE,
)
INSIGHT_TEXT_FIELDS = ("title", "text")
RECOMMENDATION_TEXT_FIELDS = ("problem", "action", "target_segment")


def close(a: float, b: float) -> bool:
    return abs(a - b) <= max(ABS_TOL, REL_TOL * abs(b))


def matches(claimed: float, actual: float) -> bool:
    """True if claimed equals actual, also across fraction/percent scales."""
    return close(claimed, actual) or close(claimed, actual * 100) or close(claimed / 100, actual)


def numbers_in(text: str) -> list[tuple[float, bool]]:
    """(number, preceded by '<') for every standalone number in the text."""
    found = []
    for m in NUMBER.finditer(text or ""):
        found.append((float(m.group("num").replace(",", "")), bool(m.group("lt"))))
    return found


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float) and math.isfinite(float(value)):
        return float(value)
    return None


def check_figure(state: dict[str, Any], figure: dict[str, Any],
                 required_prefix: str | None = None) -> list[str]:
    key = figure.get("source_key", "")
    if required_prefix and not key.startswith(required_prefix):
        return [f"{key!r} must come from {required_prefix.rstrip('.')}"]
    try:
        actual = _as_number(resolve(state, key))
    except PathNotFound:
        return [f"source_key {key!r} does not exist"]
    if actual is None:
        return [f"source_key {key!r} is not a number"]
    problems = []
    claimed = _as_number(figure.get("value"))
    if claimed is None or not matches(claimed, actual):
        problems.append(f"{key!r}: value {figure.get('value')} does not match {actual:.6g}")
    display = figure.get("display")
    if display:
        shown = numbers_in(str(display))
        if shown and not any(matches(n, actual) or (lt and actual < n) for n, lt in shown):
            problems.append(f"{key!r}: display {display!r} does not match {actual:.6g}")
    return problems


def check_text(text: str, figures: list[dict[str, Any]]) -> list[str]:
    declared: list[float] = []
    for fig in figures:
        n = _as_number(fig.get("value"))
        if n is not None:
            declared.append(n)
        declared.extend(n for n, _ in numbers_in(str(fig.get("display") or "")))
    problems = []
    for number, less_than in numbers_in(text):
        if any(matches(number, d) for d in declared):
            continue
        if less_than and any(d < number for d in declared):
            continue
        problems.append(f"number {number:g} in the text is not a declared figure")
    return problems


def validate_insight(state: dict[str, Any], insight: dict[str, Any]) -> list[str]:
    figures = insight.get("figures", [])
    problems = [p for fig in figures for p in check_figure(state, fig)]
    for field in INSIGHT_TEXT_FIELDS:
        problems += check_text(str(insight.get(field, "")), figures)
    return problems


def validate_recommendation(state: dict[str, Any], rec: dict[str, Any]) -> list[str]:
    figures = list(rec.get("figures", []))
    problems = [p for fig in figures for p in check_figure(state, fig)]
    customers = rec.get("customers_affected") or {}
    problems += check_figure(state, customers)
    impact = rec.get("impact") or {}
    problems += check_figure(state, {**impact, "display": None}, required_prefix=IMPACT_PREFIX)
    allowed = [*figures, customers, {"value": impact.get("value")}]
    for field in RECOMMENDATION_TEXT_FIELDS:
        problems += check_text(str(rec.get(field, "")), allowed)
    return problems
