import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { Analysis, Experiment } from "@/lib/api";

import { ResultsView } from "./results-view";

afterEach(cleanup);

const arm = (n: number, churned: number) => ({ n, churned, rate: churned / n, ci_low: churned / n - 0.02, ci_high: churned / n + 0.02 });

function analysis(overrides: Partial<Analysis> = {}): Analysis {
  return {
    srm: {
      observed: { treatment: 1500, control: 1500 },
      expected: { treatment: 1500, control: 1500 },
      planned_control_share: 0.5,
      observed_control_share: 0.5,
      chi2: 0,
      p_value: 1,
      threshold: 0.001,
      failed: false,
    },
    itt: {
      arms: { treatment: arm(1500, 315), control: arm(1500, 390) },
      difference: { value: -0.05, ci_low: -0.08, ci_high: -0.02, method: "newcombe", ci_level: 0.95 },
      relative_lift: -0.19,
      z: -3.2,
      p_value: 0.0012,
      significant: true,
      achieved_power: 0.81,
      label: "ITT",
    },
    impact: {
      customers_saved: 75,
      saved_ci_low: 30,
      saved_ci_high: 120,
      acceptors: 600,
      acceptance_rate: 0.4,
      customer_value: 800,
      offer_cost: 20,
      total_offer_cost: 12000,
      net_value: 48000,
      net_value_ci_low: 12000,
      net_value_ci_high: 84000,
      formula: "x",
      assumptions: [{ name: "customer_value", value: 800, source: "data" }],
    },
    per_protocol: { label: "Per-protocol: biased", available: false, significant: false },
    guardrails: {},
    segments: null,
    assumptions: [{ name: "customer_value", value: 800, source: "data" }],
    decision_helper: {
      verdict: "ship",
      reasons: ["Churn fell."],
      guardrails_breached: [],
      extra_sample_needed: null,
      note: "Decision helper only.",
    },
    warnings: [],
    ...overrides,
  };
}

function experiment(a: Analysis, status = "results_uploaded"): Experiment {
  return { id: 1, status, analysis: a, audit: [], assignment_summary: null } as unknown as Experiment;
}

describe("ResultsView", () => {
  it("shows the verdict, the per-arm rates and the decision form", () => {
    render(<ResultsView exp={experiment(analysis())} actor="Sam" onChange={() => {}} />);
    expect(screen.getByText("Suggests: ship")).toBeTruthy();
    expect(screen.getByRole("img", { name: /Treatment \(offer\): 21.0% churn/ })).toBeTruthy();
    expect(screen.getByRole("img", { name: /All assigned \(ITT\): -5.0%/ })).toBeTruthy();
    expect(screen.getByRole("radio", { name: "Ship" })).toHaveProperty("disabled", false);
    expect(screen.getByRole("button", { name: "Record decision" })).toHaveProperty("disabled", true); // note needed
  });

  it("blocks ship when the sample ratio check failed", () => {
    const a = analysis({
      srm: { ...analysis().srm, failed: true, p_value: 0.00001, observed_control_share: 0.4 },
      decision_helper: { ...analysis().decision_helper, verdict: "untrustworthy", reasons: ["SRM"] },
      warnings: ["Sample ratio mismatch: results not trustworthy."],
    });
    render(<ResultsView exp={experiment(a)} actor="Sam" onChange={() => {}} />);
    expect(screen.getByText("Not trustworthy (SRM)")).toBeTruthy();
    expect(screen.getByRole("radio", { name: "Ship" })).toHaveProperty("disabled", true);
    expect(screen.getByText(/Ship is blocked/)).toBeTruthy();
  });

  it("shows the recorded decision instead of the form once decided", () => {
    const exp = { ...experiment(analysis(), "decided"), decision: "ship", decision_note: "Go" } as Experiment;
    render(<ResultsView exp={exp} actor="Sam" onChange={() => {}} />);
    expect(screen.queryByRole("button", { name: "Record decision" })).toBeNull();
    expect(screen.getByText(": Go", { exact: false })).toBeTruthy();
  });
});

describe("ExperimentsTab demo", () => {
  it("offers the demo only on the sample data", async () => {
    const { vi } = await import("vitest");
    vi.stubGlobal("fetch", vi.fn(async () => new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } })));
    const { ExperimentsTab } = await import("./experiments-tab");
    const results = {} as Parameters<typeof ExperimentsTab>[0]["results"];
    const { unmount } = render(<ExperimentsTab results={results} sessionId={"a".repeat(32)} sample />);
    expect(screen.getByRole("button", { name: "Load demo experiment" })).toBeTruthy();
    unmount();
    render(<ExperimentsTab results={results} sessionId={"a".repeat(32)} />);
    expect(screen.queryByRole("button", { name: "Load demo experiment" })).toBeNull();
    vi.unstubAllGlobals();
  });
});
