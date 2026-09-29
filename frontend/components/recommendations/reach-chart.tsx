"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatCount } from "@/lib/format";
import { PALETTE } from "@/lib/palette";
import { GROUPS } from "@/lib/recommendations";
import { byPriority, type Recommendation } from "@/lib/results";

const GROUP_COLOURS: Record<Recommendation["group"], string> = {
  quick_win: PALETTE.green,
  medium_term: PALETTE.orange,
  strategic: PALETTE.purple,
};

/** Customers each recommendation reaches, in priority order, coloured by group. */
export function ReachChart({ recommendations }: { recommendations: Recommendation[] }) {
  const data = byPriority(recommendations).map((r) => ({
    id: `${r.id} (P${r.priority})`,
    customers: r.customers_affected.value,
    group: r.group,
    action: r.action,
  }));
  return (
    <figure>
      <div className="w-full" style={{ height: 60 + data.length * 32 }}>
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 24, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis
              type="number"
              fontSize={12}
              tickFormatter={(v: number) => formatCount(v)}
              label={{ value: "Customers affected", position: "insideBottom", offset: -14, fontSize: 12 }}
            />
            <YAxis type="category" dataKey="id" width={80} fontSize={12} />
            <Tooltip
              cursor={{ fill: "rgba(128, 128, 128, 0.15)" }}
              formatter={(v) => [formatCount(Number(v)), "Customers"]}
              labelFormatter={(_, payload) => payload?.[0]?.payload?.action ?? ""}
            />
            <Bar dataKey="customers" name="Customers">
              {data.map((d) => (
                <Cell key={d.id} fill={GROUP_COLOURS[d.group]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 flex flex-wrap gap-x-3 text-xs text-gray-500">
        <span>What this shows: how many customers each recommendation reaches, highest priority at the top.</span>
        {GROUPS.map((g) => (
          <span key={g.id} className="inline-flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: GROUP_COLOURS[g.id] }} aria-hidden />
            {g.label}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
