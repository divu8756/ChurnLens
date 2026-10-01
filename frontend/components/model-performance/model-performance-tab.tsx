"use client";

import { useEffect, useState } from "react";

import { ApiError, getModelMetrics, type ModelMetricsV2 } from "@/lib/api";
import { formatCount, formatPercent, formatStat } from "@/lib/format";
import { calibrationTraces, KPI_HELP, liftTraces, prTraces, rocTraces } from "@/lib/metrics";
import type { ResultsPayload } from "@/lib/results";

import { PlotlyChart } from "../charts/plotly-chart";
import { ConfusionMatrix } from "../drivers/confusion-matrix";
import { MetricsTable } from "../drivers/metrics-table";
import { KpiTile } from "../metrics/kpi-tile";
import { Alert, Card, EmptyState, Spinner } from "../ui";

const AXIS = { range: [0, 1], fixedrange: true };

export function ModelPerformanceTab({ results, sessionId }: { results: ResultsPayload; sessionId: string }) {
  const [metrics, setMetrics] = useState<ModelMetricsV2 | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getModelMetrics(sessionId, controller.signal)
      .then(setMetrics)
      .catch((e: unknown) => {
        if (!controller.signal.aborted) setError(e instanceof ApiError ? e.message : "Could not load the model metrics.");
      });
    return () => controller.abort();
  }, [sessionId]);

  const legacy = results.model_metrics;
  if (error) return <Alert tone="error" title={error} />;
  if (!metrics) return <Spinner label="Loading model metrics..." />;
  const cal = metrics.calibrated;
  const raw = metrics.raw;

  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm text-gray-600 dark:text-gray-400">
        {metrics.chosen_model_name ?? "The model"} on {formatCount(metrics.n_test)} test customers it never saw (trained
        on {formatCount(metrics.n_train)}). {metrics.calibration_note}
      </p>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <KpiTile label="ROC-AUC" value={formatStat(cal.roc_auc, 3)} help={KPI_HELP.roc_auc} />
        <KpiTile label="PR-AUC" value={formatStat(cal.pr_auc, 3)} note={`churn rate ${formatPercent(cal.churn_rate, 1)}`} help={KPI_HELP.pr_auc} />
        <KpiTile
          label="Precision @ top 10%"
          value={formatPercent(cal.top_10pct.precision, 1)}
          note={`${formatCount(cal.top_10pct.churners_in_top)} of ${formatCount(cal.top_10pct.k)}`}
          help={KPI_HELP.precision_top}
        />
        <KpiTile label="Recall @ top 10%" value={formatPercent(cal.top_10pct.recall, 1)} help={KPI_HELP.recall_top} />
        <KpiTile
          label="Brier score"
          value={formatStat(cal.brier, 3)}
          note={`raw model ${formatStat(raw.brier, 3)}`}
          help={KPI_HELP.brier}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="ROC curve">
          {cal.roc_curve ? (
            <PlotlyChart
              label={`ROC curve, area ${formatStat(cal.roc_auc, 3)}`}
              data={rocTraces(cal)}
              layout={{ xaxis: { ...AXIS, title: { text: "False positive rate" } }, yaxis: { ...AXIS, title: { text: "True positive rate" } } }}
            />
          ) : (
            <EmptyState>Not available (the test split has one class).</EmptyState>
          )}
        </Card>
        <Card title="Precision-recall curve">
          {cal.pr_curve ? (
            <PlotlyChart
              label={`Precision-recall curve, average precision ${formatStat(cal.pr_auc, 3)}`}
              data={prTraces(cal)}
              layout={{ xaxis: { ...AXIS, title: { text: "Recall" } }, yaxis: { ...AXIS, title: { text: "Precision" } } }}
            />
          ) : (
            <EmptyState>Not available.</EmptyState>
          )}
        </Card>
      </div>

      <Card title="Lift by decile">
        <PlotlyChart
          label="Lift by risk decile with cumulative gains"
          data={liftTraces(cal)}
          layout={{
            xaxis: { title: { text: "Risk decile (D1 = highest scores)" } },
            yaxis: { title: { text: "Lift (x overall churn rate)" } },
            yaxis2: { title: { text: "Cumulative share of churners" }, overlaying: "y", side: "right", range: [0, 1], showgrid: false },
            margin: { t: 16, r: 64, b: 48, l: 56 },
          }}
        />
        <p className="mt-1 text-xs text-gray-500">{metrics.definitions?.lift}</p>
      </Card>

      <Card title="Calibration">
        <PlotlyChart
          label="Calibration: predicted probability against observed churn rate, raw and calibrated"
          data={calibrationTraces(raw, cal)}
          layout={{
            xaxis: { ...AXIS, title: { text: "Predicted probability" } },
            yaxis: { ...AXIS, title: { text: "Observed churn rate" } },
          }}
        />
        <p className="mt-1 text-xs text-gray-500">
          Points on the dashed line mean the probabilities can be taken at face value. Money metrics use the calibrated
          probabilities ({metrics.calibration_method}).
        </p>
      </Card>

      {legacy ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card title="Model performance">
            <MetricsTable metrics={legacy} />
          </Card>
          <Card title="Confusion matrix">
            {legacy.test.confusion_matrix ? <ConfusionMatrix matrix={legacy.test.confusion_matrix} /> : <EmptyState>Not available.</EmptyState>}
          </Card>
        </div>
      ) : null}
    </div>
  );
}
