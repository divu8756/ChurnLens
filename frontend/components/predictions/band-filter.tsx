import type { RiskBand } from "@/lib/api";
import { formatCount } from "@/lib/format";
import { RISK_COLOURS } from "@/lib/palette";

const OPTIONS: (RiskBand | null)[] = [null, "High", "Medium", "Low"];

export function BandFilter({
  band,
  counts,
  total,
  onChange,
}: {
  band: RiskBand | null;
  counts: Record<string, number>;
  total: number;
  onChange: (band: RiskBand | null) => void;
}) {
  return (
    <div role="group" aria-label="Filter by risk band" className="flex flex-wrap gap-2">
      {OPTIONS.map((option) => {
        const active = option === band;
        return (
          <button
            key={option ?? "all"}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option)}
            className={`inline-flex min-h-9 items-center gap-2 rounded-full border px-3 text-sm ${
              active
                ? "border-blue-600 bg-blue-50 font-medium text-blue-800 dark:bg-blue-950 dark:text-blue-200"
                : "border-gray-300 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-900"
            }`}
          >
            {option ? (
              <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: RISK_COLOURS[option] }} aria-hidden />
            ) : null}
            {option ?? "All"}
            <span className="tabular-nums text-gray-500">{formatCount(option ? counts[option] : total)}</span>
          </button>
        );
      })}
    </div>
  );
}
