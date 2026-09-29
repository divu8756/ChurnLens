import type { Insight } from "@/lib/results";

import { SignificanceBadge } from "../overview/top-insights";
import { EmptyState } from "../ui";

export function InsightsList({ insights }: { insights: Insight[] }) {
  if (!insights.length) return <EmptyState>No verified insights for this run.</EmptyState>;
  return (
    <ol className="flex flex-col gap-4">
      {insights.slice(0, 10).map((insight) => (
        <li
          key={insight.id}
          className={`flex flex-col gap-1 border-l-4 pl-3 ${
            insight.significant ? "border-green-600" : "border-dashed border-gray-400 opacity-80"
          }`}
        >
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium">{insight.title}</h3>
            <SignificanceBadge significant={insight.significant} />
          </div>
          <p className="text-sm text-gray-700 dark:text-gray-300">{insight.text}</p>
          {!insight.significant ? (
            <p className="text-xs text-gray-500">Not statistically significant: treat as a lead to check, not a finding.</p>
          ) : null}
          {insight.causality_note ? <p className="text-xs text-gray-500">{insight.causality_note}</p> : null}
        </li>
      ))}
    </ol>
  );
}
