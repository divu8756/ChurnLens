import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OfferPanel } from "./offer-panel";

const detail = {
  customer_id: "C1",
  risk_band: "High",
  reasons: ["Contract: Month-to-month (+0.74)"],
  best_offer: "10% loyalty discount (3 mo)",
  expected_value: 104.56,
  runner_up: "Free 10GB data booster",
  runner_up_value: 40.1,
  p_churn: 0.972,
  p_accept: 0.4,
  p_stay_if_accepted: 0.72,
  p_stay_if_declined: 0.55,
  retention_lift: 0.17,
  customer_value: 1253.28,
  offer_cost: 24.73,
  low_data: true,
  eligible_offers: 6,
  no_offer_reason: null,
  value_unit: "revenue",
  formula: "",
  assumptions: [{ name: "horizon_months", value: 12, source: "default", text: "Customer value = monthly MonthlyCharges x 12 months." }],
};
const message = {
  customer_id: "C1",
  offer: detail.best_offer,
  message: "Thank you for staying with us. Enjoy a 10% loyalty discount (3 mo).",
  sms: "Enjoy a 10% loyalty discount (3 mo). Reply YES.",
  source: "ai",
  cached: false,
  problems: [],
};

const fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>();

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (url, init) =>
    new Response(JSON.stringify(init?.method === "POST" ? message : detail), { status: 200 }),
  );
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("OfferPanel", () => {
  it("shows the offer, the formula with inputs and the assumptions", async () => {
    const { container } = render(<OfferPanel sessionId="s1" customerId="C1" />);
    expect(await screen.findByText("10% loyalty discount (3 mo)")).toBeTruthy();
    expect(screen.getAllByText("104.56").length).toBeGreaterThan(0); // headline and formula
    expect(container.querySelectorAll(".katex").length).toBe(3);
    expect(screen.getByText("low data: segment rate")).toBeTruthy();
    expect(screen.getByText("default")).toBeTruthy();
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/predictions\/s1\/offer\/C1$/);
  });

  it("generates the message on demand only", async () => {
    render(<OfferPanel sessionId="s1" customerId="C1" />);
    await screen.findByText("10% loyalty discount (3 mo)");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Generate message" }));
    expect(await screen.findByText(message.message)).toBeTruthy();
    expect(screen.getByText(/SMS \(47\/160\)/)).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[1];
    expect(String(url)).toMatch(/\/offer\/C1\/message$/);
    expect(init?.method).toBe("POST");
  });
});
