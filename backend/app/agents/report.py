"""report_node: marks the run's exports as available. The files themselves are built on
demand by GET /export/{id}/excel and /pdf (runbook T7.2), so the analysis stays fast."""

from typing import Any

from app.graph.state import ChurnState, ProgressEntry

FORMATS = ("excel", "pdf")


def report_node(state: ChurnState) -> dict[str, Any]:
    ready = bool(state.clean_path and state.predictions_path)
    return {
        "report_paths": {"formats": list(FORMATS) if ready else [],
                         "note": "Generated on demand from the finished analysis."},
        "progress": [ProgressEntry(node="report", status="done" if ready else "skipped",
                                   detail="exports ready" if ready else "no predictions")],
    }
