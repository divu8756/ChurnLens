import type { ResultsPayload } from "@/lib/results";

import { Card } from "../ui";
import { KpiCards } from "./kpi-cards";
import { RiskBandChart } from "./risk-band-chart";
import { TopInsights } from "./top-insights";
import { TopRecommendations } from "./top-recommendations";
import { ValidatorBadge } from "./validator-badge";

export function OverviewTab({ results }: { results: ResultsPayload }) {
  const metrics = results.model_metrics ?? null;
  return (
    <div className="flex flex-col gap-6">
      <KpiCards impact={results.impact_estimates ?? null} metrics={metrics} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Top insights" actions={<ValidatorBadge report={results.validation_report ?? null} />}>
          <TopInsights insights={results.final_insights ?? []} />
        </Card>
        <Card title="Top recommendations">
          <TopRecommendations recommendations={results.final_recommendations ?? []} />
        </Card>
      </div>
      <Card title="Churn risk">
        <RiskBandChart bands={metrics?.risk_bands ?? null} />
      </Card>
    </div>
  );
}
