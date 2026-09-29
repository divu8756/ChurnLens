"""validator_node (docs/SPEC.md node 13).

Checks every insight and recommendation against state (app/validation.py).
Failing agents are sent back with feedback, at most MAX_RETRIES times each;
after that the failing items are dropped and the run continues. The
validator writes only its own keys: validation_report, validator_feedback,
retry_counts, final_insights and final_recommendations.
"""

import logging
from typing import Any

from app.graph.state import ChurnState, ProgressEntry
from app.validation import validate_insight, validate_recommendation

logger = logging.getLogger("churnlens.validator")

MAX_RETRIES = 2
AGENTS = {
    "insight_agent": ("insights", validate_insight),
    "recommendation_agent": ("recommendations", validate_recommendation),
}


def validator_node(state: ChurnState) -> dict[str, Any]:
    data = state.model_dump(mode="json")
    retry_counts = dict(state.retry_counts)
    feedback: dict[str, list[str]] = {}
    retry_agents: list[str] = []
    finals: dict[str, list[dict[str, Any]]] = {}
    details: list[dict[str, Any]] = []
    checked = passed = dropped = 0

    for agent, (key, check) in AGENTS.items():
        items = data.get(key) or []
        good, issues = [], []
        for item in items:
            problems = check(data, item)
            checked += 1
            details.append({"agent": agent, "id": item.get("id"), "ok": not problems,
                            "problems": problems})
            if problems:
                issues.extend(f"{item.get('id')}: {p}" for p in problems)
            else:
                passed += 1
                good.append(item)
        finals[key] = good
        if not issues:
            continue
        if retry_counts.get(agent, 0) < MAX_RETRIES:
            retry_counts[agent] = retry_counts.get(agent, 0) + 1
            retry_agents.append(agent)
            feedback[agent] = issues
        else:
            dropped += len(items) - len(good)
            logger.warning("%s: dropped %d items after %d retries", agent,
                           len(items) - len(good), MAX_RETRIES)

    failed = checked - passed
    report = {
        "checked": checked, "passed": passed, "failed": failed, "dropped": dropped,
        "retry_agents": retry_agents, "retry_counts": retry_counts,
        "final": not retry_agents,
        "details": details,
    }
    detail = (f"{passed}/{checked} items verified" +
              (f", retrying {', '.join(retry_agents)}" if retry_agents else ""))
    return {
        "validation_report": report,
        "validator_feedback": feedback,
        "retry_counts": retry_counts,
        "final_insights": finals["insights"],
        "final_recommendations": finals["recommendations"],
        "progress": [ProgressEntry(node="validator", status="done", detail=detail)],
    }
