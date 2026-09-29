"use client";

import { Fragment, useState } from "react";

import type { PredictionRow } from "@/lib/api";
import { formatPercent } from "@/lib/format";
import { formatOfferValue, type ValueUnit } from "@/lib/offers";
import { RISK_COLOURS } from "@/lib/palette";

import { OfferPanel } from "./offer-panel";
import { ReasonChips } from "./reason-chips";

/** Offer columns appear only when a next-best-offer analysis ran (valueUnit set). */
export function PredictionsTable({
  rows,
  sessionId,
  valueUnit = null,
}: {
  rows: PredictionRow[];
  sessionId?: string;
  valueUnit?: ValueUnit | null;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const offers = valueUnit != null && sessionId != null;
  const columns = offers ? 7 : 5;
  return (
    <div className="overflow-x-auto">
      <table className={`w-full text-left text-sm ${offers ? "min-w-[58rem]" : "min-w-[40rem]"}`}>
        <caption className="sr-only">Customers by predicted churn risk</caption>
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-800">
            <th className="py-2 pr-3 font-medium">Customer</th>
            <th className="py-2 pr-3 text-right font-medium">Churn probability</th>
            <th className="py-2 pr-3 font-medium">Band</th>
            <th className="py-2 pr-3 font-medium">Churned?</th>
            <th className="py-2 pr-3 font-medium">Top reasons</th>
            {offers ? (
              <>
                <th className="py-2 pr-3 font-medium">Next best offer</th>
                <th className="py-2 text-right font-medium">Expected value</th>
              </>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const isOpen = open === row.customer_id;
            return (
              <Fragment key={row.customer_id}>
                <tr className="border-b border-gray-100 align-top dark:border-gray-900">
                  <td className="py-2 pr-3 font-mono text-xs break-all">{row.customer_id}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{formatPercent(row.churn_probability, 1)}</td>
                  <td className="py-2 pr-3">
                    <span className="inline-flex items-center gap-1.5">
                      <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: RISK_COLOURS[row.risk_band] }} aria-hidden />
                      {row.risk_band}
                    </span>
                  </td>
                  <td className="py-2 pr-3">{row.actual_churn ? "Yes" : "No"}</td>
                  <td className="py-2 pr-3">
                    <ReasonChips reasons={[row.reason_1, row.reason_2, row.reason_3]} />
                  </td>
                  {offers ? (
                    <>
                      <td className="py-2 pr-3">
                        {row.best_offer ? (
                          <button
                            type="button"
                            aria-expanded={isOpen}
                            onClick={() => setOpen(isOpen ? null : row.customer_id)}
                            className="text-left text-blue-700 hover:underline dark:text-blue-300"
                          >
                            <span aria-hidden>{isOpen ? "▾ " : "▸ "}</span>
                            {row.best_offer}
                          </button>
                        ) : (
                          <span className="text-gray-500" title="Only Medium and High risk customers are scored">
                            –
                          </span>
                        )}
                      </td>
                      <td className="py-2 text-right tabular-nums">
                        {row.best_offer ? formatOfferValue(row.expected_value, valueUnit) : "–"}
                      </td>
                    </>
                  ) : null}
                </tr>
                {offers && isOpen ? (
                  <tr className="border-b border-gray-100 dark:border-gray-900">
                    <td colSpan={columns} className="py-3">
                      <OfferPanel sessionId={sessionId} customerId={row.customer_id} />
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
