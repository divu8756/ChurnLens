import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { HypothesisTest } from "@/lib/hypothesis";
import type { ResultsPayload } from "@/lib/results";

import { HypothesisTab } from "./hypothesis-tab";

afterEach(cleanup);

const contract: HypothesisTest = {
  variable: "Contract",
  kind: "categorical",
  test_name: "Chi-square test of independence",
  why: "All expected counts >= 5.",
  h0: "Churn rate is the same for every level of Contract.",
  h1: "Churn rate differs between at least two levels of Contract.",
  assumptions: [{ name: "Expected counts >= 5 in every cell", result: true, detail: "smallest expected count = 380.8" }],
  inputs: {
    observed: { rows: ["Month-to-month", "Two year"], columns: ["retained", "churned"], values: [[2324, 1537], [1589, 66]] },
    churn_rate_by_level: { "Month-to-month": 0.398, "Two year": 0.0399 },
  },
  statistic: 937.307,
  statistic_name: "chi-square",
  df: 2,
  p_value: 2.9e-204,
  p_adjusted: 1.17e-202,
  significant: true,
  effect_size: { name: "Cramér's V", value: 0.3659, band: "medium" },
  steps: [{ label: "Chi-square statistic", formula: "\\chi^2 = \\sum \\frac{(O-E)^2}{E}", substituted: "\\chi^2 = 937.3" }],
  conclusion: "Significant at alpha = 0.05.",
  merged_levels: [],
};
const borderline: HypothesisTest = { ...contract, variable: "CityTier", p_value: 0.02, p_adjusted: 0.03, conclusion: "Significant at alpha = 0.05." };

const results = {
  hypothesis_results: { alpha: 0.05, correction: "Benjamini-Hochberg", n_tests: 2, n_significant: 2, tests: [borderline, contract], skipped: [] },
} as unknown as ResultsPayload;

describe("HypothesisTab", () => {
  it("sorts by adjusted p and formats tiny p-values", () => {
    render(<HypothesisTab results={results} />);
    const rows = screen.getAllByRole("button", { expanded: false }).map((b) => b.textContent);
    expect(rows).toEqual(["▸Contract", "▸CityTier"]);
    expect(screen.getByText("< 0.001")).toBeTruthy();
    expect(screen.getByText("0.030")).toBeTruthy();
  });

  it("expands a row into the KaTeX calculation", () => {
    const { container } = render(<HypothesisTab results={results} />);
    fireEvent.click(screen.getByRole("button", { name: /Contract/ }));
    expect(screen.getByText(/H₀:/)).toBeTruthy();
    expect(container.querySelectorAll(".katex").length).toBe(2);
    expect(screen.getByText("Observed counts (O)")).toBeTruthy();
  });

  it("re-derives significance when alpha moves", () => {
    render(<HypothesisTab results={results} />);
    expect(screen.getByText("2", { selector: "span" })).toBeTruthy();
    fireEvent.change(screen.getByRole("slider"), { target: { value: "2" } }); // alpha 0.01
    expect(screen.getByText("1", { selector: "span" })).toBeTruthy();
    expect(screen.getAllByText("No")).toHaveLength(1);
  });
});
