// Experiments tab display helpers. Every number comes from the API; these only pick,
// label and position values (the browser never computes metrics).
import type { Analysis, Experiment, ExperimentListItem, SegmentFilter } from "./api";
import { formatPercent } from "./format";

export type Status = ExperimentListItem["status"];
export type Verdict = Analysis["decision_helper"]["verdict"];
type Tone = "grey" | "blue" | "amber" | "green" | "red";

export const TONE_CLASSES: Record<Tone, string> = {
  grey: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  blue: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  amber: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
  green: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  red: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
};

export const STATUS: Record<string, { label: string; tone: Tone; next: string }> = {
  draft: { label: "Draft", tone: "grey", next: "Review the design, then approve it." },
  approved: { label: "Approved", tone: "blue", next: "Assign customers to treatment and control." },
  running: { label: "Running", tone: "amber", next: "Send the offer to the treatment group, then upload the results." },
  results_uploaded: { label: "Results in", tone: "blue", next: "Read the analysis and record a decision." },
  decided: { label: "Decided", tone: "green", next: "Done. The measured effect now feeds next best offer." },
};

export function statusInfo(status: string) {
  return STATUS[status] ?? { label: status, tone: "grey" as Tone, next: "" };
}

export const VERDICT: Record<Verdict, { label: string; tone: Tone }> = {
  ship: { label: "Suggests: ship", tone: "green" },
  dont_ship: { label: "Suggests: don't ship", tone: "red" },
  inconclusive: { label: "Inconclusive", tone: "amber" },
  untrustworthy: { label: "Not trustworthy (SRM)", tone: "red" },
};

export const DECISION_LABELS: Record<string, string> = { ship: "Ship", dont_ship: "Don't ship", extend: "Extend" };

const OPS: Record<SegmentFilter["op"], string> = {
  eq: "=",
  ne: "≠",
  in: "in",
  not_in: "not in",
  gt: ">",
  gte: "≥",
  lt: "<",
  lte: "≤",
};

export function filterText(f: SegmentFilter): string {
  const value = Array.isArray(f.value) ? f.value.join(", ") : String(f.value);
  return `${f.column} ${OPS[f.op]} ${value}`;
}

export function segmentText(filters: SegmentFilter[]): string {
  return filters.length ? filters.map(filterText).join(" and ") : "All customers";
}

export type ForestRow = { label: string; value: number; low: number; high: number; primary: boolean; note?: string };

/** Overall ITT difference first, then the pre-registered segments (exploratory). */
export function forestRows(analysis: Analysis): ForestRow[] {
  const d = analysis.itt.difference;
  const rows: ForestRow[] = d ? [{ label: "All assigned (ITT)", value: d.value, low: d.ci_low, high: d.ci_high, primary: true }] : [];
  for (const [name, seg] of Object.entries(analysis.segments?.items ?? {})) {
    if (!seg.difference) continue;
    rows.push({
      label: name,
      value: seg.difference.value,
      low: seg.difference.ci_low,
      high: seg.difference.ci_high,
      primary: false,
      note: seg.p_adjusted != null ? `adj. p ${seg.p_adjusted < 0.001 ? "< 0.001" : seg.p_adjusted.toFixed(3)}` : undefined,
    });
  }
  return rows;
}

/** Axis range that always shows 0 (no effect), padded by 10%. */
export function axisDomain(values: number[]): [number, number] {
  const lo = Math.min(0, ...values);
  const hi = Math.max(0, ...values);
  const pad = (hi - lo || 0.01) * 0.1;
  return [lo - pad, hi + pad];
}

/** Position of value within [lo, hi] as a percentage (for SVG / CSS placement). */
export function position(value: number, [lo, hi]: [number, number]): number {
  return hi === lo ? 50 : ((value - lo) / (hi - lo)) * 100;
}

export type HealthItem = { label: string; ok: boolean; detail: string };

/** SRM, balance and guardrail checks in one strip. */
export function healthItems(exp: Experiment): HealthItem[] {
  const items: HealthItem[] = [];
  const a = exp.analysis;
  if (a) {
    items.push({
      label: "Sample ratio",
      ok: !a.srm.failed,
      detail: a.srm.failed
        ? `Split differs from plan (p ${a.srm.p_value < 0.001 ? "< 0.001" : a.srm.p_value.toFixed(3)})`
        : `Control ${formatPercent(a.srm.observed_control_share, 1)} vs planned ${formatPercent(a.srm.planned_control_share, 0)}`,
    });
  }
  const balance = exp.assignment_summary?.balance;
  if (balance) {
    items.push({
      label: "Balance",
      ok: balance.balanced,
      detail: balance.balanced ? "All |SMD| ≤ 0.1" : `Imbalanced: ${balance.flagged.join(", ")}`,
    });
  }
  for (const [name, g] of Object.entries(a?.guardrails ?? {})) {
    items.push({
      label: name === "arpu" ? "ARPU guardrail" : "Complaints guardrail",
      ok: !g.breached,
      detail: g.breached ? "Breached" : "Not breached",
    });
  }
  return items;
}
