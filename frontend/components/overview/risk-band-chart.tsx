"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatCount, formatPercent } from "@/lib/format";
import { RISK_COLOURS } from "@/lib/palette";
import type { ModelMetrics } from "@/lib/results";

import { EmptyState } from "../ui";

const BANDS = ["High", "Medium", "Low"] as const;

export function RiskBandChart({ bands }: { bands: NonNullable<ModelMetrics["risk_bands"]> | null }) {
  if (!bands) return <EmptyState>Risk scores are not available for this run.</EmptyState>;
  const data = BANDS.map((band) => ({ band, customers: bands.band_counts[band] ?? 0 }));
  return (
    <figure>
      <div className="h-56 w-full">
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 20, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="band" fontSize={12} label={{ value: "Risk band", position: "insideBottom", offset: -12, fontSize: 12 }} />
            <YAxis fontSize={12} tickFormatter={(v: number) => formatCount(v)} label={{ value: "Customers", angle: -90, position: "insideLeft", fontSize: 12 }} />
            <Tooltip formatter={(v) => [formatCount(Number(v)), "Customers"]} />
            <Bar dataKey="customers" name="Customers">
              {data.map((d) => (
                <Cell key={d.band} fill={RISK_COLOURS[d.band]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 text-xs text-gray-500">
        What this shows: customers by predicted churn risk. High ≥ {formatPercent(bands.thresholds.high, 0)}, Medium ≥{" "}
        {formatPercent(bands.thresholds.medium, 0)}, Low below that.
      </figcaption>
    </figure>
  );
}
