import type { ResultsPayload } from "@/lib/results";

import { Alert, Card, EmptyState } from "../ui";
import { ConfusionMatrix } from "./confusion-matrix";
import { DriverTable } from "./driver-table";
import { ImportanceChart } from "./importance-chart";
import { MetricsTable } from "./metrics-table";
import { OddsForest } from "./odds-forest";
import { RocCurve } from "./roc-curve";
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
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Model performance">
          <MetricsTable metrics={metrics} />
        </Card>
        <Card title="Confusion matrix">
          {metrics.test.confusion_matrix ? (
            <ConfusionMatrix matrix={metrics.test.confusion_matrix} />
          ) : (
            <EmptyState>Not available.</EmptyState>
          )}
        </Card>
      </div>
      <Card title="ROC curve">
        {metrics.test.roc_curve ? (
          <RocCurve curve={metrics.test.roc_curve} auc={metrics.test.roc_auc} />
        ) : (
          <EmptyState>Not available.</EmptyState>
        )}
      </Card>
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
