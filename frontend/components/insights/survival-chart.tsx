"use client";

import { useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { components } from "@/lib/api-types";
import { formatP, formatPercent, formatStat } from "@/lib/format";
import { curveSeries } from "@/lib/insights";

import { EmptyState } from "../ui";

type Survival = components["schemas"]["SurvivalResults"];

export function SurvivalChart({ survival }: { survival: Survival | null | undefined }) {
  const [view, setView] = useState("overall");
  if (!survival || survival.skipped || !survival.overall) {
    return <EmptyState>{survival?.reason ?? "Survival curves need a time column (for example tenure)."}</EmptyState>;
  }
  const groups = survival.by_group ?? [];
  const group = groups.find((g) => g.column === view);
  const curves = group ? group.curves : [survival.overall];
  const series = curveSeries(curves);
  const unit = survival.time_column ?? "time";
  return (
    <figure className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm sm:max-w-xs">
        <span className="font-medium">Show</span>
        <select
          value={view}
          onChange={(e) => setView(e.target.value)}
          className="min-h-9 rounded-lg border border-gray-300 bg-white px-2 dark:border-gray-700 dark:bg-gray-900"
        >
          <option value="overall">All customers</option>
          {groups.map((g) => (
            <option key={g.column} value={g.column}>
              By {g.column}
            </option>
          ))}
        </select>
      </label>
      <div className="h-72 w-full">
        <ResponsiveContainer>
          <LineChart margin={{ top: 8, right: 16, bottom: 24, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              type="number"
              dataKey="time"
              domain={[0, "dataMax"]}
              fontSize={12}
              allowDuplicatedCategory={false}
              label={{ value: unit, position: "insideBottom", offset: -14, fontSize: 12 }}
            />
            <YAxis
              type="number"
              domain={[0, 1]}
              fontSize={12}
              tickFormatter={(v: number) => formatPercent(v, 0)}
              label={{ value: "Still a customer", angle: -90, position: "insideLeft", fontSize: 12 }}
            />
            <Tooltip formatter={(v) => formatPercent(Number(v), 1)} labelFormatter={(v) => `${unit} ${formatStat(Number(v), 0)}`} />
            <Legend verticalAlign="top" wrapperStyle={{ fontSize: 12, paddingBottom: 8 }} />
            {series.map((s) => (
              <Line
                key={s.label}
                data={s.points}
                dataKey="survival"
                name={s.label}
                type="stepAfter"
                stroke={s.colour}
                dot={false}
                strokeWidth={2}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="text-xs text-gray-500">
        What this shows: the share of customers still with you after each amount of {unit} (Kaplan-Meier).{" "}
        {curves
          .map((c) => `${c.label}: median ${c.median_reached && c.median_survival != null ? formatStat(c.median_survival, 0) : "not reached"}`)
          .join("; ")}
        .{group ? ` Log-rank test p ${formatP(group.logrank.p_value)}.` : ""}
      </figcaption>
    </figure>
  );
}
