"use client";

import { CartesianGrid, ErrorBar, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";

import { forestAxis, forestRows, shortLabel, type ForestRow, type OddsRatioTerm } from "@/lib/drivers";
import { formatP, formatStat } from "@/lib/format";
import { PALETTE } from "@/lib/palette";

import { EmptyState } from "../ui";

function RowTooltip({ active, payload }: { active?: boolean; payload?: { payload: ForestRow }[] }) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <div className="rounded border border-gray-200 bg-white px-2 py-1 text-xs shadow dark:border-gray-700 dark:bg-gray-900">
      <p className="font-medium">{row.label}</p>
      <p>
        OR {formatStat(row.odds_ratio)} (95% CI {formatStat(row.ci_lower)} to {formatStat(row.ci_upper)})
      </p>
      <p>p {formatP(row.p_value)}</p>
    </div>
  );
}

export function OddsForest({ terms, method }: { terms: OddsRatioTerm[]; method: string | null | undefined }) {
  const rows = forestRows(terms);
  if (!rows.length) return <EmptyState>Odds ratios are not available.</EmptyState>;
  const data = rows.map((row, i) => ({ ...row, y: rows.length - 1 - i }));
  const axis = forestAxis(rows);
  return (
    <figure>
      <div className="w-full" style={{ height: 60 + rows.length * 28 }}>
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 8, right: 16, bottom: 24, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} strokeOpacity={0.4} />
            <XAxis
              type="number"
              dataKey="odds_ratio"
              scale="log"
              domain={axis.domain}
              ticks={axis.ticks}
              fontSize={12}
              tickFormatter={(v: number) => String(v)}
              label={{ value: "Odds ratio (log scale)", position: "insideBottom", offset: -14, fontSize: 12 }}
            />
            <YAxis
              type="number"
              dataKey="y"
              domain={[-0.6, rows.length - 0.4]}
              ticks={data.map((d) => d.y)}
              tickFormatter={(y: number) => shortLabel(data.find((d) => d.y === y)?.label ?? "", 28)}
              width={180}
              fontSize={11}
            />
            <ReferenceLine x={1} stroke={PALETTE.grey} strokeWidth={2} />
            <Tooltip content={<RowTooltip />} />
            <Scatter data={data} fill={PALETTE.vermillion} isAnimationActive={false}>
              <ErrorBar dataKey="whisker" direction="x" stroke={PALETTE.vermillion} width={4} />
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 text-xs text-gray-500">
        What this shows: odds of churning for each group compared with its reference (right of the solid line at 1 = more
        likely to churn), with 95% confidence intervals; the {rows.length} terms with the strongest evidence. {method}
      </figcaption>
    </figure>
  );
}
