"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { shortLabel } from "@/lib/drivers";
import { formatCount, formatPercent } from "@/lib/format";
import type { EdaResults } from "@/lib/insights";
import { PALETTE } from "@/lib/palette";

import { EmptyState } from "../ui";

type Row = { level: string; n: number; churned: number; churn_rate: number };

function RowTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <div className="rounded border border-gray-200 bg-white px-2 py-1 text-xs shadow dark:border-gray-700 dark:bg-gray-900">
      <p className="font-medium">{row.level}</p>
      <p>
        {formatPercent(row.churn_rate)} churn ({formatCount(row.churned)} of {formatCount(row.n)})
      </p>
    </div>
  );
}

export function CategoryChart({
  categorical,
  columns,
  overallRate,
}: {
  categorical: EdaResults["categorical"];
  columns: string[];
  overallRate: number | null;
}) {
  const [column, setColumn] = useState(columns[0] ?? "");
  const summary = categorical?.[column];
  if (!columns.length) return <EmptyState>No categorical columns to compare.</EmptyState>;
  const rows = summary?.levels ?? [];
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
      <div className="w-full" style={{ height: 60 + rows.length * 30 }}>
        <ResponsiveContainer>
          <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 16, bottom: 24, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis
              type="number"
              fontSize={12}
              tickFormatter={(v: number) => formatPercent(v, 0)}
              label={{ value: "Churn rate", position: "insideBottom", offset: -14, fontSize: 12 }}
            />
            <YAxis type="category" dataKey="level" width={130} fontSize={12} interval={0} tickFormatter={(v: string) => shortLabel(v, 20)} />
            <Tooltip cursor={{ fill: "rgba(128, 128, 128, 0.15)" }} content={<RowTooltip />} />
            {overallRate != null ? <ReferenceLine x={overallRate} stroke={PALETTE.grey} strokeWidth={2} /> : null}
            <Bar dataKey="churn_rate" name="Churn rate" fill={PALETTE.vermillion} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="text-xs text-gray-500">
        What this shows: the share of customers who churned in each group of {column}; the grey line is the overall
        rate{overallRate != null ? ` (${formatPercent(overallRate)})` : ""}.
        {summary?.levels_folded_into_other ? ` ${summary.levels_folded_into_other} rare levels are grouped as Other.` : ""}
      </figcaption>
    </figure>
  );
}
