import { formatCount, formatPercent, formatStat } from "@/lib/format";
import { distinctiveFeatures, type Segment } from "@/lib/insights";

import { EmptyState } from "../ui";

export function SegmentCards({ segments, skippedReason }: { segments: Segment[]; skippedReason?: string | null }) {
  if (!segments.length) return <EmptyState>{skippedReason ?? "No segments were found."}</EmptyState>;
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {segments.map((s) => (
        <article key={s.segment} className="flex flex-col gap-2 rounded-xl border border-gray-200 p-4 dark:border-gray-800">
          <p className="text-xs text-gray-500">Segment {s.segment + 1}</p>
          <h3 className="font-semibold">{s.label}</h3>
          <dl className="grid grid-cols-3 gap-2 text-sm">
            <div>
              <dt className="text-xs text-gray-500">Customers</dt>
              <dd className="tabular-nums">{formatCount(s.size)}</dd>
              <dd className="text-xs text-gray-500">{formatPercent(s.pct_of_base, 1)} of base</dd>
            </div>
            <div>
              <dt className="text-xs text-gray-500">Churn rate</dt>
              <dd className="tabular-nums">{formatPercent(s.churn_rate)}</dd>
            </div>
            <div>
              <dt className="text-xs text-gray-500">vs overall</dt>
              <dd className={`tabular-nums ${s.churn_lift != null && s.churn_lift > 1 ? "text-orange-700 dark:text-orange-300" : ""}`}>
                {s.churn_lift != null ? `${formatStat(s.churn_lift)}×` : "–"}
              </dd>
            </div>
          </dl>
          <ul className="text-xs text-gray-600 dark:text-gray-400">
            {distinctiveFeatures(s).map((f) => (
              <li key={f.feature}>
                {f.feature}: {formatStat(f.mean)} ({f.z > 0 ? "+" : ""}
                {formatStat(f.z, 1)} SD vs average)
              </li>
            ))}
          </ul>
        </article>
      ))}
    </div>
  );
}
