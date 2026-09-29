import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { ResultsPayload } from "@/lib/results";

import { InsightsTab } from "./insights-tab";

afterEach(cleanup);

const results = {
  eda_results: {
    overview: { rows: 100, churned: 25, churn_rate: 0.25 },
    numeric: {
      tenure: {
        count: 100,
        missing: 0,
        churned: { n: 25, mean: 10, median: 8, std: 5 },
        retained: { n: 75, mean: 30, median: 28, std: 12 },
        histogram: { edges: [0, 1], counts: [100] },
      },
    },
    categorical: {
      Contract: { levels: [{ level: "Month-to-month", n: 60, churned: 20, churn_rate: 0.333 }], levels_folded_into_other: 0 },
    },
    correlation: { columns: ["tenure", "fee"], matrix: [[1, -0.4], [-0.4, 1]], with_target: { tenure: -0.35, fee: 0.2 } },
  },
  segments: {
    skipped: false,
    segments: [
      { segment: 0, label: "High fee, Low tenure", size: 30, pct_of_base: 0.3, churn_rate: 0.5, churn_lift: 2, feature_means: { fee: 90 }, feature_z: { fee: 1.5 } },
    ],
  },
  survival_results: null,
  final_insights: [
    { id: "I1", title: "Monthly contracts churn most", text: "t", figures: [], significant: true, causality_note: "" },
    { id: "I2", title: "Region looks flat", text: "t", figures: [], significant: false, causality_note: "" },
  ],
} as unknown as ResultsPayload;

describe("InsightsTab", () => {
  it("renders every section and marks non-significant insights", () => {
    render(<InsightsTab results={results} />);
    expect(screen.getByText("Monthly contracts churn most")).toBeTruthy();
    expect(screen.getByText(/Not statistically significant: treat as a lead/)).toBeTruthy();
    expect(screen.getByText("High fee, Low tenure")).toBeTruthy();
    expect(screen.getByText("2.00×")).toBeTruthy();
    expect(screen.getAllByTitle(/tenure vs fee: r = -0.40/)).toHaveLength(1);
    expect(screen.getByText(/Survival curves need a time column/)).toBeTruthy();
  });

  it("explains missing EDA", () => {
    render(<InsightsTab results={{} as ResultsPayload} />);
    expect(screen.getByText("Exploratory results are not available for this run.")).toBeTruthy();
  });
});
