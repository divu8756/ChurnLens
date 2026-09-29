import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { ImpactEstimates, Insight, ModelMetrics, Recommendation } from "@/lib/results";

import { KpiCards } from "./kpi-cards";
import { TopInsights } from "./top-insights";
import { TopRecommendations } from "./top-recommendations";
import { ValidatorBadge } from "./validator-badge";

afterEach(cleanup);

const metrics = {
  chosen_model: "logistic_regression",
  chosen_model_name: "Logistic regression",
  test: { roc_auc: 0.8308, pr_auc: 0.63, accuracy: 0.74, precision: 0.5, recall: 0.75, f1: 0.6, n_test: 1400 },
  n_train: 5600,
  n_test: 1400,
  risk_bands: { thresholds: { high: 0.6, medium: 0.3 }, band_counts: { High: 2239, Medium: 1862, Low: 2899 }, total: 7000 },
} as ModelMetrics;

const impact = {
  overall: { id: "overall", label: "All customers", customers: 7000, churners: 1796, churn_rate: 0.256571, monthly_revenue_at_risk: 142056.33 },
  revenue_column: "MonthlyCharges",
} as ImpactEstimates;

const rec = (id: string, priority: number, action: string): Recommendation => ({
  id,
  problem: "p",
  action,
  target_segment: "Month-to-month customers",
  customers_affected: { source_key: "k", value: 3861, display: "3,861" },
  impact: { source_key: "i", value: 1, assumption: "a" },
  effort: "low",
  priority,
  group: "quick_win",
  figures: [],
});

describe("Executive Overview", () => {
  it("shows the five KPIs formatted", () => {
    render(<KpiCards impact={impact} metrics={metrics} />);
    for (const text of ["7,000", "25.66%", "2,239", "142,056", "0.83"]) {
      expect(screen.getByText(text)).toBeTruthy();
    }
    expect(screen.getByText("Logistic regression, held-out test set")).toBeTruthy();
  });

  it("shows dashes when the model and revenue are missing", () => {
    render(<KpiCards impact={{ ...impact, overall: { ...impact.overall, monthly_revenue_at_risk: null }, revenue_column: null }} metrics={null} />);
    expect(screen.getAllByText("–").length).toBe(3);
    expect(screen.getByText("no revenue column chosen")).toBeTruthy();
  });

  it("lists the top 3 recommendations by priority", () => {
    render(<TopRecommendations recommendations={[rec("R4", 4, "Fourth"), rec("R1", 1, "First"), rec("R3", 3, "Third"), rec("R2", 2, "Second")]} />);
    const actions = screen.getAllByRole("heading").map((h) => h.textContent);
    expect(actions).toEqual(["First", "Second", "Third"]);
  });

  it("marks non-significant insights and handles none", () => {
    const insight: Insight = { id: "I9", title: "Demographics", text: "No clear link.", figures: [], significant: false, causality_note: "" };
    render(<TopInsights insights={[insight]} />);
    expect(screen.getByText("Not significant")).toBeTruthy();
    cleanup();
    render(<TopInsights insights={[]} />);
    expect(screen.getByText("No verified insights for this run.")).toBeTruthy();
  });

  it("shows the validator result", () => {
    render(<ValidatorBadge report={{ checked: 15, passed: 12, failed: 3, dropped: 3, final: true }} />);
    expect(screen.getByText(/12\/15 AI items verified · 3 dropped/)).toBeTruthy();
  });
});
