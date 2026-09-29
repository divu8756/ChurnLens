// Customer Insights helpers: choosing and arranging what to show. Every value shown comes
// from the API; these only order, subset and colour it.
import type { components } from "./api-types";
import { PALETTE } from "./palette";

type S = components["schemas"];
export type EdaResults = S["EdaResults"];
export type Correlation = S["Correlation"];
export type Segment = S["Segment"];
export type KmSummary = S["KmSummary"];
export type HypothesisTest = S["HypothesisTest"];

export const MAX_HEATMAP = 12;

/** Columns ordered by the strength of their hypothesis-test evidence, then name. */
export function orderByEvidence(columns: string[], tests: HypothesisTest[] | undefined): string[] {
  const p = new Map((tests ?? []).map((t) => [t.variable, t.p_adjusted ?? 1]));
  return [...columns].sort((a, b) => (p.get(a) ?? 1) - (p.get(b) ?? 1) || a.localeCompare(b));
}

/** The columns most correlated with churn (by |r| from the API), as a smaller square matrix. */
export function topCorrelations(corr: Correlation, max = MAX_HEATMAP): { columns: string[]; matrix: (number | null)[][] } {
  const cols = corr.columns ?? [];
  const withTarget = corr.with_target ?? {};
  const picked = [...cols]
    .sort((a, b) => Math.abs(withTarget[b] ?? 0) - Math.abs(withTarget[a] ?? 0))
    .slice(0, max);
  const index = picked.map((c) => cols.indexOf(c));
  return { columns: picked, matrix: index.map((i) => index.map((j) => corr.matrix?.[i]?.[j] ?? null)) };
}

function mix(from: number[], to: number[], t: number): string {
  return `rgb(${from.map((c, i) => Math.round(c + (to[i] - c) * t)).join(", ")})`;
}

const WHITE = [245, 245, 245];
const BLUE = [0x00, 0x72, 0xb2];
const VERMILLION = [0xd5, 0x5e, 0x00];

/** Diverging colour for a correlation in [-1, 1]: blue (negative), light grey (0), vermillion (positive). */
export function divergingColour(r: number | null): string {
  if (r == null) return "transparent";
  const t = Math.min(1, Math.abs(r));
  return r < 0 ? mix(WHITE, BLUE, t) : mix(WHITE, VERMILLION, t);
}

/** Text colour that stays readable on the diverging fill. */
export function cellTextColour(r: number | null): string {
  return r != null && Math.abs(r) > 0.55 ? "#ffffff" : "#1f2937";
}

/** The features that most set a segment apart (largest |z|), for its card. */
export function distinctiveFeatures(segment: Segment, max = 3): { feature: string; z: number; mean: number | null }[] {
  return Object.entries(segment.feature_z ?? {})
    .filter((e): e is [string, number] => e[1] != null)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, max)
    .map(([feature, z]) => ({ feature, z, mean: segment.feature_means?.[feature] ?? null }));
}

export const CURVE_COLOURS = [PALETTE.blue, PALETTE.vermillion, PALETTE.green, PALETTE.orange, PALETTE.purple, PALETTE.skyBlue];

/** Kaplan-Meier curves as point lists for one chart (each curve keeps its own time grid). */
export function curveSeries(curves: KmSummary[]): { label: string; colour: string; points: { time: number; survival: number | null }[] }[] {
  return curves.map((curve, i) => ({
    label: curve.label,
    colour: CURVE_COLOURS[i % CURVE_COLOURS.length],
    points: curve.curve.time.map((time, k) => ({ time, survival: curve.curve.survival[k] ?? null })),
  }));
}
