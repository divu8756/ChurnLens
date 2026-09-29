"""One real end-to-end run on the Telco sample with Gemini (runbook T5.5).

    backend/.venv/bin/python scripts/run_telco_live.py [report.md]

Accepts the AI schema proposal as-is, runs the whole graph, and writes a
Markdown report (no secrets): runtime, LLM calls and tokens per agent,
validator results and the final insights/recommendations. Stops making LLM
calls after MAX_CALLS.
"""

import sys
import time
from collections import defaultdict
from pathlib import Path
from tempfile import mkdtemp

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import pandas as pd  # noqa: E402
from app import llm  # noqa: E402
from app.graph.builder import build_graph  # noqa: E402
from app.graph.checkpointer import make_serde  # noqa: E402
from app.graph.nodes import default_nodes  # noqa: E402
from app.graph.state import ProgressEntry  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from langgraph.types import Command  # noqa: E402

MAX_CALLS = 60
SCHEMA_TO_AGENT = {"SchemaProposal": "schema_agent", "InsightList": "insight_agent",
                   "RecommendationList": "recommendation_agent"}


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "runs" / "telco_run.md"
    records: list[llm.CallRecord] = []

    def count(record: llm.CallRecord) -> None:
        records.append(record)
        if sum(r.attempts for r in records) >= MAX_CALLS:
            raise SystemExit(f"Stopped: reached the cap of {MAX_CALLS} Gemini calls.")

    llm.add_usage_listener(count)

    folder = Path(mkdtemp(prefix="churnlens-live-"))
    raw = pd.read_csv(ROOT / "backend" / "sample_data" / "telco_churn.csv")
    raw.to_parquet(folder / "raw.parquet", index=False)

    nodes = default_nodes()

    def ingest(state):  # the uploaded file lives in a temp folder, not a session
        return {"raw_path": str(folder / "raw.parquet"),
                "progress": [ProgressEntry(node="ingest", status="done",
                                           detail=f"{len(raw)} rows")]}
    nodes["ingest"] = ingest

    graph = build_graph(nodes=nodes, checkpointer=InMemorySaver(serde=make_serde()))
    config = {"configurable": {"thread_id": "telco-live"}}
    started = time.monotonic()
    graph.invoke({"session_id": "0" * 32}, config)
    proposal = graph.get_state(config).interrupts[0].value["proposal"]
    schema = {k: proposal[k] for k in ("target_column", "positive_label", "id_columns",
                                       "time_column", "revenue_column")}
    schema["columns"] = [{"name": c["name"], "semantic_type": c["semantic_type"]}
                         for c in proposal["columns"]]
    state = graph.invoke(Command(resume=schema), config)
    runtime = time.monotonic() - started

    per_agent: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in records:
        agent = SCHEMA_TO_AGENT.get(r.schema, r.schema)
        per_agent[agent]["calls"] += 1
        per_agent[agent]["attempts"] += r.attempts
        per_agent[agent]["ok"] += r.outcome == "ok"
        per_agent[agent]["input_tokens"] += r.input_tokens
        per_agent[agent]["output_tokens"] += r.output_tokens
        per_agent[agent]["latency_ms"] += r.latency_ms
    report = state.get("validation_report") or {}
    lines = [
        "# ChurnLens live run: Telco sample", "",
        f"- Runtime: {runtime:.1f} s (includes the schema proposal)",
        f"- Schema proposal source: {proposal.get('source')}",
        f"- Models: pro tier = {llm.model_name('pro')}, fast tier = {llm.model_name('fast')}",
        f"- Model: {state['model_metrics']['chosen_model_name']}, test ROC-AUC "
        f"{state['model_metrics']['test']['roc_auc']:.3f}",
        f"- Validator: {report.get('passed')}/{report.get('checked')} items passed, "
        f"{report.get('dropped')} dropped, retries {state.get('retry_counts')}",
        "- Cost: ESTIMATE 0 (Gemini free tier)", "",
        "## LLM calls per agent", "",
        "| Agent | Calls | Attempts | OK | Input tokens | Output tokens | Latency (s) |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for agent, s in per_agent.items():
        lines.append(f"| {agent} | {s['calls']} | {s['attempts']} | {s['ok']} | "
                     f"{s['input_tokens']:,} | {s['output_tokens']:,} | "
                     f"{s['latency_ms'] / 1000:.1f} |")
    lines += ["", "## Errors", ""]
    lines += [f"- {e.node}: {e.message}" for e in state.get("errors", [])] or ["- none"]
    lines += ["", "## Validator details", ""]
    for d in report.get("details", []):
        status = "ok" if d["ok"] else "; ".join(d["problems"])
        lines.append(f"- {d['agent']} {d['id']}: {status}")
    lines += ["", "## Final insights", ""]
    for i in state.get("final_insights", []):
        lines.append(f"{i['id']}. **{i['title']}**: {i['text']}")
    lines += ["", "## Final recommendations", ""]
    for r in state.get("final_recommendations", []):
        lines.append(f"{r['id']} (priority {r['priority']}, {r['group']}, {r['effort']} effort): "
                     f"**{r['action']}** Problem: {r['problem']} Target: {r['target_segment']}. "
                     f"Impact: {r['impact']['value']:g} ({r['impact']['assumption']})")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out} in {runtime:.1f}s; LLM attempts {sum(r.attempts for r in records)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
