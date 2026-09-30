import type { ResultsPayload } from "@/lib/results";

import { Alert, Card, EmptyState } from "../ui";
import { DriverTable } from "./driver-table";
import { ImportanceChart } from "./importance-chart";
import { OddsForest } from "./odds-forest";
import { ShapSummary } from "./shap-summary";

export function DriversTab({ results }: { results: ResultsPayload }) {
  const metrics = results.model_metrics;
  if (!metrics) return <EmptyState>The churn model did not run, so there are no drivers to show.</EmptyState>;
  const importance = results.feature_importance;
  const shap = results.shap_summary;
  const odds = results.odds_ratios;
  return (
    <div className="flex flex-col gap-6">
      {metrics.leakage_warnings?.length ? (
        <Alert tone="warning" title="Possible leakage">
          These columns track the target very closely and may be recorded after churn:{" "}
          {metrics.leakage_warnings.map((w) => w.column).join(", ")}.
        </Alert>
      ) : null}
      <p className="text-sm text-gray-600 dark:text-gray-400">
        What drives churn, by three methods. How well the model predicts is on the Model Performance tab.
      </p>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Feature importance">
          <ImportanceChart items={importance?.features ?? []} method={importance?.method} />
        </Card>
        <Card title="SHAP summary">
          {shap?.error ? <Alert tone="warning" title="SHAP could not be computed">{shap.error}</Alert> : null}
          <ShapSummary features={shap?.beeswarm ?? []} scale={shap?.scale} />
        </Card>
      </div>
      <Card title="Odds ratios">
        {odds?.error ? <Alert tone="warning" title="Odds ratios could not be computed">{odds.error}</Alert> : null}
        <OddsForest terms={odds?.terms ?? []} method={odds?.method} />
        {odds?.dropped?.length ? (
          <details className="mt-2 text-xs text-gray-500">
            <summary className="cursor-pointer">{odds.dropped.length} terms left out of the regression</summary>
            <ul className="mt-1 list-disc pl-5">
              {odds.dropped.map((d) => (
                <li key={d.term}>
                  {d.term}: {d.reason}
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </Card>
      <Card title="Driver summary">
        <p className="mb-3 text-xs text-gray-500">
          Each driver across the three methods: permutation rank, SHAP strength, odds ratio, and the hypothesis test
          with its multiple-testing adjusted p-value. Associations, not proof of cause.
        </p>
        <DriverTable rows={importance?.driver_impact ?? []} />
      </Card>
    </div>
  );
}
