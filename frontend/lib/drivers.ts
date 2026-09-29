// Chart geometry for the Churn Drivers tab. Only layout (ordering, whisker lengths, jitter,
// colour positions); every number shown comes from the API unchanged.
import type { components } from "./api-types";

type S = components["schemas"];
export type OddsRatioTerm = S["OddsRatioTerm"];
export type ShapFeature = S["ShapFeature"];
export type PermutationItem = S["PermutationItem"];

export const MAX_BARS = 15;
export const MAX_FOREST_ROWS = 15;

export type ForestRow = {
  label: string;
  odds_ratio: number;
  ci_lower: number;
  ci_upper: number;
  p_value: number | null;
  /** Whisker lengths below and above the point, for the chart's error bars. */
  whisker: [number, number];
};

/** The terms with a complete estimate and CI, strongest evidence (smallest p) first. */
export function forestRows(terms: OddsRatioTerm[], max = MAX_FOREST_ROWS): ForestRow[] {
  return terms
    .filter(
      (t): t is OddsRatioTerm & { odds_ratio: number; ci_lower: number; ci_upper: number } =>
        t.odds_ratio != null && t.ci_lower != null && t.ci_upper != null && t.odds_ratio > 0 && t.ci_lower > 0,
    )
    .sort((a, b) => (a.p_value ?? 1) - (b.p_value ?? 1))
    .slice(0, max)
    .map((t) => ({
      label: t.label,
      odds_ratio: t.odds_ratio,
      ci_lower: t.ci_lower,
      ci_upper: t.ci_upper,
      p_value: t.p_value ?? null,
      whisker: [t.odds_ratio - t.ci_lower, t.ci_upper - t.odds_ratio],
    }));
}

const LOG_TICKS = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100];

/** Log-axis range that contains every whisker and 1, with round tick values inside it. */
export function forestAxis(rows: ForestRow[]): { domain: [number, number]; ticks: number[] } {
  const lo = Math.min(1, ...rows.map((r) => r.ci_lower));
  const hi = Math.max(1, ...rows.map((r) => r.ci_upper));
  const domain: [number, number] = [
    [...LOG_TICKS].reverse().find((t) => t <= lo) ?? lo,
    LOG_TICKS.find((t) => t >= hi) ?? hi,
  ];
  return { domain, ticks: LOG_TICKS.filter((t) => t >= domain[0] && t <= domain[1]) };
}

/** Shorten long axis labels; the full name stays in tooltips and tables. */
export function shortLabel(label: string, max = 22): string {
  return label.length > max ? `${label.slice(0, max - 1)}…` : label;
}

/** Permutation importance, largest first, capped for readability. */
export function topImportance(items: PermutationItem[], max = MAX_BARS): PermutationItem[] {
  return [...items].sort((a, b) => a.rank - b.rank).slice(0, max);
}

export type BeeswarmPoint = { shap: number; row: number; tone: number; label: string };

/** Deterministic vertical spread so overlapping points stay visible (no randomness). */
function jitter(i: number): number {
  return (((i * 37) % 17) / 16 - 0.5) * 0.6;
}

/**
 * One row per feature (row 0 = most important at the top). Numeric points get a tone in
 * [0, 1] from low to high value within the feature; categorical points get their level's index.
 */
export function beeswarmPoints(features: ShapFeature[]): { points: BeeswarmPoint[]; levels: Record<string, string[]> } {
  const points: BeeswarmPoint[] = [];
  const levels: Record<string, string[]> = {};
  features.forEach((feature, f) => {
    const row = features.length - 1 - f;
    if (feature.kind === "numeric") {
      const values = feature.points.map((p) => (typeof p.value === "number" ? p.value : NaN)).filter(Number.isFinite);
      const lo = Math.min(...values);
      const hi = Math.max(...values);
      feature.points.forEach((p, i) => {
        const v = typeof p.value === "number" ? p.value : NaN;
        const tone = Number.isFinite(v) && hi > lo ? (v - lo) / (hi - lo) : 0.5;
        points.push({ shap: p.shap, row: row + jitter(i), tone, label: `${feature.feature} = ${Number.isFinite(v) ? v : "missing"}` });
      });
    } else {
      const names = [...new Set(feature.points.map((p) => String(p.value ?? "missing")))];
      levels[feature.feature] = names;
      feature.points.forEach((p, i) => {
        const name = String(p.value ?? "missing");
        const tone = names.length > 1 ? names.indexOf(name) / (names.length - 1) : 0.5;
        points.push({ shap: p.shap, row: row + jitter(i), tone, label: `${feature.feature} = ${name}` });
      });
    }
  });
  return { points, levels };
}
