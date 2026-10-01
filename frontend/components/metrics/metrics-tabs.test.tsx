import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../charts/plotly-chart", () => ({
  PlotlyChart: ({ label }: { label: string }) => <div role="img" aria-label={label} />,
}));

import { AgentHealthTab } from "../agent-health/agent-health-tab";
import { BusinessImpactTab } from "../business-impact/business-impact-tab";
import { ModelPerformanceTab } from "../model-performance/model-performance-tab";
import { KpiTile } from "./kpi-tile";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const scoreSet = {
  n: 1400,
  churn_rate: 0.26,
  roc_auc: 0.8286,
  pr_auc: 0.63,
  brier: 0.1397,
  top_10pct: { share: 0.1, k: 140, churners_in_top: 99, precision: 0.7071, recall: 0.27 },
  deciles: [],
  calibration: [],
  roc_curve: { fpr: [0, 1], tpr: [0, 1] },
  pr_curve: { recall: [0, 1], precision: [1, 0.26] },
};

const business = {
  enabled: true,
  defaults_only: true,
  revenue_at_risk: { total: 500000, customers: 7000, months_remaining: 12, arpu_column: "MonthlyCharges", formula: "x" },
  kpis: { revenue_at_risk: 500000, expected_saving: 12000, customers_with_offer: 2500, customers_scored: 7000, overall_roi: 1.5 },
  by_offer: [],
  roi_by_segment: [],
  offers: [
    { name: "Free 10GB data booster", acceptance: 0.45, save_rate: 0.3, cost: 5, cost_basis: "per_accepted", sources: { acceptance: "default", save_rate: "default", cost: "default" } },
  ],
  formula: {},
  warnings: [],
  assumptions: [{ name: "months_remaining", value: 12, unit: "months", source: "default", meaning: "Months." }],
  next_best_offers: [],
  ab_plan: { available: true, segment: "customers with an offer", segment_customers: 2500, p1: 0.4, p2: 0.32, relative_lift: 0.2, n_per_arm: 530, total_n: 1060, formula_latex: "n", warnings: [], assumptions: [] },
};

describe("KpiTile", () => {
  it("shows its plain-English explanation on demand", () => {
    render(<KpiTile label="Brier score" value="0.140" help="Lower is better." />);
    const help = screen.getByText("Lower is better.");
    expect(help.hidden).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "What is Brier score?" }));
    expect(help.hidden).toBe(false);
  });
});

describe("ModelPerformanceTab", () => {
  it("shows the KPIs and the four charts", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({
      split: "test", n_train: 5600, n_test: 1400, raw: { ...scoreSet, brier: 0.1681 }, calibrated: scoreSet,
      calibration_method: "isotonic", calibration_note: "Calibrated on the training split.", definitions: { lift: "Lift." },
      chosen_model_name: "Logistic regression",
    })));
    render(<ModelPerformanceTab results={{}} sessionId={"a".repeat(32)} />);
    expect(await screen.findByText("0.829")).toBeTruthy();
    expect(screen.getByText("70.7%")).toBeTruthy();
    expect(screen.getByText("raw model 0.168")).toBeTruthy();
    for (const name of [/^ROC curve/, /^Precision-recall curve/, /^Lift by risk decile/, /^Calibration:/]) {
      expect(screen.getByRole("img", { name })).toBeTruthy();
    }
  });
});

describe("BusinessImpactTab", () => {
  it("recomputes on the server after an edit and flags the explanation as stale", async () => {
    const calls: { url: string; body?: string }[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, body: init?.body as string | undefined });
      if (url.endsWith("/explain")) {
        return json({ sentences: ["a", "b", "c"], figures: [], source: "ai", problems: [], assumptions_hash: "h", cached: false });
      }
      if (init?.method === "POST") return json({ ...business, defaults_only: false });
      return json(business);
    }));
    render(<BusinessImpactTab sessionId={"a".repeat(32)} />);
    expect(await screen.findByText("500,000")).toBeTruthy();
    expect(screen.getAllByText("ASSUMPTION").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Explain these numbers" }));
    expect(await screen.findByText("a b c")).toBeTruthy();

    fireEvent.change(screen.getByRole("spinbutton", { name: "Months of revenue per saved customer" }), { target: { value: "24" } });
    expect(await screen.findByText("Based on default assumptions")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Regenerate explanation" })).toBeTruthy();
    await waitFor(() => expect(calls.some((c) => c.body === JSON.stringify({ months_remaining: 24 }))).toBe(true));
  });

  it("explains why business metrics are off without a revenue column", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ enabled: false, reason: "No monthly revenue (ARPU) column was confirmed." })));
    render(<BusinessImpactTab sessionId={"a".repeat(32)} />);
    expect(await screen.findByText(/No monthly revenue/)).toBeTruthy();
  });
});

describe("AgentHealthTab", () => {
  it("shows validator, corrections, tokens and the ESTIMATE cost", async () => {
    const summary = {
      session_id: "s", status: "done", events: 14,
      validator: { checked: 5, passed: 4, failed: 1, dropped: 1, figures_caught: 2, pass_rate: 0.8 },
      retries: { validator: { insight_agent: 1 }, llm_by_node: {} },
      schema_corrections: { count: 1, available: true, fields: [{ field: "revenue_column", proposed: null, confirmed: "MonthlyCharges" }] },
      latency_ms: { by_node: [{ node: "modelling", latency_ms: 4200, runs: 1, status: "done" }], total_node_time: 9000, wall_clock: 12500 },
      tokens: { by_model: { "gemini-x": { input_tokens: 1200, output_tokens: 300 } }, input: 1200, output: 300 },
      cost: { label: "ESTIMATE", currency: "USD", note: "free tier", total: 0, by_model: { "gemini-x": 0 } },
    };
    vi.stubGlobal("fetch", vi.fn(async (url: string) => (url.includes("/runs") ? json([summary]) : json(summary))));
    render(<AgentHealthTab sessionId={"a".repeat(32)} />);
    expect(await screen.findByText("80%")).toBeTruthy();
    expect(screen.getByText("12.5 s")).toBeTruthy();
    expect(screen.getAllByText("1,200")).toHaveLength(2); // KPI tile and the per-model table
    expect(screen.getAllByText("Cost (ESTIMATE)").length).toBeGreaterThan(0);
    expect(screen.getByText(/insight agent: 1 validator retry/)).toBeTruthy();
    expect(screen.getByRole("img", { name: "Latency per pipeline step" })).toBeTruthy();
  });
});
