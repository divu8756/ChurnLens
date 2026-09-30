"use client";

import { useId, useState, type KeyboardEvent, type ReactNode } from "react";

import type { ResultsPayload } from "@/lib/results";

import { DataHealthView } from "../data-health";
import { DriversTab } from "../drivers/drivers-tab";
import { AgentHealthTab } from "../agent-health/agent-health-tab";
import { BusinessImpactTab } from "../business-impact/business-impact-tab";
import { ExperimentsTab } from "../experiments/experiments-tab";
import { ModelPerformanceTab } from "../model-performance/model-performance-tab";
import { HypothesisTab } from "../hypothesis/hypothesis-tab";
import { InsightsTab } from "../insights/insights-tab";
import { PredictionsTab } from "../predictions/predictions-tab";
import { RecommendationsTab } from "../recommendations/recommendations-tab";
import { OverviewTab } from "../overview/overview-tab";
import { EmptyState } from "../ui";

type Tab = { id: string; label: string; render: (results: ResultsPayload, sessionId: string, sample: boolean) => ReactNode };

// Each dashboard tab registers here (later tabs are added by their own tasks).
const TABS: Tab[] = [
  { id: "overview", label: "Executive Overview", render: (r) => <OverviewTab results={r} /> },
  { id: "insights", label: "Customer Insights", render: (r) => <InsightsTab results={r} /> },
  { id: "drivers", label: "Churn Drivers", render: (r) => <DriversTab results={r} /> },
  { id: "model", label: "Model Performance", render: (r, id) => <ModelPerformanceTab results={r} sessionId={id} /> },
  { id: "hypothesis", label: "Hypothesis Testing", render: (r) => <HypothesisTab results={r} /> },
  { id: "predictions", label: "Risk Predictions", render: (r, id) => <PredictionsTab results={r} sessionId={id} /> },
  { id: "recommendations", label: "Recommendations", render: (r) => <RecommendationsTab results={r} /> },
  { id: "business", label: "Business Impact", render: (_, id) => <BusinessImpactTab sessionId={id} /> },
  { id: "experiments", label: "Experiments", render: (r, id, sample) => <ExperimentsTab results={r} sessionId={id} sample={sample} /> },
  { id: "agents", label: "Agent Health", render: (_, id) => <AgentHealthTab sessionId={id} /> },
  {
    id: "health",
    label: "Data Health",
    render: (r) =>
      r.data_health ? (
        <DataHealthView health={r.data_health} log={r.cleaning_log ?? []} warnings={r.offer_effectiveness?.warnings ?? []} />
      ) : (
        <EmptyState>Data health is not available.</EmptyState>
      ),
  },
];

export function Dashboard({ results, sessionId, sample = false }: { results: ResultsPayload; sessionId: string; sample?: boolean }) {
  const [active, setActive] = useState(TABS[0].id);
  const base = useId();

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const index = TABS.findIndex((t) => t.id === active);
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const next = TABS[(index + step + TABS.length) % TABS.length];
    setActive(next.id);
    document.getElementById(`${base}-tab-${next.id}`)?.focus();
  };

  const tab = TABS.find((t) => t.id === active) ?? TABS[0];
  return (
    <div className="flex flex-col gap-4">
      <div
        role="tablist"
        aria-label="Dashboard"
        onKeyDown={onKeyDown}
        className="-mx-4 flex gap-1 overflow-x-auto border-b border-gray-200 px-4 dark:border-gray-800"
      >
        {TABS.map((t) => (
          <button
            key={t.id}
            id={`${base}-tab-${t.id}`}
            type="button"
            role="tab"
            aria-selected={t.id === active}
            aria-controls={`${base}-panel`}
            tabIndex={t.id === active ? 0 : -1}
            onClick={() => setActive(t.id)}
            className={`shrink-0 border-b-2 px-3 py-2 text-sm font-medium whitespace-nowrap ${
              t.id === active
                ? "border-blue-600 text-blue-700 dark:text-blue-300"
                : "border-transparent text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`${base}-panel`} aria-labelledby={`${base}-tab-${tab.id}`}>
        {tab.render(results, sessionId, sample)}
      </div>
    </div>
  );
}
