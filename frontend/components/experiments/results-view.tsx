"use client";

import { useState } from "react";

import {
  ApiError,
  decideExperiment,
  getExperimentSummary,
  reanalyseExperiment,
  type Analysis,
  type DecideRequest,
  type Experiment,
  type ExperimentSummaryText,
} from "@/lib/api";
import { DECISION_LABELS, forestRows, healthItems, TONE_CLASSES, VERDICT } from "@/lib/experiments";
import { formatCount, formatMoney, formatP, formatPercent, formatStat } from "@/lib/format";

import { Tex } from "../hypothesis/tex";
import { Alert, Button, Card, Spinner } from "../ui";
import { ArmRateBars, ForestPlot } from "./ci-charts";

const fieldClass =
  "min-h-10 w-full rounded-lg border border-gray-300 bg-white px-3 text-sm dark:border-gray-700 dark:bg-gray-900";

function errorText(e: unknown, fallback: string): string {
  return e instanceof ApiError ? e.message : fallback;
}

function HealthStrip({ exp }: { exp: Experiment }) {
  const items = healthItems(exp);
  return (
    <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4" aria-label="Trust checks">
      {items.map((item) => (
        <li
          key={item.label}
          className={`rounded-lg border p-2 text-sm ${
            item.ok
              ? "border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950"
              : "border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950"
          }`}
        >
          <p className="font-medium">
            <span aria-hidden>{item.ok ? "✓" : "✗"}</span> {item.label}
          </p>
          <p className="text-xs text-gray-600 dark:text-gray-400">{item.detail}</p>
        </li>
      ))}
    </ul>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-lg font-semibold tabular-nums">{value}</p>
      {sub ? <p className="text-xs text-gray-500 tabular-nums">{sub}</p> : null}
    </div>
  );
}

