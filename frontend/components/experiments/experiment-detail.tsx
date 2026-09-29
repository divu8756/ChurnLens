"use client";

import { useState } from "react";

import {
  ApiError,
  approveExperiment,
  assignExperiment,
  assignmentCsvUrl,
  uploadExperimentResults,
  type Experiment,
} from "@/lib/api";
import { segmentText, statusInfo, TONE_CLASSES } from "@/lib/experiments";
import { formatCount, formatPercent, formatStat } from "@/lib/format";

import { Alert, Button, Card } from "../ui";
import { ResultsView } from "./results-view";

const fieldClass =
  "min-h-10 w-full rounded-lg border border-gray-300 bg-white px-3 text-sm dark:border-gray-700 dark:bg-gray-900";

export function StatusChip({ status }: { status: string }) {
  const info = statusInfo(status);
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${TONE_CLASSES[info.tone]}`}>{info.label}</span>;
}

function useAction(onChange: (e: Experiment) => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const run = async (action: () => Promise<Experiment>) => {
    setBusy(true);
    setError(null);
    try {
      onChange(await action());
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("network", "The request failed."));
    } finally {
      setBusy(false);
    }
  };
  return { busy, error, run };
}

function ErrorBox({ error }: { error: ApiError | null }) {
  if (!error) return null;
  return (
    <Alert tone="error" title={error.message}>
      {error.problems.length ? (
        <ul className="list-disc pl-5">
          {error.problems.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      ) : null}
    </Alert>
  );
}

function DesignCard({ exp }: { exp: Experiment }) {
  const rows: [string, string][] = [
    ["Offer", exp.offer],
    ["Eligible", segmentText(exp.segment_definition.filters ?? [])],
    ["Baseline churn", formatPercent(exp.baseline_rate, 1)],
    ["Minimum detectable effect", exp.mde_type === "absolute" ? `${formatStat(exp.mde * 100, 1)} points` : `${formatPercent(exp.mde, 0)} relative`],
    ["α / power", `${exp.alpha} / ${formatPercent(exp.power, 0)}`],
    ["Split", `${formatPercent(1 - exp.control_share, 0)} treatment / ${formatPercent(exp.control_share, 0)} control`],
    ["Customers needed", `${formatCount(exp.n_required_treatment)} + ${formatCount(exp.n_required_control)}`],
    ["Outcome", `churn within ${exp.outcome_window_days} days`],
    ["Planned", exp.planned_start || exp.planned_end ? `${exp.planned_start ?? "not set"} to ${exp.planned_end ?? "not set"}` : "Dates not set"],
    ["Guardrails", exp.guardrail_metrics.join(", ") || "none"],
  ];
  return (
    <Card title="Design">
      <p className="mb-3 text-sm">{exp.hypothesis}</p>
      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-3 border-b border-gray-100 py-1 dark:border-gray-900">
            <dt className="text-gray-500">{k}</dt>
            <dd className="text-right">{v}</dd>
          </div>
        ))}
      </dl>
      {exp.preregistered_segments?.length ? (
        <p className="mt-3 text-xs text-gray-500">
          Pre-registered segments: {exp.preregistered_segments.map((s) => `${s.name} (${segmentText(s.filters)})`).join("; ")}
        </p>
      ) : null}
      {(exp.design?.warnings ?? []).map((w) => (
        <div key={w} className="mt-3">
          <Alert tone="warning">{w}</Alert>
        </div>
      ))}
    </Card>
  );
}

function ApproveCard({ exp, actor, onChange }: { exp: Experiment; actor: string; onChange: (e: Experiment) => void }) {
  const [reviewed, setReviewed] = useState(false);
  const [note, setNote] = useState("");
  const { busy, error, run } = useAction(onChange);
  return (
    <Card title="Approval">
      <div className="flex flex-col gap-3 text-sm">
        <p className="text-gray-600 dark:text-gray-400">Approving locks the design: it can no longer be edited.</p>
        <label className="flex items-start gap-2">
          <input type="checkbox" checked={reviewed} onChange={(e) => setReviewed(e.target.checked)} className="mt-1" />
          I reviewed the offer cost and who is eligible.
        </label>
        <label className="flex flex-col gap-1">
          <span className="font-medium">Note (optional)</span>
          <input className={fieldClass} value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} />
        </label>
        <ErrorBox error={error} />
        <div>
          <Button
            disabled={!reviewed || busy || !actor.trim()}
            onClick={() => void run(() => approveExperiment(exp.id, { approver: actor, cost_and_eligibility_reviewed: reviewed, note: note || null }))}
          >
            {busy ? "Approving..." : `Approve as ${actor || "..."}`}
          </Button>
        </div>
      </div>
    </Card>
  );
}

function AssignCard({ exp, actor, sessionId, onChange }: { exp: Experiment; actor: string; sessionId: string; onChange: (e: Experiment) => void }) {
  const { busy, error, run } = useAction(onChange);
  return (
    <Card title="Assignment">
      <div className="flex flex-col gap-3 text-sm">
        <p className="text-gray-600 dark:text-gray-400">
          Customers in the segment from this analysis are split at random (a hash of experiment and customer ID, so the
          same customer always lands in the same group). Customers in another running experiment are left out.
        </p>
        <ErrorBox error={error} />
        <div>
          <Button disabled={busy || !actor.trim()} onClick={() => void run(() => assignExperiment(exp.id, sessionId, actor))}>
            {busy ? "Assigning..." : "Assign customers"}
          </Button>
        </div>
      </div>
    </Card>
  );
}

function AssignmentSummary({ exp }: { exp: Experiment }) {
  const s = exp.assignment_summary;
  if (!s) return null;
  return (
    <Card
      title="Assigned groups"
      actions={
        <a className="text-sm font-medium text-blue-700 hover:underline dark:text-blue-300" href={assignmentCsvUrl(exp.id)}>
          Download assignment CSV
        </a>
      }
    >
      <div className="flex flex-col gap-3 text-sm">
        <p>
          {formatCount(s.n_treatment)} treatment and {formatCount(s.n_control)} control (needed {formatCount(s.required_treatment)} +{" "}
          {formatCount(s.required_control)}). {s.messages_attached ? `${formatCount(s.messages_attached)} offer messages attached.` : ""}
        </p>
        {s.warnings.map((w) => (
          <Alert key={w} tone="warning">
            {w}
          </Alert>
        ))}
        <details>
          <summary className="cursor-pointer text-gray-600 dark:text-gray-400">
            Balance check ({s.balance.balanced ? "balanced" : `${s.balance.flagged.length} flagged`})
          </summary>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[28rem] text-left text-xs">
              <caption className="sr-only">Standardised mean differences, treatment vs control</caption>
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-800">
                  <th className="py-1 pr-3 font-medium">Covariate</th>
                  <th className="py-1 pr-3 text-right font-medium">Treatment</th>
                  <th className="py-1 pr-3 text-right font-medium">Control</th>
                  <th className="py-1 text-right font-medium">SMD</th>
                </tr>
              </thead>
              <tbody>
                {s.balance.covariates.map((c) => (
                  <tr key={`${c.covariate}-${c.level ?? ""}`} className={c.flagged ? "text-red-700 dark:text-red-300" : ""}>
                    <td className="py-1 pr-3">{c.level ? `${c.covariate} = ${c.level}` : c.covariate}</td>
                    <td className="py-1 pr-3 text-right tabular-nums">{formatStat(c.treatment_mean, 3)}</td>
                    <td className="py-1 pr-3 text-right tabular-nums">{formatStat(c.control_mean, 3)}</td>
                    <td className="py-1 text-right tabular-nums">{formatStat(c.smd, 3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>
    </Card>
  );
}

function UploadCard({ exp, actor, onChange }: { exp: Experiment; actor: string; onChange: (e: Experiment) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [value, setValue] = useState("");
  const [cost, setCost] = useState("");
  const { busy, error, run } = useAction(onChange);
  return (
    <Card title={exp.status === "results_uploaded" ? "Replace results" : "Upload results"}>
      <div className="flex flex-col gap-3 text-sm">
        <p className="text-gray-600 dark:text-gray-400">
          CSV with customer_id, group, churned (0/1 within the window), offer_accepted (treatment), and optionally revenue,
          complaints and churn_date.
        </p>
        <input type="file" accept=".csv,text/csv" aria-label="Results CSV" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium">Value per saved customer (optional)</span>
            <input className={fieldClass} type="number" min={0} value={value} placeholder="estimated from the data" onChange={(e) => setValue(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium">Cost per accepted offer</span>
            <input className={fieldClass} type="number" min={0} value={cost} onChange={(e) => setCost(e.target.value)} />
          </label>
        </div>
        <ErrorBox error={error} />
        <div>
          <Button
            disabled={!file || busy || !actor.trim()}
            onClick={() =>
              file &&
              void run(() =>
                uploadExperimentResults(exp.id, file, actor, {
                  customer_value: value === "" ? null : Number(value),
                  offer_cost: cost === "" ? null : Number(cost),
                }),
              )
            }
          >
            {busy ? "Analysing..." : "Upload and analyse"}
          </Button>
        </div>
      </div>
    </Card>
  );
}

function AuditTrail({ exp }: { exp: Experiment }) {
  return (
    <Card title="Audit trail">
      <ol className="flex flex-col gap-2 text-sm">
        {(exp.audit ?? []).map((entry, i) => (
          <li key={i} className="border-l-2 border-gray-200 pl-3 dark:border-gray-800">
            <p>
              <span className="font-medium">{entry.action.replaceAll("_", " ")}</span> by {entry.actor}
              {entry.to_status ? ` → ${statusInfo(entry.to_status).label}` : ""}
            </p>
            <p className="text-xs text-gray-500">
              {new Date(entry.at).toLocaleString()}
              {entry.note ? ` · ${entry.note}` : ""}
            </p>
          </li>
        ))}
      </ol>
    </Card>
  );
}

export function ExperimentDetail({
  exp,
  actor,
  sessionId,
  onChange,
}: {
  exp: Experiment;
  actor: string;
  sessionId: string;
  onChange: (e: Experiment) => void;
}) {
  const info = statusInfo(exp.status);
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-xl font-semibold">{exp.name}</h2>
          <StatusChip status={exp.status} />
        </div>
        <p className="text-sm text-gray-600 dark:text-gray-400">Next: {info.next}</p>
      </div>
      {exp.analysis ? <ResultsView exp={exp} actor={actor} onChange={onChange} /> : null}
      <DesignCard exp={exp} />
      {exp.status === "draft" ? <ApproveCard exp={exp} actor={actor} onChange={onChange} /> : null}
      {exp.status === "approved" ? <AssignCard exp={exp} actor={actor} sessionId={sessionId} onChange={onChange} /> : null}
      <AssignmentSummary exp={exp} />
      {exp.status === "running" || exp.status === "results_uploaded" ? <UploadCard exp={exp} actor={actor} onChange={onChange} /> : null}
      <AuditTrail exp={exp} />
    </div>
  );
}
