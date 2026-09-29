// Hypothesis Testing tab helpers. Significance at another alpha is a comparison of the
// server's BH-adjusted p-value with alpha (the adjustment itself does not depend on alpha).
import type { components } from "./api-types";

export type HypothesisResults = components["schemas"]["HypothesisResults"];
export type HypothesisTest = components["schemas"]["HypothesisTest"];

export const ALPHAS = [0.001, 0.005, 0.01, 0.025, 0.05, 0.1] as const;
export const DEFAULT_ALPHA = 0.05;

export function significantAt(test: HypothesisTest, alpha: number): boolean {
  return test.p_adjusted != null && test.p_adjusted < alpha;
}

/** Strongest evidence first; tests without a p-value last. */
export function sortTests(tests: HypothesisTest[]): HypothesisTest[] {
  return [...tests].sort((a, b) => (a.p_adjusted ?? Infinity) - (b.p_adjusted ?? Infinity));
}

export function significantCount(tests: HypothesisTest[], alpha: number): number {
  return tests.filter((t) => significantAt(t, alpha)).length;
}

/** The server's conclusion is written for its alpha; say so when the user picks another. */
export function conclusionFor(test: HypothesisTest, alpha: number, serverAlpha: number): string {
  if (alpha === serverAlpha) return test.conclusion;
  const verdict = significantAt(test, alpha) ? "Significant" : "Not significant";
  return `${verdict} at alpha = ${alpha} (the adjusted p-value compared with the alpha you chose). At alpha = ${serverAlpha}: ${test.conclusion}`;
}
