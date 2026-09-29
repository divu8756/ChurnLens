"use client";

import { useState } from "react";

import { ApiError, confirmSchema, type SchemaProposal } from "@/lib/api";
import {
  SEMANTIC_TYPES,
  draftFromProposal,
  draftProblems,
  labelValues,
  toConfirmed,
  withColumnType,
  withTarget,
  type SchemaDraft,
  type SemanticType,
} from "@/lib/schema-form";

import { Alert, Button, Card, Spinner } from "./ui";

const selectClass =
  "min-h-9 w-full rounded-lg border border-gray-300 bg-white px-2 text-sm dark:border-gray-700 dark:bg-gray-900";

export function SchemaConfirmation({
  sessionId,
  proposal,
  onExpired,
}: {
  sessionId: string;
  proposal: SchemaProposal;
  onExpired: () => void;
}) {
  const [draft, setDraft] = useState<SchemaDraft>(() => draftFromProposal(proposal));
  const [sending, setSending] = useState(false);
  const [serverProblems, setServerProblems] = useState<{ message: string; problems: string[] } | null>(null);
  const localProblems = draftProblems(draft);
  const names = draft.columns.map((c) => c.name);
  const values = draft.target_column ? labelValues(proposal, draft.target_column) : null;
  const numericNames = draft.columns.filter((c) => c.semantic_type === "numeric").map((c) => c.name);

  const submit = async () => {
    setSending(true);
    setServerProblems(null);
    try {
      await confirmSchema(sessionId, toConfirmed(draft));
      // The stream reports "resumed" and the view moves on.
    } catch (e) {
      if (e instanceof ApiError && e.kind === "expired") {
        onExpired();
      } else if (e instanceof ApiError) {
        setServerProblems({ message: e.message, problems: e.problems });
      } else {
        setServerProblems({ message: "Could not send the schema. Please try again.", problems: [] });
      }
    } finally {
      setSending(false);
    }
  };

  return (
    <Card title="Confirm the columns">
      <div className="flex flex-col gap-5">
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Check what each column holds before the analysis runs. ID columns are ignored by the statistics and the
          model.
        </p>
        {proposal.reasoning ? (
          <Alert tone="info" title={proposal.source === "ai+rules" ? "AI proposal (checked by rules)" : "Proposed by rules"}>
            {proposal.reasoning}
          </Alert>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium">Target (churn) column</span>
            <select
              className={selectClass}
              value={draft.target_column}
              onChange={(e) => setDraft(withTarget(draft, proposal, e.target.value))}
            >
              <option value="">Choose a column</option>
              {names.map((n) => (
                <option key={n} value={n}>
                  {n}
                  {proposal.target_candidates?.includes(n) ? " (suggested)" : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium">Value that means &ldquo;churned&rdquo;</span>
            {values ? (
              <select
                className={selectClass}
                value={draft.positive_label}
                onChange={(e) => setDraft({ ...draft, positive_label: e.target.value })}
              >
                {values.map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            ) : (
              <input
                className={selectClass}
                value={draft.positive_label}
                placeholder="e.g. Yes"
                onChange={(e) => setDraft({ ...draft, positive_label: e.target.value })}
              />
            )}
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium">Time column (tenure, optional)</span>
            <select
              className={selectClass}
              value={draft.time_column ?? ""}
              onChange={(e) => setDraft({ ...draft, time_column: e.target.value || null })}
            >
              <option value="">None</option>
              {numericNames.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium">Monthly revenue column (optional)</span>
            <select
              className={selectClass}
              value={draft.revenue_column ?? ""}
              onChange={(e) => setDraft({ ...draft, revenue_column: e.target.value || null })}
            >
              <option value="">None</option>
              {numericNames.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="max-h-96 overflow-auto rounded-lg border border-gray-200 dark:border-gray-800">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-gray-50 dark:bg-gray-900">
              <tr>
                <th className="px-3 py-2 font-medium">Column</th>
                <th className="px-3 py-2 font-medium">Type</th>
                <th className="hidden px-3 py-2 font-medium sm:table-cell">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {draft.columns.map((c) => (
                <tr key={c.name} className="border-t border-gray-100 dark:border-gray-800">
                  <td className="px-3 py-1.5 break-all">
                    {c.name}
                    {c.name === draft.target_column ? <span className="ml-2 text-xs text-blue-600">target</span> : null}
                  </td>
                  <td className="px-3 py-1.5">
                    <select
                      aria-label={`Type of ${c.name}`}
                      className={selectClass}
                      value={c.semantic_type}
                      onChange={(e) => setDraft(withColumnType(draft, c.name, e.target.value as SemanticType))}
                    >
                      {SEMANTIC_TYPES.map((t) => (
                        <option key={t} value={t}>
                          {t === "id" ? "ID (ignored)" : t}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="hidden px-3 py-1.5 text-gray-500 sm:table-cell">{Math.round(c.confidence * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {localProblems.length ? (
          <Alert tone="warning" title="Fix these before continuing">
            <ul className="list-disc pl-5">
              {localProblems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </Alert>
        ) : null}
        {serverProblems ? (
          <Alert tone="error" title={serverProblems.message}>
            {serverProblems.problems.length ? (
              <ul className="list-disc pl-5">
                {serverProblems.problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            ) : null}
          </Alert>
        ) : null}

        <div className="flex items-center gap-3">
          <Button onClick={() => void submit()} disabled={sending || localProblems.length > 0}>
            Confirm and run the analysis
          </Button>
          {sending ? <Spinner label="Sending..." /> : null}
        </div>
      </div>
    </Card>
  );
}
