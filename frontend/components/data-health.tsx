"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { components } from "@/lib/api-types";

import { Card, EmptyState } from "./ui";

type DataHealth = components["schemas"]["DataHealth"];
type CleaningStep = components["schemas"]["CleaningStep"];

const MAX_BARS = 15;
const STEP_NAMES: Record<string, string> = {
  unify_case: "Unified spelling",
  trim_whitespace: "Trimmed spaces",
  blank_to_missing: "Blank to missing",
  drop_duplicates: "Removed duplicates",
};

const fmt = new Intl.NumberFormat("en");

function scoreTone(score: number): string {
  if (score >= 80) return "text-green-600";
  if (score >= 60) return "text-amber-600";
  return "text-red-600";
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  );
}

export function DataHealthView({ health, log }: { health: DataHealth; log: CleaningStep[] }) {
  // Display only: the percentages come from the API; the browser just picks the non-zero ones.
  const missing = Object.entries(health.missing_pct_before)
    .filter(([, pct]) => pct > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, MAX_BARS)
    .map(([column, pct]) => ({ column, before: pct, after: health.missing_pct_after[column] ?? 0 }));
  const balance = health.class_balance;

  return (
    <Card title="Data health">
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap items-end gap-6">
          <div>
            <p className="text-xs text-gray-500">Health score</p>
            <p className={`text-4xl font-bold ${scoreTone(health.health_score)}`}>
              {health.health_score}
              <span className="text-base font-normal text-gray-500"> / 100</span>
            </p>
          </div>
          <details className="max-w-xl text-xs text-gray-600 dark:text-gray-400">
            <summary className="cursor-pointer">How is this scored?</summary>
            <p className="mt-1">{health.score_formula}</p>
          </details>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Rows before" value={fmt.format(health.rows_before)} />
          <Stat label="Rows after" value={fmt.format(health.rows_after)} />
          <Stat label="Columns" value={fmt.format(health.columns)} />
          <Stat label="Duplicates removed" value={fmt.format(health.duplicates_removed)} />
        </div>

        <div>
          <h3 className="mb-2 text-sm font-semibold">Class balance</h3>
          <div className="flex h-6 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-800" aria-hidden>
            <div className="bg-red-500" style={{ width: `${balance.positive_rate * 100}%` }} />
          </div>
          <p className="mt-2 text-sm">
            <span className="font-medium text-red-600">
              {fmt.format(balance.positive)} churned (&ldquo;{balance.positive_label}&rdquo;)
            </span>{" "}
            vs {fmt.format(balance.negative)} retained: churn rate {(balance.positive_rate * 100).toFixed(2)}%.
          </p>
        </div>

        <div>
          <h3 className="mb-2 text-sm font-semibold">Missing values by column (%)</h3>
          {missing.length ? (
            <div className="h-72 w-full">
              <ResponsiveContainer>
                <BarChart data={missing} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" unit="%" fontSize={12} />
                  <YAxis type="category" dataKey="column" width={120} fontSize={12} />
                  <Tooltip formatter={(value) => `${value}%`} />
                  <Bar dataKey="before" name="Before cleaning" fill="#f59e0b" />
                  <Bar dataKey="after" name="After cleaning" fill="#2563eb" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState>No missing values.</EmptyState>
          )}
          <p className="mt-1 text-xs text-gray-500">
            Remaining gaps are filled inside the model on the training data only, so test data never leaks in.
          </p>
        </div>

        <div>
          <h3 className="mb-2 text-sm font-semibold">Cleaning log</h3>
          {log.length ? (
            <div className="max-h-80 overflow-auto rounded-lg border border-gray-200 dark:border-gray-800">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-gray-50 dark:bg-gray-900">
                  <tr>
                    <th className="px-3 py-2 font-medium">Step</th>
                    <th className="px-3 py-2 font-medium">Column</th>
                    <th className="px-3 py-2 text-right font-medium">Rows</th>
                    <th className="hidden px-3 py-2 font-medium sm:table-cell">What happened</th>
                  </tr>
                </thead>
                <tbody>
                  {log.map((step, i) => (
                    <tr key={`${step.step}-${step.column ?? ""}-${i}`} className="border-t border-gray-100 dark:border-gray-800">
                      <td className="px-3 py-1.5">{STEP_NAMES[step.step] ?? step.step.replaceAll("_", " ")}</td>
                      <td className="px-3 py-1.5 break-all">{step.column ?? "All"}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums">{fmt.format(step.rows_affected)}</td>
                      <td className="hidden px-3 py-1.5 text-gray-600 sm:table-cell dark:text-gray-400">{step.detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState>Nothing needed cleaning.</EmptyState>
          )}
        </div>
      </div>
    </Card>
  );
}
