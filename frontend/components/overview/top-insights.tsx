import type { Insight } from "@/lib/results";

import { EmptyState } from "../ui";

export function SignificanceBadge({ significant }: { significant: boolean }) {
  return significant ? (
    <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-950 dark:text-green-200">
      Statistically significant
    </span>
  ) : (
    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-300">
      Not significant
    </span>
  );
}

export function TopInsights({ insights }: { insights: Insight[] }) {
  if (!insights.length) return <EmptyState>No verified insights for this run.</EmptyState>;
  return (
    <ol className="flex flex-col gap-4">
      {insights.slice(0, 3).map((insight) => (
        <li key={insight.id} className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium">{insight.title}</h3>
            <SignificanceBadge significant={insight.significant} />
          </div>
          <p className="text-sm text-gray-700 dark:text-gray-300">{insight.text}</p>
          {insight.causality_note ? <p className="text-xs text-gray-500">{insight.causality_note}</p> : null}
        </li>
      ))}
    </ol>
  );
}
