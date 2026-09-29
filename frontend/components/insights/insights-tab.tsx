import { orderByEvidence } from "@/lib/insights";
import type { ResultsPayload } from "@/lib/results";

import { Card, EmptyState } from "../ui";
import { CategoryChart } from "./category-chart";
import { CorrelationHeatmap } from "./correlation-heatmap";
import { InsightsList } from "./insights-list";
import { NumericComparison } from "./numeric-comparison";
import { SegmentCards } from "./segment-cards";
import { SurvivalChart } from "./survival-chart";

export function InsightsTab({ results }: { results: ResultsPayload }) {
  const eda = results.eda_results;
  if (!eda) return <EmptyState>Exploratory results are not available for this run.</EmptyState>;
  const tests = results.hypothesis_results?.tests;
  const categorical = orderByEvidence(Object.keys(eda.categorical ?? {}), tests);
  const numeric = orderByEvidence(Object.keys(eda.numeric ?? {}), tests);
  const overall = typeof eda.overview.churn_rate === "number" ? eda.overview.churn_rate : null;
  const segments = results.segments;
  return (
    <div className="flex flex-col gap-6">
      <Card title="Insights">
        <InsightsList insights={results.final_insights ?? []} />
      </Card>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Churn rate by category">
          <CategoryChart categorical={eda.categorical} columns={categorical} overallRate={overall} />
        </Card>
        <Card title="Churned vs retained">
          <NumericComparison numeric={eda.numeric} columns={numeric} />
        </Card>
      </div>
      <Card title="Customer segments">
        <SegmentCards segments={segments?.segments ?? []} skippedReason={segments?.reason} />
      </Card>
      <Card title="Survival curves">
        <SurvivalChart survival={results.survival_results} />
      </Card>
      <Card title="Correlations">
        {eda.correlation ? <CorrelationHeatmap correlation={eda.correlation} /> : <EmptyState>Not available.</EmptyState>}
      </Card>
    </div>
  );
}
