import { formatCount, formatMoney, formatPercent, formatStat } from "@/lib/format";
import type { ImpactEstimates, ModelMetrics } from "@/lib/results";

type Kpi = { label: string; value: string; note: string; help: string };

function KpiCard({ kpi }: { kpi: Kpi }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950" title={kpi.help}>
      <p className="text-xs font-medium text-gray-500">{kpi.label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{kpi.value}</p>
      <p className="mt-1 text-xs text-gray-500">{kpi.note}</p>
    </div>
  );
}

export function KpiCards({ impact, metrics }: { impact: ImpactEstimates | null; metrics: ModelMetrics | null }) {
  const overall = impact?.overall;
  const bands = metrics?.risk_bands;
  const high = bands?.band_counts.High;
  const kpis: Kpi[] = [
    {
      label: "Customers",
      value: formatCount(overall?.customers),
      note: `${formatCount(overall?.churners)} churned`,
      help: "Customers analysed after cleaning (duplicates removed).",
    },
    {
      label: "Churn rate",
      value: formatPercent(overall?.churn_rate),
      note: "share of customers who left",
      help: "Churned customers divided by all customers in the data.",
    },
    {
      label: "High-risk customers",
      value: formatCount(high),
      note: bands ? `risk score ≥ ${formatPercent(bands.thresholds.high, 0)}` : "model not available",
      help: "Customers whose predicted churn probability is at or above the high-risk threshold.",
    },
    {
      label: "Monthly revenue at risk",
      value: formatMoney(overall?.monthly_revenue_at_risk),
      note: impact?.revenue_column ? `sum of ${impact.revenue_column} of churned customers` : "no revenue column chosen",
      help: impact?.revenue_note ?? "Monthly revenue of the customers who churned.",
    },
    {
      label: "Model ROC-AUC",
      value: formatStat(metrics?.test.roc_auc),
      note: metrics ? `${metrics.chosen_model_name}, held-out test set` : "model not available",
      help: "How well the model ranks churners above non-churners on data it never saw: 0.5 is chance, 1 is perfect.",
    },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {kpis.map((kpi) => (
        <KpiCard key={kpi.label} kpi={kpi} />
      ))}
    </div>
  );
}
