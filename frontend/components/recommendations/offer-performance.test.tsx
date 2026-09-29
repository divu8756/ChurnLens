import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { components } from "@/lib/api-types";

import { OfferPerformance } from "./offer-performance";

afterEach(cleanup);

const effectiveness: components["schemas"]["OfferEffectiveness"] = {
  offers: [
    {
      offer: "10% loyalty discount (3 mo)",
      shown: 430,
      accepted: 190,
      acceptance_rate: 0.4419,
      acceptors: { n: 190, churned: 53, churn_rate: 0.2789 },
      decliners: { n: 240, churned: 107, churn_rate: 0.4458 },
      test: { test_name: "Chi-square test of independence", variable: "Offer: x", p_value: 0.0001, p_adjusted: 0.0007, significant: true },
    },
    {
      offer: "Device upgrade credit",
      shown: 133,
      accepted: 25,
      acceptance_rate: 0.188,
      acceptors: { n: 25, churned: 8, churn_rate: 0.32 },
      decliners: { n: 108, churned: 42, churn_rate: 0.3889 },
      test: { test_name: "Chi-square test of independence", variable: "Offer: y", p_value: 0.5, p_adjusted: 0.65, significant: false },
    },
  ],
  never_offered: { n: 5448, churned: 1212, churn_rate: 0.2225 },
  offered: { n: 1552, churned: 584, churn_rate: 0.3763 },
  warnings: ["Offered customers were riskier to begin with."],
  note: "Acceptors chose to accept.",
  next_best_offer: {
    customers_scored: 4136,
    value_unit: "revenue",
    total_expected_value: 187408.3,
    by_offer: [{ offer: "10% loyalty discount (3 mo)", customers: 1793, expected_value: 104179.13 }],
    offer_models: {},
    formula: "",
    assumptions: [],
  },
};

describe("OfferPerformance", () => {
  it("shows every offer with n, significance, warnings and the next-best-offer summary", () => {
    render(<OfferPerformance effectiveness={effectiveness} />);
    expect(screen.getByRole("heading", { name: /Offer performance/ })).toBeTruthy();
    expect(screen.getByText("27.9%")).toBeTruthy();
    expect(screen.getByText("n = 240")).toBeTruthy();
    expect(screen.getByText("Statistically significant")).toBeTruthy();
    expect(screen.getByText("Not significant")).toBeTruthy();
    expect(screen.getByText("Offered customers were riskier to begin with.")).toBeTruthy();
    expect(screen.getByText(/4,136 Medium and High risk customers scored/)).toBeTruthy();
    expect(screen.getByText("1,793 · 104,179")).toBeTruthy();
  });
});
