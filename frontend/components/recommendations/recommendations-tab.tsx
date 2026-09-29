import { groupRecommendations } from "@/lib/recommendations";
import type { ResultsPayload } from "@/lib/results";

import { ValidatorBadge } from "../overview/validator-badge";
import { Card, EmptyState } from "../ui";
import { ReachChart } from "./reach-chart";
import { RecommendationCard } from "./recommendation-card";

export function RecommendationsTab({ results }: { results: ResultsPayload }) {
  const recommendations = results.final_recommendations ?? [];
  if (!recommendations.length) {
    return (
      <EmptyState>
        No recommendations passed the number checks for this run. The statistics in the other tabs are still complete.
      </EmptyState>
    );
  }
  const revenueColumn = results.impact_estimates?.revenue_column;
  return (
    <div className="flex flex-col gap-6">
      <Card title="Recommendations" actions={<ValidatorBadge report={results.validation_report ?? null} />}>
        <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
          Written by AI from the computed results; every number was checked against them. Impacts are what-if scenarios
          based on observed churn, not guaranteed or causal.
        </p>
        <ReachChart recommendations={recommendations} />
      </Card>
      {groupRecommendations(recommendations).map((group) => (
        <section key={group.id} aria-labelledby={`group-${group.id}`} className="flex flex-col gap-3">
          <div>
            <h2 id={`group-${group.id}`} className="text-lg font-semibold">
              {group.label} <span className="text-sm font-normal text-gray-500">({group.items.length})</span>
            </h2>
            <p className="text-sm text-gray-500">{group.blurb}</p>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            {group.items.map((rec) => (
              <RecommendationCard key={rec.id} rec={rec} revenueColumn={revenueColumn} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
