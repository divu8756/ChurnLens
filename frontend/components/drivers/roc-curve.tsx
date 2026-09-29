"use client";

import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatStat } from "@/lib/format";
import { PALETTE } from "@/lib/palette";
import type { ModelMetrics } from "@/lib/results";

type Curve = NonNullable<ModelMetrics["test"]["roc_curve"]>;

const TICKS = [0, 0.2, 0.4, 0.6, 0.8, 1];

export function RocCurve({ curve, auc }: { curve: Curve; auc: number | null | undefined }) {
  const data = curve.fpr.map((fpr, i) => ({ fpr, tpr: curve.tpr[i] }));
  return (
    <figure>
      <div className="h-64 w-full">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 24, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              type="number"
              dataKey="fpr"
              domain={[0, 1]}
              ticks={TICKS}
              fontSize={12}
              tickFormatter={(v: number) => formatStat(v, 1)}
              label={{ value: "False positive rate", position: "insideBottom", offset: -14, fontSize: 12 }}
            />
            <YAxis
              type="number"
              domain={[0, 1]}
              ticks={TICKS}
              fontSize={12}
              tickFormatter={(v: number) => formatStat(v, 1)}
              label={{ value: "True positive rate", angle: -90, position: "insideLeft", fontSize: 12 }}
            />
            <Tooltip
              formatter={(v) => formatStat(Number(v))}
              labelFormatter={(v) => `False positive rate ${formatStat(Number(v))}`}
            />
            <ReferenceLine
              segment={[
                { x: 0, y: 0 },
                { x: 1, y: 1 },
              ]}
              stroke={PALETTE.grey}
              strokeDasharray="4 4"
            />
            <Line type="stepAfter" dataKey="tpr" name="True positive rate" stroke={PALETTE.blue} dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 text-xs text-gray-500">
        What this shows: how many churners the model catches (up) for each rate of false alarms (right) on the test
        set. The dashed line is chance; ROC-AUC {formatStat(auc)}.
      </figcaption>
    </figure>
  );
}
