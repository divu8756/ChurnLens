import { describe, expect, it } from "vitest";

import { conclusionFor, significantAt, significantCount, sortTests, type HypothesisTest } from "./hypothesis";

const test = (variable: string, p: number | null): HypothesisTest => ({
  variable,
  kind: "categorical",
  test_name: "Chi-square test of independence",
  why: "",
  h0: "",
  h1: "",
  assumptions: [],
  inputs: {},
  statistic: 1,
  statistic_name: "chi-square",
  df: 1,
  p_value: p,
  p_adjusted: p,
  significant: p != null && p < 0.05,
  effect_size: { name: "Cramér's V", value: 0.1, band: "small" },
  steps: [],
  conclusion: "server text",
  merged_levels: [],
});

describe("hypothesis helpers", () => {
  it("re-derives significance at any alpha from the adjusted p-value", () => {
    const t = test("x", 0.03);
    expect(significantAt(t, 0.05)).toBe(true);
    expect(significantAt(t, 0.01)).toBe(false);
    expect(significantAt(test("y", 0.05), 0.05)).toBe(false); // strict: p < alpha
    expect(significantAt(test("z", null), 0.1)).toBe(false);
  });

  it("counts significant tests at the chosen alpha", () => {
    const tests = [test("a", 1e-10), test("b", 0.02), test("c", 0.2)];
    expect(significantCount(tests, 0.05)).toBe(2);
    expect(significantCount(tests, 0.001)).toBe(1);
  });

  it("sorts by adjusted p with missing values last", () => {
    expect(sortTests([test("c", 0.2), test("n", null), test("a", 1e-10)]).map((t) => t.variable)).toEqual(["a", "c", "n"]);
  });

  it("keeps the server conclusion at the server alpha and explains other alphas", () => {
    expect(conclusionFor(test("a", 0.03), 0.05, 0.05)).toBe("server text");
    expect(conclusionFor(test("a", 0.03), 0.01, 0.05)).toMatch(/^Not significant at alpha = 0.01/);
  });
});
