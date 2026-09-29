import { formatCount, formatP, formatPercent, formatStat } from "@/lib/format";
import { conclusionFor, significantAt, type HypothesisTest } from "@/lib/hypothesis";
import type { components } from "@/lib/api-types";

import { Tex } from "./tex";

type Table = components["schemas"]["LabelledTable"];

function CountTable({ title, table, digits }: { title: string; table: Table; digits: number }) {
  return (
    <div className="min-w-0">
      <p className="mb-1 text-xs font-medium text-gray-500">{title}</p>
      <div className="overflow-x-auto">
        <table className="text-sm">
          <thead>
            <tr>
              <th />
              {table.columns.map((c) => (
                <th key={c} className="px-2 py-1 text-right font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, i) => (
              <tr key={row} className="border-t border-gray-100 dark:border-gray-800">
                <td className="py-1 pr-3 break-all">{row}</td>
                {table.values[i].map((v, j) => (
                  <td key={j} className="px-2 py-1 text-right tabular-nums">
                    {digits ? formatStat(v, digits) : formatCount(v)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Inputs({ test }: { test: HypothesisTest }) {
  const { observed, expected, groups, churn_rate_by_level: rates } = test.inputs;
  if (test.kind === "categorical" && observed) {
    return (
      <div className="grid gap-4 sm:grid-cols-2">
        <CountTable title="Observed counts (O)" table={observed} digits={0} />
        {expected ? <CountTable title="Expected counts if H0 is true (E)" table={expected} digits={1} /> : null}
        {rates ? (
          <p className="text-xs text-gray-500 sm:col-span-2">
            Churn rate by level:{" "}
            {Object.entries(rates)
              .map(([level, rate]) => `${level} ${formatPercent(rate)}`)
              .join(" · ")}
          </p>
        ) : null}
      </div>
    );
  }
  if (groups) {
    return (
      <div className="overflow-x-auto">
        <table className="text-sm">
          <thead>
            <tr>
              <th className="pr-3 text-left font-medium">Group</th>
              <th className="px-2 text-right font-medium">n</th>
              <th className="px-2 text-right font-medium">Mean</th>
              <th className="px-2 text-right font-medium">Median</th>
              <th className="px-2 text-right font-medium">SD</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(groups).map(([name, g]) => (
              <tr key={name} className="border-t border-gray-100 dark:border-gray-800">
                <td className="py-1 pr-3 capitalize">{name}</td>
                <td className="px-2 text-right tabular-nums">{formatCount(g.n)}</td>
                <td className="px-2 text-right tabular-nums">{formatStat(g.mean)}</td>
                <td className="px-2 text-right tabular-nums">{formatStat(g.median)}</td>
                <td className="px-2 text-right tabular-nums">{formatStat(g.sd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  return null;
}

export function TestDetail({ test, alpha, serverAlpha }: { test: HypothesisTest; alpha: number; serverAlpha: number }) {
  return (
    <div className="flex flex-col gap-4 text-sm">
      <div className="grid gap-2 sm:grid-cols-2">
        <p>
          <span className="font-medium">H₀:</span> {test.h0}
        </p>
        <p>
          <span className="font-medium">H₁:</span> {test.h1}
        </p>
      </div>
      <p>
        <span className="font-medium">Why {test.test_name}:</span> {test.why}
      </p>

      <div>
        <p className="mb-1 font-medium">Assumption checks</p>
        <ul className="flex flex-col gap-1">
          {(test.assumptions ?? []).map((a) => (
            <li key={a.name} className="flex gap-2">
              <span aria-hidden className={a.result ? "text-green-600" : "text-orange-600"}>
                {a.result ? "✓" : "✕"}
              </span>
              <span>
                {a.name}: <span className="text-gray-500">{a.detail}</span>
                <span className="sr-only">{a.result ? " (met)" : " (not met)"}</span>
              </span>
            </li>
          ))}
        </ul>
      </div>

      <Inputs test={test} />

      <div>
        <p className="mb-1 font-medium">Calculation</p>
        <ol className="flex flex-col gap-3">
          {(test.steps ?? []).map((step, i) => (
            <li key={`${step.label}-${i}`} className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
              <p className="text-xs font-medium text-gray-500">
                {i + 1}. {step.label}
              </p>
              <Tex latex={step.formula} block />
              <Tex latex={step.substituted} block />
            </li>
          ))}
        </ol>
      </div>

      <p className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
        <span className="font-medium">Conclusion: </span>
        {conclusionFor(test, alpha, serverAlpha)}
      </p>
      <p className="text-xs text-gray-500">
        Raw p = {formatP(test.p_value)}; adjusted p = {formatP(test.p_adjusted)} ({significantAt(test, alpha) ? "below" : "not below"}{" "}
        α = {alpha}). A significant result shows association, not cause.
      </p>
    </div>
  );
}
