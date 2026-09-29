"use client";

import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";

import { beeswarmPoints, shortLabel, type BeeswarmPoint, type ShapFeature } from "@/lib/drivers";
import { formatStat } from "@/lib/format";
import { PALETTE, toneColour } from "@/lib/palette";

import { EmptyState } from "../ui";

function PointTooltip({ active, payload }: { active?: boolean; payload?: { payload: BeeswarmPoint }[] }) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;
  return (
    <div className="rounded border border-gray-200 bg-white px-2 py-1 text-xs shadow dark:border-gray-700 dark:bg-gray-900">
      <p>{point.label}</p>
      <p>SHAP {formatStat(point.shap)}</p>
    </div>
  );
}

export function ShapSummary({ features, scale }: { features: ShapFeature[]; scale: string | null | undefined }) {
  if (!features.length) return <EmptyState>SHAP values are not available for this model.</EmptyState>;
  const { points } = beeswarmPoints(features);
  const names = features.map((f) => f.feature);
  const rowName = (row: number) => shortLabel(names[names.length - 1 - Math.round(row)] ?? "", 20);
  return (
    <figure>
      <div className="w-full" style={{ height: 60 + features.length * 34 }}>
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 8, right: 16, bottom: 24, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis
              type="number"
              dataKey="shap"
              fontSize={12}
              tickFormatter={(v: number) => formatStat(v, 1)}
              label={{ value: "SHAP value (log-odds)", position: "insideBottom", offset: -14, fontSize: 12 }}
            />
            <YAxis
              type="number"
              dataKey="row"
              domain={[-0.6, names.length - 0.4]}
              ticks={names.map((_, i) => i)}
              tickFormatter={rowName}
              width={140}
              fontSize={12}
            />
            <ReferenceLine x={0} stroke={PALETTE.grey} />
            <Tooltip content={<PointTooltip />} />
            <Scatter
              data={points}
              isAnimationActive={false}
              shape={(props: { cx?: number; cy?: number; payload?: BeeswarmPoint }) => (
                <circle cx={props.cx} cy={props.cy} r={2.5} fill={toneColour(props.payload?.tone ?? 0.5)} fillOpacity={0.7} />
              )}
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 text-xs text-gray-500">
        What this shows: each dot is a test customer; dots right of 0 push that customer&apos;s churn risk up. Colour runs
        from <span style={{ color: toneColour(0) }}>low</span> to <span style={{ color: toneColour(1) }}>high</span>{" "}
        values (or across category levels). Scale: {scale ?? "log-odds"}.
      </figcaption>
    </figure>
  );
}
