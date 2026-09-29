import type { PredictionRow } from "@/lib/api";
import { formatPercent } from "@/lib/format";
import { RISK_COLOURS } from "@/lib/palette";

import { ReasonChips } from "./reason-chips";

export function PredictionsTable({ rows }: { rows: PredictionRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[40rem] text-left text-sm">
        <caption className="sr-only">Customers by predicted churn risk</caption>
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-800">
            <th className="py-2 pr-3 font-medium">Customer</th>
            <th className="py-2 pr-3 text-right font-medium">Churn probability</th>
            <th className="py-2 pr-3 font-medium">Band</th>
            <th className="py-2 pr-3 font-medium">Churned?</th>
            <th className="py-2 font-medium">Top reasons</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.customer_id} className="border-b border-gray-100 align-top dark:border-gray-900">
              <td className="py-2 pr-3 font-mono text-xs break-all">{row.customer_id}</td>
              <td className="py-2 pr-3 text-right tabular-nums">{formatPercent(row.churn_probability, 1)}</td>
              <td className="py-2 pr-3">
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: RISK_COLOURS[row.risk_band] }} aria-hidden />
                  {row.risk_band}
                </span>
              </td>
              <td className="py-2 pr-3">{row.actual_churn ? "Yes" : "No"}</td>
              <td className="py-2">
                <ReasonChips reasons={[row.reason_1, row.reason_2, row.reason_3]} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
