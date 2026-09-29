import { describe, expect, it } from "vitest";

import type { NextBestOffer } from "./api";
import { formatOfferValue, substitutedFormula } from "./offers";

const offer = {
  customer_id: "C1",
  risk_band: "High",
  reasons: [],
  best_offer: "10% loyalty discount (3 mo)",
  expected_value: 104.56,
  p_churn: 0.972,
  p_accept: 0.4,
  p_stay_if_accepted: 0.72,
  p_stay_if_declined: 0.55,
  retention_lift: 0.17,
  customer_value: 1253.28,
  offer_cost: 24.73,
  low_data: false,
  eligible_offers: 6,
  value_unit: "revenue",
  formula: "",
  assumptions: [],
} as NextBestOffer;

describe("offers", () => {
  it("formats values by unit", () => {
    expect(formatOfferValue(12077.84, "revenue")).toBe("12,078");
    expect(formatOfferValue(0.4567, "customers")).toBe("0.46 customers");
    expect(formatOfferValue(null, "revenue")).toBe("–");
  });

  it("substitutes the customer's inputs into the formula", () => {
    expect(substitutedFormula(offer)).toBe(
      String.raw`EV = 0.972 \times 0.400 \times 0.170 \times 1253.28 - 0.400 \times 24.73 = 104.56`,
    );
    expect(substitutedFormula({ ...offer, p_accept: null, retention_lift: null })).toContain("No offer");
  });
});
