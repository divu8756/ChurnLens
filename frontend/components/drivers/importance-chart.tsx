"use client";

import { Bar, BarChart, CartesianGrid, ErrorBar, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { shortLabel, topImportance, type PermutationItem } from "@/lib/drivers";
import { formatStat } from "@/lib/format";
import { PALETTE } from "@/lib/palette";

import { EmptyState } from "../ui";

export function ImportanceChart({ items, method }: { items: PermutationItem[]; method: string | null | undefined }) {
  const data = topImportance(items);
  if (!data.length) return <EmptyState>Feature importance is not available.</EmptyState>;
  return (
    <figure>
      <div className="w-full" style={{ height: 40 + data.length * 26 }}>
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 24, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis
              type="number"
              fontSize={12}
              tickFormatter={(v: number) => formatStat(v, 3)}
              label={{ value: "Drop in test ROC-AUC when shuffled", position: "insideBottom", offset: -14, fontSize: 12 }}
            />
            <YAxis type="category" dataKey="feature" width={140} fontSize={12} interval={0} tickFormatter={(v: string) => shortLabel(v, 20)} />
            <Tooltip cursor={{ fill: "rgba(128, 128, 128, 0.15)" }} formatter={(v) => [formatStat(Number(v), 4), "ROC-AUC drop"]} />
            <Bar dataKey="importance_mean" name="ROC-AUC drop" fill={PALETTE.blue}>
              <ErrorBar dataKey="importance_std" direction="x" stroke={PALETTE.grey} width={4} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 text-xs text-gray-500">
        What this shows: how much the model gets worse when each column is scrambled (bigger = more important;
        whiskers ± 1 SD). {method}
      </figcaption>
    </figure>
  );
}
