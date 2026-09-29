import type { ReactNode } from "react";

import { EFFORT_LABELS, impactText } from "@/lib/recommendations";
import type { Recommendation } from "@/lib/results";

const EFFORT_STYLES: Record<Recommendation["effort"], string> = {
  low: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  medium: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-100",
  high: "bg-orange-100 text-orange-900 dark:bg-orange-950 dark:text-orange-100",
};

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-gray-500">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

export function RecommendationCard({ rec, revenueColumn }: { rec: Recommendation; revenueColumn?: string | null }) {
  return (
    <article className="flex flex-col gap-3 rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded-full bg-blue-100 px-2 py-0.5 font-medium text-blue-800 dark:bg-blue-950 dark:text-blue-200">
          Priority {rec.priority}
        </span>
        <span className={`rounded-full px-2 py-0.5 font-medium ${EFFORT_STYLES[rec.effort]}`}>{EFFORT_LABELS[rec.effort]}</span>
      </div>
      <h3 className="text-base font-semibold">{rec.action}</h3>
      <dl className="grid gap-3 sm:grid-cols-2">
        <Field label="Problem">{rec.problem}</Field>
        <Field label="Who">{rec.target_segment}</Field>
        <Field label="Customers affected">
          <span className="tabular-nums">{rec.customers_affected.display}</span>
        </Field>
        <Field label="Estimated impact">
          <span className="tabular-nums">{impactText(rec.impact, revenueColumn)}</span>
          <span className="mt-0.5 block text-xs text-gray-500">Assumption: {rec.impact.assumption}</span>
        </Field>
      </dl>
    </article>
  );
}
