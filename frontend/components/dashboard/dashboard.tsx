"use client";

import { useId, useState, type KeyboardEvent, type ReactNode } from "react";

import type { ResultsPayload } from "@/lib/results";

import { DataHealthView } from "../data-health";
import { OverviewTab } from "../overview/overview-tab";
import { EmptyState } from "../ui";

type Tab = { id: string; label: string; render: (results: ResultsPayload) => ReactNode };

// Each dashboard tab registers here (later tabs are added by their own tasks).
const TABS: Tab[] = [
  { id: "overview", label: "Executive Overview", render: (r) => <OverviewTab results={r} /> },
  {
    id: "health",
    label: "Data Health",
    render: (r) =>
      r.data_health ? (
        <DataHealthView health={r.data_health} log={r.cleaning_log ?? []} />
      ) : (
        <EmptyState>Data health is not available.</EmptyState>
      ),
  },
];

export function Dashboard({ results }: { results: ResultsPayload }) {
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
        {tab.render(results)}
      </div>
    </div>
  );
}
