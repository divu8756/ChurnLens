// Result types the dashboard tabs read, generated from the API contract.
import type { components } from "./api-types";

type S = components["schemas"];

export type ResultsPayload = S["ResultsPayload"];
export type ModelMetrics = S["ModelMetrics"];
export type ImpactEstimates = S["ImpactEstimates"];
export type Insight = S["Insight"];
export type Recommendation = S["Recommendation"];
export type ValidationReport = S["ValidationReport"];

/** Recommendations in the order to act on them (priority 1 = do first). */
export function byPriority(items: Recommendation[]): Recommendation[] {
  return [...items].sort((a, b) => a.priority - b.priority);
}
