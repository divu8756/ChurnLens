import { byPriority, type Recommendation } from "@/lib/results";

import { EmptyState } from "../ui";

export const GROUP_LABELS: Record<Recommendation["group"], string> = {
  quick_win: "Quick win",
  medium_term: "Medium-term",
  strategic: "Strategic",
};

export function TopRecommendations({ recommendations }: { recommendations: Recommendation[] }) {
  if (!recommendations.length) return <EmptyState>No verified recommendations for this run.</EmptyState>;
  return (
    <ol className="flex flex-col gap-4">
      {byPriority(recommendations)
        .slice(0, 3)
        .map((rec) => (
          <li key={rec.id} className="flex flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
              <span className="font-medium text-gray-700 dark:text-gray-300">Priority {rec.priority}</span>
              <span>·</span>
              <span>{GROUP_LABELS[rec.group]}</span>
              <span>·</span>
              <span>{rec.effort} effort</span>
            </div>
            <h3 className="font-medium">{rec.action}</h3>
            <p className="text-sm text-gray-700 dark:text-gray-300">
              {rec.target_segment}: {rec.customers_affected.display} customers.
            </p>
          </li>
        ))}
    </ol>
  );
}
