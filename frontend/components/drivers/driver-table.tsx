import { formatP, formatStat } from "@/lib/format";
import type { components } from "@/lib/api-types";

import { EmptyState } from "../ui";

type Row = components["schemas"]["DriverImpactRow"];

export function DriverTable({ rows }: { rows: Row[] }) {
  if (!rows.length) return <EmptyState>No driver summary for this run.</EmptyState>;
  return (
    <div className="max-h-[32rem] overflow-auto">
      <table className="w-full min-w-[40rem] text-left text-sm">
        <caption className="sr-only">Churn drivers compared across methods</caption>
        <thead className="sticky top-0 bg-white dark:bg-gray-950">
          <tr className="border-b border-gray-200 dark:border-gray-800">
            <th className="py-2 pr-3 font-medium">Driver</th>
            <th className="py-2 pr-3 text-right font-medium" title="Permutation importance rank">Rank</th>
            <th className="py-2 pr-3 text-right font-medium" title="Mean absolute SHAP value (log-odds)">Mean |SHAP|</th>
            <th className="py-2 pr-3 font-medium">Odds ratio (95% CI)</th>
            <th className="py-2 pr-3 font-medium">Test</th>
            <th className="py-2 text-right font-medium" title="Benjamini-Hochberg adjusted p-value">Adj. p</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.feature} className="border-b border-gray-100 align-top dark:border-gray-900">
              <td className="py-1.5 pr-3 font-medium break-all">{row.feature}</td>
              <td className="py-1.5 pr-3 text-right tabular-nums">{row.permutation_rank ?? "–"}</td>
              <td className="py-1.5 pr-3 text-right tabular-nums">{formatStat(row.mean_abs_shap)}</td>
              <td className="py-1.5 pr-3">
                {row.odds_ratio != null ? (
                  <>
                    <span className="tabular-nums">
                      {formatStat(row.odds_ratio)} ({formatStat(row.or_ci_lower)} to {formatStat(row.or_ci_upper)})
                    </span>
                    {row.or_label ? <span className="block text-xs text-gray-500">{row.or_label}</span> : null}
                  </>
                ) : (
                  "–"
                )}
              </td>
              <td className="py-1.5 pr-3 text-gray-600 dark:text-gray-400">{row.test_name ?? "–"}</td>
              <td className="py-1.5 text-right tabular-nums">
                {formatP(row.p_adjusted)}
                {row.significant === false ? <span className="block text-xs text-gray-500">not significant</span> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