function ImpactCard({ exp, actor, onChange }: { exp: Experiment; actor: string; onChange: (e: Experiment) => void }) {
  const a = exp.analysis as Analysis;
  const impact = a.impact;
  const inputs = a.assumption_inputs;
  const [value, setValue] = useState(inputs?.customer_value != null ? String(inputs.customer_value) : "");
  const [cost, setCost] = useState(inputs?.offer_cost != null ? String(inputs.offer_cost) : "");
  const [tolerance, setTolerance] = useState(String(inputs?.arpu_tolerance ?? 0.05));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const editable = exp.status === "results_uploaded";

  const apply = async () => {
    setBusy(true);
    setError(null);
    try {
      onChange(
        await reanalyseExperiment(exp.id, actor, {
          customer_value: value === "" ? null : Number(value),
          offer_cost: cost === "" ? null : Number(cost),
          arpu_tolerance: Number(tolerance),
        }),
      );
    } catch (e) {
      setError(errorText(e, "Could not recompute the analysis."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Business impact">
      <div className="flex flex-col gap-4 text-sm">
        <div className="grid gap-2 sm:grid-cols-3">
          <Stat
            label="Customers saved"
            value={formatStat(impact.customers_saved, 1)}
            sub={`95% CI ${formatStat(impact.saved_ci_low, 1)} to ${formatStat(impact.saved_ci_high, 1)}`}
          />
          <Stat
            label="Net value"
            value={impact.net_value == null ? "Needs offer cost" : formatMoney(impact.net_value)}
            sub={
              impact.net_value_ci_low != null && impact.net_value_ci_high != null
                ? `95% CI ${formatMoney(impact.net_value_ci_low)} to ${formatMoney(impact.net_value_ci_high)}`
                : undefined
            }
          />
          <Stat
            label="Offers accepted"
            value={formatCount(impact.acceptors)}
            sub={`${formatPercent(impact.acceptance_rate, 1)} of treatment`}
          />
        </div>
        <div className="overflow-x-auto">
          <Tex latex={impact.formula} block />
        </div>
        <div>
          <p className="mb-1 font-medium">Assumptions</p>
          <ul className="flex flex-col gap-1 text-xs text-gray-600 dark:text-gray-400">
            {a.assumptions.map((as) => (
              <li key={as.name}>
                <span className="mr-1 rounded bg-gray-100 px-1.5 py-0.5 font-medium dark:bg-gray-800">{as.source}</span>
                {as.name.replaceAll("_", " ")}: {as.value == null ? "not set" : formatStat(as.value, 2)}
              </li>
            ))}
          </ul>
        </div>
        {editable ? (
          <div className="grid items-end gap-2 sm:grid-cols-4">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium">Value per saved customer</span>
              <input className={fieldClass} type="number" min={0} value={value} placeholder="from data" onChange={(e) => setValue(e.target.value)} />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium">Cost per accepted offer</span>
              <input className={fieldClass} type="number" min={0} value={cost} onChange={(e) => setCost(e.target.value)} />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium">ARPU drop tolerated</span>
              <input className={fieldClass} type="number" min={0} max={1} step={0.01} value={tolerance} onChange={(e) => setTolerance(e.target.value)} />
            </label>
            <Button variant="secondary" onClick={() => void apply()} disabled={busy || !actor.trim()}>
              {busy ? "Recomputing..." : "Recompute"}
            </Button>
          </div>
        ) : null}
        {error ? <Alert tone="error" title={error} /> : null}
      </div>
    </Card>
  );
}

function GuardrailTable({ analysis }: { analysis: Analysis }) {
  const rows = Object.entries(analysis.guardrails);
  if (!rows.length) return <p className="text-sm text-gray-500">No guardrail data in the results file.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[32rem] text-left text-sm">
        <caption className="sr-only">Guardrail metrics per arm</caption>
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-800">
            <th className="py-2 pr-3 font-medium">Metric</th>
            <th className="py-2 pr-3 text-right font-medium">Treatment</th>
            <th className="py-2 pr-3 text-right font-medium">Control</th>
            <th className="py-2 pr-3 text-right font-medium">Difference (95% CI)</th>
            <th className="py-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([name, g]) => (
            <tr key={name} className="border-b border-gray-100 dark:border-gray-900">
              <td className="py-1.5 pr-3">{name === "arpu" ? "Revenue per customer" : "Complaints per customer"}</td>
              <td className="py-1.5 pr-3 text-right tabular-nums">{formatStat(g.arms.treatment.mean, 3)}</td>
              <td className="py-1.5 pr-3 text-right tabular-nums">{formatStat(g.arms.control.mean, 3)}</td>
              <td className="py-1.5 pr-3 text-right tabular-nums">
                {g.difference
                  ? `${formatStat(g.difference.value, 3)} [${formatStat(g.difference.ci_low, 3)}, ${formatStat(g.difference.ci_high, 3)}]`
                  : "–"}
              </td>
              <td className="py-1.5">
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${TONE_CLASSES[g.breached ? "red" : "green"]}`}>
                  {g.breached ? "Breached" : "OK"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SummaryCard({ exp }: { exp: Experiment }) {
  const [summary, setSummary] = useState<ExperimentSummaryText | null>(exp.analysis?.summary ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setBusy(true);
    setError(null);
    try {
      setSummary(await getExperimentSummary(exp.id));
    } catch (e) {
      setError(errorText(e, "Could not write the summary."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Summary for the retention manager">
      {summary ? (
        <div className="flex flex-col gap-2 text-sm">
          <p>{summary.sentences.join(" ")}</p>
          <p className="text-xs text-gray-500">
            {summary.source === "ai"
              ? "Written by AI; every number was checked against the analysis."
              : "Standard wording (the AI version was unavailable or did not pass the checks)."}
          </p>
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={() => void load()} disabled={busy}>
            Write summary
          </Button>
          {busy ? <Spinner label="Writing the summary..." /> : null}
        </div>
      )}
      {error ? <Alert tone="error" title={error} /> : null}
    </Card>
  );
}

function DecisionForm({ exp, actor, onChange }: { exp: Experiment; actor: string; onChange: (e: Experiment) => void }) {
  const srmFailed = Boolean(exp.analysis?.srm.failed);
  const [decision, setDecision] = useState<DecideRequest["decision"]>(srmFailed ? "extend" : "ship");
  const [note, setNote] = useState("");
  const [newEnd, setNewEnd] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      onChange(
        await decideExperiment(exp.id, {
          decision,
          decider: actor,
          note,
          new_planned_end: decision === "extend" && newEnd ? newEnd : null,
        }),
      );
    } catch (e) {
      setError(errorText(e, "Could not record the decision."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Decision">
      <div className="flex flex-col gap-3 text-sm">
        <p className="text-gray-600 dark:text-gray-400">
          The verdict above is a suggestion. A person records the decision; it is kept in the audit trail.
        </p>
        <fieldset className="flex flex-wrap gap-4">
          <legend className="sr-only">Decision</legend>
          {(["ship", "dont_ship", "extend"] as const).map((d) => (
            <label key={d} className="flex items-center gap-1">
              <input
                type="radio"
                name={`decision-${exp.id}`}
                checked={decision === d}
                disabled={d === "ship" && srmFailed}
                onChange={() => setDecision(d)}
              />
              {DECISION_LABELS[d]}
            </label>
          ))}
        </fieldset>
        {srmFailed ? <p className="text-xs text-red-700 dark:text-red-300">Ship is blocked: the sample ratio check failed.</p> : null}
        {decision === "extend" ? (
          <label className="flex flex-col gap-1">
            <span className="font-medium">New planned end (optional)</span>
            <input className={fieldClass} type="date" value={newEnd} onChange={(e) => setNewEnd(e.target.value)} />
          </label>
        ) : null}
        <label className="flex flex-col gap-1">
          <span className="font-medium">Note (required)</span>
          <textarea className={`${fieldClass} py-2`} rows={2} value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} />
        </label>
        {error ? <Alert tone="error" title={error} /> : null}
        <div>
          <Button onClick={() => void submit()} disabled={busy || !note.trim() || !actor.trim()}>
            {busy ? "Saving..." : "Record decision"}
          </Button>
        </div>
      </div>
    </Card>
  );
}

export function ResultsView({ exp, actor, onChange }: { exp: Experiment; actor: string; onChange: (e: Experiment) => void }) {
  const a = exp.analysis;
  if (!a) return null;
  const itt = a.itt;
  const verdict = VERDICT[a.decision_helper.verdict];
  const pp = a.per_protocol;

  return (
    <div className="flex flex-col gap-6">
      <HealthStrip exp={exp} />
      {(a.warnings ?? []).map((w) => (
        <Alert key={w} tone="warning">
          {w}
        </Alert>
      ))}

      <Card title="Primary result: churn">
        <div className="flex flex-col gap-4">
          {itt.arms ? <ArmRateBars arms={itt.arms} /> : null}
          <div className="grid gap-2 sm:grid-cols-4">
            <Stat
              label="Difference"
              value={formatPercent(itt.difference?.value, 1)}
              sub={itt.difference ? `95% CI ${formatPercent(itt.difference.ci_low, 1)} to ${formatPercent(itt.difference.ci_high, 1)}` : undefined}
            />
            <Stat label="Relative change" value={formatPercent(itt.relative_lift, 1)} />
            <Stat label="p-value" value={formatP(itt.p_value)} sub="two-proportion z-test" />
            <Stat label="Power for planned effect" value={formatPercent(itt.achieved_power, 0)} sub="at the observed size" />
          </div>
          <ForestPlot rows={forestRows(a)} />
        </div>
      </Card>

      <Card title="Decision helper">
        <div className="flex flex-col gap-2 text-sm">
          <p>
            <span className={`rounded-full px-2.5 py-1 text-sm font-medium ${TONE_CLASSES[verdict.tone]}`}>{verdict.label}</span>
          </p>
          <ul className="list-disc pl-5">
            {a.decision_helper.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          {a.decision_helper.extra_sample_needed &&
          (a.decision_helper.extra_sample_needed.treatment > 0 || a.decision_helper.extra_sample_needed.control > 0) ? (
            <p>
              Extra customers needed for the planned power: {formatCount(a.decision_helper.extra_sample_needed.treatment)}{" "}
              treatment and {formatCount(a.decision_helper.extra_sample_needed.control)} control.
            </p>
          ) : null}
          <p className="text-xs text-gray-500">{a.decision_helper.note}</p>
        </div>
      </Card>

      <SummaryCard key={a.upload?.file_sha256 ?? "summary"} exp={exp} />
      <ImpactCard key={JSON.stringify(a.assumption_inputs)} exp={exp} actor={actor} onChange={onChange} />

      <Card title="Guardrails">
        <GuardrailTable analysis={a} />
      </Card>

      {pp.available && pp.difference ? (
        <Card title="Acceptors only (per-protocol)">
          <p className="mb-2 text-sm text-amber-800 dark:text-amber-200">{pp.label}</p>
          <p className="text-sm tabular-nums">
            Churn {formatPercent(pp.arms?.treatment.rate, 1)} among acceptors vs {formatPercent(pp.arms?.control.rate, 1)} in
            control; difference {formatPercent(pp.difference.value, 1)} (95% CI {formatPercent(pp.difference.ci_low, 1)} to{" "}
            {formatPercent(pp.difference.ci_high, 1)}).
          </p>
        </Card>
      ) : null}

      {exp.status === "results_uploaded" ? (
        <DecisionForm exp={exp} actor={actor} onChange={onChange} />
      ) : exp.status === "decided" ? (
        <Card title="Decision">
          <p className="text-sm">
            <span className="font-medium">{DECISION_LABELS[exp.decision ?? ""] ?? exp.decision}</span>
            {exp.decision_note ? `: ${exp.decision_note}` : ""}
          </p>
        </Card>
      ) : null}
    </div>
  );
}
