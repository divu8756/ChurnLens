import { shortLabel } from "@/lib/drivers";
import { formatStat } from "@/lib/format";
import { cellTextColour, divergingColour, topCorrelations, type Correlation } from "@/lib/insights";

import { EmptyState } from "../ui";

export function CorrelationHeatmap({ correlation }: { correlation: Correlation }) {
  const { columns, matrix } = topCorrelations(correlation);
  if (columns.length < 2) return <EmptyState>Not enough numeric columns for a correlation map.</EmptyState>;
  return (
    <figure>
      <div className="overflow-x-auto">
        <table className="border-separate border-spacing-0.5 text-xs">
          <caption className="sr-only">Pearson correlation between numeric columns</caption>
          <thead>
            <tr>
              <th />
              {columns.map((c) => (
                <th key={c} scope="col" className="relative h-28 w-10 min-w-10 font-normal">
                  {/* Absolutely placed so the rotated label does not widen its column. */}
                  <span className="absolute bottom-1 left-1/2 origin-bottom-left -rotate-60 whitespace-nowrap" title={c}>
                    {shortLabel(c, 16)}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {columns.map((row, i) => (
              <tr key={row}>
                <th scope="row" className="pr-2 text-right font-normal whitespace-nowrap" title={row}>
                  {shortLabel(row, 18)}
                </th>
                {matrix[i].map((r, j) => (
                  <td
                    key={columns[j]}
                    title={`${row} vs ${columns[j]}: r = ${formatStat(r)}`}
                    className="h-10 w-10 min-w-10 text-center tabular-nums"
                    style={{ background: divergingColour(r), color: cellTextColour(r) }}
                  >
                    {formatStat(r, 1)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <figcaption className="mt-2 text-xs text-gray-500">
        What this shows: Pearson correlation between the {columns.length} numeric columns most correlated with churn (orange = move
        together, blue = move in opposite directions).
      </figcaption>
    </figure>
  );
}
