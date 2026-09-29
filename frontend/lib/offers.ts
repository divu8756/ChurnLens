// Next-best-offer display helpers. Values come from the API; these only format them.
import type { NextBestOffer } from "./api";
import { formatMoney, formatStat } from "./format";

export type ValueUnit = "revenue" | "customers";

export function formatOfferValue(value: number | null | undefined, unit: ValueUnit): string {
  if (value == null) return "–";
  return unit === "revenue" ? formatMoney(value) : `${formatStat(value, 2)} customers`;
}

const p = (v: number | null | undefined) => formatStat(v, 3);

/** The expected-value formula with this customer's inputs filled in (LaTeX). */
export function substitutedFormula(o: NextBestOffer): string {
  if (o.p_accept == null || o.retention_lift == null) return String.raw`\text{No offer: } EV = 0`;
  const value = o.value_unit === "revenue" ? formatStat(o.customer_value, 2) : "1";
  const cost = formatStat(o.offer_cost ?? 0, 2);
  return (
    String.raw`EV = ${p(o.p_churn)} \times ${p(o.p_accept)} \times ${p(o.retention_lift)} \times ${value}` +
    String.raw` - ${p(o.p_accept)} \times ${cost} = ${formatStat(o.expected_value, 2)}`
  );
}

export const GENERAL_FORMULA = String.raw`EV = P(\text{churn}) \times P(\text{accept}) \times \text{lift} \times \text{value} - P(\text{accept}) \times \text{cost}`;
export const LIFT_FORMULA = String.raw`\text{lift} = \max\big(0,\ P(\text{stay} \mid \text{accepted}) - P(\text{stay} \mid \text{declined})\big)`;
