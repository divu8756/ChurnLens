// Recommendations tab helpers: grouping, ordering and labelling the validated impact figure.
import { formatMoney } from "./format";
import { byPriority, type Recommendation } from "./results";

export type Group = Recommendation["group"];

export const GROUPS: { id: Group; label: string; blurb: string }[] = [
  { id: "quick_win", label: "Quick wins", blurb: "Low effort, results soon." },
  { id: "medium_term", label: "Medium-term", blurb: "Some build or budget needed." },
  { id: "strategic", label: "Strategic", blurb: "Bigger changes with a longer payoff." },
];

/** Groups in a fixed order, each sorted by priority (1 = do first); empty groups are dropped. */
export function groupRecommendations(items: Recommendation[]): { id: Group; label: string; blurb: string; items: Recommendation[] }[] {
  const sorted = byPriority(items);
  return GROUPS.map((g) => ({ ...g, items: sorted.filter((r) => r.group === g.id) })).filter((g) => g.items.length > 0);
}

const oneDecimal = new Intl.NumberFormat("en", { maximumFractionDigits: 1 });

/** The impact value comes from impact_estimates; its key says what it counts. */
export function impactText(impact: Recommendation["impact"], revenueColumn?: string | null): string {
  const key = impact.source_key;
  if (key.endsWith(".monthly_revenue_saved")) {
    return `${formatMoney(impact.value)} monthly revenue kept${revenueColumn ? ` (${revenueColumn})` : ""}`;
  }
  if (key.endsWith(".churners_saved")) return `${oneDecimal.format(impact.value)} fewer churners`;
  return oneDecimal.format(impact.value);
}

export const EFFORT_LABELS: Record<Recommendation["effort"], string> = { low: "Low effort", medium: "Medium effort", high: "High effort" };
