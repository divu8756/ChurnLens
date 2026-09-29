import { describe, expect, it } from "vitest";

import { groupRecommendations, impactText } from "./recommendations";
import type { Recommendation } from "./results";

const rec = (id: string, group: Recommendation["group"], priority: number): Recommendation => ({
  id,
  problem: "p",
  action: "a",
  target_segment: "s",
  customers_affected: { source_key: "k", value: 10, display: "10" },
  impact: { source_key: "impact_estimates.items.x.scenarios.reduce_10pct.churners_saved", value: 1, assumption: "a" },
  effort: "low",
  priority,
  group,
  figures: [],
});

describe("groupRecommendations", () => {
  it("keeps a fixed group order, sorts by priority and drops empty groups", () => {
    const groups = groupRecommendations([rec("R3", "strategic", 3), rec("R2", "quick_win", 4), rec("R1", "quick_win", 1)]);
    expect(groups.map((g) => g.id)).toEqual(["quick_win", "strategic"]);
    expect(groups[0].items.map((r) => r.id)).toEqual(["R1", "R2"]);
  });
});

describe("impactText", () => {
  const key = (suffix: string) => `impact_estimates.items.Contract=Month-to-month.scenarios.reduce_10pct.${suffix}`;

  it("labels revenue and churner impacts", () => {
    expect(impactText({ source_key: key("monthly_revenue_saved"), value: 12077.84, assumption: "" }, "MonthlyCharges")).toBe(
      "12,078 monthly revenue kept (MonthlyCharges)",
    );
    expect(impactText({ source_key: key("churners_saved"), value: 153.7, assumption: "" })).toBe("153.7 fewer churners");
  });

  it("falls back to the number", () => {
    expect(impactText({ source_key: "impact_estimates.items.x.customers", value: 3861, assumption: "" })).toBe("3,861");
  });
});
