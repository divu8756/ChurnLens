// One place for number formatting so every tab shows numbers the same way.
// These only format numbers from the API; they never derive new metrics.
const EN = "en";

const DASH = "–";

const valid = (value: number | null | undefined): value is number => typeof value === "number" && Number.isFinite(value);

/** Whole counts with thousands separators: 7,000. */
export function formatCount(value: number | null | undefined): string {
  return valid(value) ? new Intl.NumberFormat(EN, { maximumFractionDigits: 0 }).format(value) : DASH;
}

/** A fraction (0.2566) shown as a percentage: 25.66%. */
export function formatPercent(fraction: number | null | undefined, digits = 2): string {
  return valid(fraction) ? `${(fraction * 100).toFixed(digits)}%` : DASH;
}

/** Statistics (test statistics, effect sizes, AUC) to 2 dp by default. */
export function formatStat(value: number | null | undefined, digits = 2): string {
  if (!valid(value)) return DASH;
  const text = value.toFixed(digits);
  return /^-0(\.0+)?$/.test(text) ? text.slice(1) : text; // no "-0.0" for tiny negatives
}

/** p-values: 3 dp, and anything below 0.001 as "< 0.001". */
export function formatP(value: number | null | undefined): string {
  if (!valid(value)) return DASH;
  return value < 0.001 ? "< 0.001" : value.toFixed(3);
}

/** Money in the data's own (unknown) currency: grouped, no decimals for large sums. */
export function formatMoney(value: number | null | undefined): string {
  if (!valid(value)) return DASH;
  const digits = Math.abs(value) >= 1000 ? 0 : 2;
  return new Intl.NumberFormat(EN, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
}
