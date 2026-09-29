import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { Recommendation, ResultsPayload } from "@/lib/results";

import { RecommendationsTab } from "./recommendations-tab";

afterEach(cleanup);

const rec = (id: string, group: Recommendation["group"], priority: number, action: string): Recommendation => ({
  id,
  problem: "Month-to-month customers churn at 39.81%.",
  action,
  target_segment: "Month-to-month customers",
  customers_affected: { source_key: "impact_estimates.items.Contract=Month-to-month.customers", value: 3861, display: "3,861" },
  impact: {
    source_key: "impact_estimates.items.Contract=Month-to-month.scenarios.reduce_10pct.monthly_revenue_saved",
    value: 12077.84,
    assumption: "If churn in this group fell by 10% (relative).",
  },
  effort: group === "quick_win" ? "low" : "high",
  priority,
  group,
  figures: [],
});

const results = (items: Recommendation[]) =>
  ({
    final_recommendations: items,
    impact_estimates: { overall: {}, revenue_column: "MonthlyCharges" },
    validation_report: { checked: 3, passed: 3, failed: 0, dropped: 0, final: true },
  }) as unknown as ResultsPayload;

describe("RecommendationsTab", () => {
  it("groups cards in order and shows every field", () => {
    render(
      <RecommendationsTab
        results={results([rec("R3", "strategic", 3, "Rebuild onboarding"), rec("R2", "quick_win", 2, "Email offer"), rec("R1", "quick_win", 1, "Annual plan")])}
      />,
    );
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(["Recommendations", "Quick wins (2)", "Strategic (1)"]);
    const actions = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(actions).toEqual(["Annual plan", "Email offer", "Rebuild onboarding"]);
    expect(screen.getAllByText("12,078 monthly revenue kept (MonthlyCharges)")).toHaveLength(3);
    expect(screen.getAllByText(/Assumption: If churn in this group fell by 10%/)).toHaveLength(3);
    expect(screen.getAllByText("3,861")).toHaveLength(3);
    expect(screen.getByText("✓ 3/3 AI items verified")).toBeTruthy();
  });

  it("explains an empty result", () => {
    render(<RecommendationsTab results={results([])} />);
    expect(screen.getByText(/No recommendations passed the number checks/)).toBeTruthy();
  });
});
