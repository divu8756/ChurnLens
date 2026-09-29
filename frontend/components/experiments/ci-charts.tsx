import type { Analysis } from "@/lib/api";
import { axisDomain, position, type ForestRow } from "@/lib/experiments";
import { formatCount, formatPercent } from "@/lib/format";
import { PALETTE } from "@/lib/palette";

const ARMS = [
  { key: "treatment", label: "Treatment (offer)", colour: PALETTE.blue },
  { key: "control", label: "Control", colour: PALETTE.grey },
] as const;

/** Churn rate per arm as bars with 95% Wilson CI whiskers. */
export function ArmRateBars({ arms }: { arms: NonNullable<Analysis["itt"]["arms"]> }) {
  const max = Math.max(arms.treatment.ci_high, arms.control.ci_high) * 1.15 || 1;
  const domain: [number, number] = [0, max];
  return (
    <figure>
      <div className="flex flex-col gap-3">
        {ARMS.map(({ key, label, colour }) => {
          const arm = arms[key];
          return (
            <div key={key} className="grid grid-cols-[8.5rem_1fr] items-center gap-3 text-sm">
              <div>
                <p className="font-medium">{label}</p>
                <p className="text-xs text-gray-500">
                  {formatCount(arm.churned)} of {formatCount(arm.n)} churned
                </p>
              </div>
              <div className="relative h-8" role="img" aria-label={`${label}: ${formatPercent(arm.rate, 1)} churn, 95% CI ${formatPercent(arm.ci_low, 1)} to ${formatPercent(arm.ci_high, 1)}`}>
                <div className="absolute inset-y-1 left-0 rounded-r" style={{ width: `${position(arm.rate, domain)}%`, background: colour, opacity: 0.85 }} />
                <div
                  className="absolute top-1/2 h-px bg-gray-900 dark:bg-gray-100"
                  style={{ left: `${position(arm.ci_low, domain)}%`, width: `${position(arm.ci_high, domain) - position(arm.ci_low, domain)}%` }}
                />
                {[arm.ci_low, arm.ci_high].map((v, i) => (
                  <div key={i} className="absolute top-2 h-4 w-px bg-gray-900 dark:bg-gray-100" style={{ left: `${position(v, domain)}%` }} />
                ))}
                <span className="absolute top-1/2 -translate-y-1/2 pl-2 text-xs tabular-nums" style={{ left: `${position(arm.ci_high, domain)}%` }}>
                  {formatPercent(arm.rate, 1)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
      <figcaption className="mt-2 text-xs text-gray-500">
        What this shows: churn within the outcome window for everyone assigned (intention-to-treat). Whiskers are 95%
        Wilson confidence intervals.
      </figcaption>
    </figure>
  );
}

/** Difference in churn (treatment − control) with 95% CIs; left of 0 = the offer lowered churn. */
export function ForestPlot({ rows }: { rows: ForestRow[] }) {
  const domain = axisDomain(rows.flatMap((r) => [r.low, r.high]));
  const zero = position(0, domain);
  return (
    <figure>
      <div className="flex flex-col gap-2">
        {rows.map((r) => (
          <div key={r.label} className="grid grid-cols-[9rem_1fr_7.5rem] items-center gap-3 text-sm">
            <p className={r.primary ? "font-medium" : "text-gray-600 dark:text-gray-400"}>{r.label}</p>
            <div
              className="relative h-6"
              role="img"
              aria-label={`${r.label}: ${formatPercent(r.value, 1)} (95% CI ${formatPercent(r.low, 1)} to ${formatPercent(r.high, 1)})`}
            >
              <div className="absolute inset-y-0 w-px bg-gray-400" style={{ left: `${zero}%` }} />
              <div
                className="absolute top-1/2 h-0.5"
                style={{
                  left: `${position(r.low, domain)}%`,
                  width: `${position(r.high, domain) - position(r.low, domain)}%`,
                  background: r.primary ? PALETTE.blue : PALETTE.grey,
                }}
              />
              <div
                className={`absolute top-1/2 -translate-x-1/2 -translate-y-1/2 ${r.primary ? "h-3.5 w-3.5" : "h-2.5 w-2.5"} rotate-45`}
                style={{ left: `${position(r.value, domain)}%`, background: r.primary ? PALETTE.blue : PALETTE.grey }}
              />
            </div>
            <p className="text-right text-xs tabular-nums text-gray-600 dark:text-gray-400">
              {formatPercent(r.value, 1)} [{formatPercent(r.low, 1)}, {formatPercent(r.high, 1)}]
              {r.note ? <span className="block">{r.note}</span> : null}
            </p>
          </div>
        ))}
      </div>
      <figcaption className="mt-2 text-xs text-gray-500">
        What this shows: difference in churn rate, treatment minus control, with 95% Newcombe confidence intervals. Left of
        the line means the offer lowered churn; an interval crossing the line is not conclusive. Segment rows are
        pre-registered and exploratory.
      </figcaption>
    </figure>
  );
}
