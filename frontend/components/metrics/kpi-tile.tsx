"use client";

import { useId, useState } from "react";

/** A KPI with a plain-English explanation that works with a mouse, keyboard or touch. */
export function KpiTile({ label, value, note, help }: { label: string; value: string; note?: string; help: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-gray-500">{label}</p>
        <button
          type="button"
          aria-label={`What is ${label}?`}
          aria-expanded={open}
          aria-controls={id}
          onClick={() => setOpen(!open)}
          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-gray-300 text-xs text-gray-500 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-900"
        >
          ?
        </button>
      </div>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {note ? <p className="mt-1 text-xs text-gray-500">{note}</p> : null}
      <p id={id} hidden={!open} className="mt-2 text-xs text-gray-600 dark:text-gray-400">
        {help}
      </p>
    </div>
  );
}

export function SourceChip({ source }: { source: string }) {
  const style =
    source === "user"
      ? "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200"
      : source === "data"
        ? "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200"
        : "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300";
  return <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${style}`}>{source}</span>;
}
