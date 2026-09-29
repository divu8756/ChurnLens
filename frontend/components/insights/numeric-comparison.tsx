"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatStat } from "@/lib/format";
import type { EdaResults } from "@/lib/insights";
import { PALETTE } from "@/lib/palette";

import { EmptyState } from "../ui";

export function NumericComparison({ numeric, columns }: { numeric: EdaResults["numeric"]; columns: string[] }) {
  const [column, setColumn] = useState(columns[0] ?? "");
  const summary = numeric?.[column];
  if (!columns.length || !summary) return <EmptyState>No numeric columns to compare.</EmptyState>;
  const data = [
    { stat: "Mean", Churned: summary.churned.mean, Retained: summary.retained.mean },
    { stat: "Median", Churned: summary.churned.median, Retained: summary.retained.median },
  ];
  return (
    <figure className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm sm:max-w-xs">
        <span className="font-medium">Column (strongest evidence first)</span>
        <select
          value={column}
          onChange={(e) => setColumn(e.target.value)}
          className="min-h-9 rounded-lg border border-gray-300 bg-white px-2 dark:border-gray-700 dark:bg-gray-900"
        >
          {columns.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>
      <div className="h-60 w-full">
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="stat" fontSize={12} />
            <YAxis fontSize={12} tickFormatter={(v: number) => formatStat(v, Number.isInteger(v) ? 0 : 1)} label={{ value: column, angle: -90, position: "insideLeft", fontSize: 12 }} />
            <Tooltip cursor={{ fill: "rgba(128, 128, 128, 0.15)" }} formatter={(v) => formatStat(Number(v))} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="Churned" fill={PALETTE.vermillion} />
            <Bar dataKey="Retained" fill={PALETTE.blue} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="text-xs text-gray-500">
        What this shows: typical {column} for customers who churned vs stayed (n = {summary.churned.n} and{" "}
        {summary.retained.n}
        {summary.missing ? `; ${summary.missing} missing values left out` : ""}).
      </figcaption>
    </figure>
  );
}
