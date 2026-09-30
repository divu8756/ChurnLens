"use client";

import { useEffect, useState } from "react";

import { ApiError, getRunSummary, listRunSummaries, type RunSummary } from "@/lib/api";
import { formatCount, formatPercent, formatStat } from "@/lib/format";
import { PALETTE } from "@/lib/palette";

import { PlotlyChart } from "../charts/plotly-chart";
import { KpiTile } from "../metrics/kpi-tile";
import { Alert, Card, EmptyState, Spinner } from "../ui";

const HELP = {
  pass_rate: "Share of AI-written insights and recommendations whose every number matched the computed results.",
  caught: "Numbers the validator rejected because they did not match the data (the agent was asked to fix them).",
  corrections: "Schema fields you changed after the AI's proposal (target, IDs, column types...).",
  latency: "Time the pipeline was busy: parallel steps count once and the wait for you to confirm the columns is left out.",
  tokens: "Tokens sent to and received from Gemini in this run.",
  cost: "ESTIMATE from app/config/pricing.yaml; the free tier costs nothing.",
};

function seconds(ms: number | null | undefined): string {
  return ms == null ? "–" : `${formatStat(ms / 1000, 1)} s`;
}

export function AgentHealthTab({ sessionId }: { sessionId: string }) {
  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [history, setHistory] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getRunSummary(sessionId, controller.signal)
      .then(setSummary)
      .catch((e: unknown) => {
        if (!controller.signal.aborted) setError(e instanceof ApiError ? e.message : "Could not load the run summary.");
      });
    listRunSummaries(50, controller.signal)
      .then(setHistory)
      .catch(() => {
        if (!controller.signal.aborted) setHistory([]);
      });
    return () => controller.abort();
  }, [sessionId]);

  if (error) return <Alert tone="error" title={error} />;
  if (!summary) return <Spinner label="Loading agent health..." />;
  const v = summary.validator;
  const nodes = [...summary.latency_ms.by_node].sort((a, b) => b.latency_ms - a.latency_ms);
  const trend = [...(history ?? [])].reverse();

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        <KpiTile label="Validator pass rate" value={formatPercent(v.pass_rate, 0)} note={`${v.passed} of ${v.checked} items`} help={HELP.pass_rate} />
        <KpiTile label="Figures caught" value={formatCount(v.figures_caught)} note={`${v.dropped} items dropped`} help={HELP.caught} />
        <KpiTile label="Schema corrections" value={formatCount(summary.schema_corrections.count)} help={HELP.corrections} />
        <KpiTile label="Run time" value={seconds(summary.latency_ms.wall_clock)} note={`${formatCount(summary.events)} steps`} help={HELP.latency} />
        <KpiTile
          label="Tokens in"
          value={formatCount(summary.tokens.input)}
          note={`${formatCount(summary.tokens.output)} out`}
          help={HELP.tokens}
        />
        <KpiTile
          label="Cost (ESTIMATE)"
          value={`${formatStat(summary.cost.total, 4)} ${summary.cost.currency}`}
          note={summary.cost.note}
          help={HELP.cost}
        />
      </div>

      <Card title="Time per step">
        {nodes.length ? (
          <PlotlyChart
            label="Latency per pipeline step"
            height={Math.max(260, 40 + nodes.length * 24)}
            data={[
              {
                type: "bar",
                orientation: "h",
                y: nodes.map((n) => n.node.replaceAll("_", " ")),
                x: nodes.map((n) => n.latency_ms / 1000),
                text: nodes.map((n) => `${n.status}${n.runs > 1 ? `, ${n.runs} runs` : ""}`),
                hovertemplate: "%{y}: %{x:.2f} s (%{text})<extra></extra>",
                textposition: "none",
                marker: { color: nodes.map((n) => (n.status === "failed" ? PALETTE.vermillion : PALETTE.blue)) },
              },
            ]}
            layout={{ yaxis: { automargin: true, autorange: "reversed" }, xaxis: { title: { text: "Seconds" } }, showlegend: false }}
          />
        ) : (
          <EmptyState>No step timings were recorded for this run.</EmptyState>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Retries">
          {Object.keys(summary.retries.validator).length || Object.keys(summary.retries.llm_by_node).length ? (
            <ul className="flex flex-col gap-1 text-sm">
              {Object.entries(summary.retries.validator).map(([agent, n]) => (
                <li key={`v-${agent}`}>
                  {agent.replaceAll("_", " ")}: {n} validator {n === 1 ? "retry" : "retries"}
                </li>
              ))}
              {Object.entries(summary.retries.llm_by_node).map(([node, n]) => (
                <li key={`l-${node}`}>
                  {node.replaceAll("_", " ")}: {n} model {n === 1 ? "retry" : "retries"} (errors or timeouts)
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState>No retries in this run.</EmptyState>
          )}
        </Card>
        <Card title="Schema corrections">
          {summary.schema_corrections.fields.length ? (
            <ul className="flex flex-col gap-1 text-sm">
              {summary.schema_corrections.fields.map((f) => (
                <li key={f.field}>
                  <span className="font-medium">{f.field}</span>: AI proposed {JSON.stringify(f.proposed)}, you confirmed{" "}
                  {JSON.stringify(f.confirmed)}
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState>You kept the AI&apos;s proposed schema.</EmptyState>
          )}
        </Card>
      </div>

      <Card title="Tokens by model">
        {Object.keys(summary.tokens.by_model).length ? (
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Tokens and estimated cost per model</caption>
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-800">
                <th className="py-2 pr-3 font-medium">Model</th>
                <th className="py-2 pr-3 text-right font-medium">Input</th>
                <th className="py-2 pr-3 text-right font-medium">Output</th>
                <th className="py-2 text-right font-medium">Cost (ESTIMATE)</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(summary.tokens.by_model).map(([model, t]) => (
                <tr key={model} className="border-b border-gray-100 dark:border-gray-900">
                  <td className="py-1.5 pr-3 font-mono text-xs">{model}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{formatCount(t.input_tokens)}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{formatCount(t.output_tokens)}</td>
                  <td className="py-1.5 text-right tabular-nums">{formatStat(summary.cost.by_model[model], 4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <EmptyState>No AI calls were recorded for this run.</EmptyState>
        )}
      </Card>

      <Card title="Recent runs">
        {history === null ? (
          <Spinner label="Loading run history..." />
        ) : trend.length < 2 ? (
          <EmptyState>The trend appears after two or more finished runs from this browser.</EmptyState>
        ) : (
          <PlotlyChart
            label="Validator pass rate and run time over recent runs"
            data={[
              {
                type: "scatter",
                mode: "lines+markers",
                name: "Pass rate",
                x: trend.map((r) => r.created_at ?? ""),
                y: trend.map((r) => r.validator.pass_rate ?? null),
                line: { color: PALETTE.blue },
              },
              {
                type: "scatter",
                mode: "lines+markers",
                name: "Run time (s)",
                x: trend.map((r) => r.created_at ?? ""),
                y: trend.map((r) => r.latency_ms.wall_clock / 1000),
                yaxis: "y2",
                line: { color: PALETTE.orange },
              },
            ]}
            layout={{
              yaxis: { title: { text: "Pass rate" }, range: [0, 1] },
              yaxis2: { title: { text: "Seconds" }, overlaying: "y", side: "right", showgrid: false },
              margin: { t: 16, r: 64, b: 48, l: 56 },
            }}
          />
        )}
      </Card>
    </div>
  );
}
