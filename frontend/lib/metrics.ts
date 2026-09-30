// Display helpers for the Model Performance, Business Impact and Agent Health tabs.
// Every number comes from the API; these only pick values and build chart traces.
import type { Trace } from "plotly.js-basic-dist-min";

import type { BusinessAssumptions, ScoreSet } from "./api";
import { PALETTE } from "./palette";

export const KPI_HELP = {
  roc_auc: "How well the model ranks churners above stayers: 0.5 is a coin toss, 1 is perfect.",
  pr_auc: "Average precision across all cut-offs; judge it against the churn rate, which is what random guessing scores.",
  precision_top: "Of the 10% of customers we flag, this share actually churned.",
  recall_top: "Of all customers who churned, this share was in the 10% we flag.",
  brier: "Average squared gap between the predicted probability and what happened (lower is better).",
  revenue_at_risk: "Churn probability x monthly revenue x months remaining, summed over customers.",
  expected_saving: "Estimated net saving if each customer gets their best offer (after offer costs).",
  customers_with_offer: "Customers whose best offer has a positive expected saving.",
  overall_roi: "Net expected saving per unit of expected offer cost.",
} as const;

export function rocTraces(scores: ScoreSet): Trace[] {
  const curve = scores.roc_curve;
  if (!curve) return [];
  return [
    { type: "scatter", mode: "lines", name: "Model", x: curve.fpr, y: curve.tpr, line: { color: PALETTE.blue, width: 2 } },
    { type: "scatter", mode: "lines", name: "Random", x: [0, 1], y: [0, 1], line: { color: PALETTE.grey, dash: "dash" } },
  ];
}

export function prTraces(scores: ScoreSet): Trace[] {
  const curve = scores.pr_curve;
  if (!curve) return [];
  return [
    { type: "scatter", mode: "lines", name: "Model", x: curve.recall, y: curve.precision, line: { color: PALETTE.blue, width: 2 } },
    {
      type: "scatter",
      mode: "lines",
      name: "Random (churn rate)",
      x: [0, 1],
      y: [scores.churn_rate, scores.churn_rate],
      line: { color: PALETTE.grey, dash: "dash" },
    },
  ];
}

export function liftTraces(scores: ScoreSet): Trace[] {
  const labels = scores.deciles.map((d) => `D${d.decile}`);
  return [
    { type: "bar", name: "Lift", x: labels, y: scores.deciles.map((d) => d.lift ?? null), marker: { color: PALETTE.blue } },
    {
      type: "scatter",
      mode: "lines+markers",
      name: "Cumulative gain",
      x: labels,
      y: scores.deciles.map((d) => d.cumulative_gain ?? null),
      yaxis: "y2",
      line: { color: PALETTE.orange },
    },
  ];
}

export function calibrationTraces(raw: ScoreSet, calibrated: ScoreSet): Trace[] {
  const points = (s: ScoreSet) => s.calibration.filter((b) => b.n > 0);
  const series = (s: ScoreSet, name: string, colour: string): Trace => ({
    type: "scatter",
    mode: "lines+markers",
    name,
    x: points(s).map((b) => b.mean_predicted ?? null),
    y: points(s).map((b) => b.observed_rate ?? null),
    text: points(s).map((b) => `${b.n} customers`),
    hovertemplate: "predicted %{x:.2f}, observed %{y:.2f} (%{text})<extra></extra>",
    line: { color: colour },
  });
  return [
    { type: "scatter", mode: "lines", name: "Perfect", x: [0, 1], y: [0, 1], line: { color: PALETTE.grey, dash: "dash" } },
    series(raw, "Raw model", PALETTE.orange),
    series(calibrated, "Calibrated", PALETTE.blue),
  ];
}

/** True when the user changed anything from the defaults (drives the stale-explanation banner). */
export function isEdited(a: BusinessAssumptions): boolean {
  return (
    a.months_remaining != null ||
    a.relative_lift != null ||
    a.power != null ||
    a.alpha != null ||
    Object.values(a.offers ?? {}).some((o) => o.acceptance != null || o.save_rate != null || o.cost != null)
  );
}

/** Same assumptions (order-insensitive), so an explanation still matches the numbers. */
export function sameAssumptions(a: BusinessAssumptions, b: BusinessAssumptions): boolean {
  const canonical = (x: BusinessAssumptions) =>
    JSON.stringify(x, (_, v) => (v && typeof v === "object" && !Array.isArray(v) ? Object.fromEntries(Object.entries(v).sort()) : v));
  return canonical(a) === canonical(b);
}

export const SOURCE_STYLE: Record<string, string> = {
  default: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  user: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  data: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
};
