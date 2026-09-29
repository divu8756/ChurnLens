// Pure helpers for the schema confirmation screen. The server re-validates everything.
import type { ConfirmedSchema, SchemaProposal } from "./api";
import type { components } from "./api-types";

export type SemanticType = components["schemas"]["ConfirmedColumn"]["semantic_type"];
export type OfferColumns = components["schemas"]["OfferColumns"];

/** The single-column offer fields the form can edit (lists come only from the proposal). */
export const OFFER_FIELDS = [
  { key: "shown", label: "Offer shown", help: "Name of the offer a customer was sent" },
  { key: "accepted", label: "Offer accepted", help: "Yes/No, or the accepted offer names" },
  { key: "date", label: "Offer date", help: "When the offer was sent (used to avoid leakage)" },
  { key: "cost", label: "Offer cost", help: "Cost of the offer to you" },
  { key: "group", label: "Campaign group", help: "Targeted / holdout arm, if any" },
] as const;
export type OfferField = (typeof OFFER_FIELDS)[number]["key"];

export const SEMANTIC_TYPES: SemanticType[] = ["numeric", "categorical", "binary", "datetime", "text", "id"];

export type SchemaDraft = {
  columns: { name: string; semantic_type: SemanticType; confidence: number }[];
  target_column: string;
  positive_label: string;
  time_column: string | null;
  revenue_column: string | null;
  /** null = no offer analysis. */
  offer_columns: OfferColumns | null;
};

export function labelValues(proposal: SchemaProposal, column: string): string[] | null {
  return proposal.label_options?.find((option) => option.column === column)?.values ?? null;
}

export function draftFromProposal(proposal: SchemaProposal): SchemaDraft {
  const target = proposal.target_column ?? "";
  const values = target ? labelValues(proposal, target) : null;
  const positive = proposal.positive_label ?? values?.[values.length - 1] ?? "";
  return {
    columns: proposal.columns.map((c) => ({ ...c })),
    target_column: target,
    positive_label: positive,
    time_column: proposal.time_column ?? null,
    revenue_column: proposal.revenue_column ?? null,
    offer_columns: proposal.offer_columns ? { ...proposal.offer_columns } : null,
  };
}

export function withTarget(draft: SchemaDraft, proposal: SchemaProposal, target: string): SchemaDraft {
  const values = labelValues(proposal, target);
  // Keep the label if the new target has it; otherwise pick a likely "churned" value.
  const positive =
    values && values.includes(draft.positive_label)
      ? draft.positive_label
      : (values?.find((v) => /^(yes|true|1|churn(ed)?|exited|left)$/i.test(v)) ?? values?.[values.length - 1] ?? "");
  const columns = draft.columns.map((c) =>
    c.name === target && c.semantic_type === "id" ? { ...c, semantic_type: "binary" as const } : c,
  );
  return { ...draft, target_column: target, positive_label: positive, columns };
}

export function withColumnType(draft: SchemaDraft, name: string, type: SemanticType): SchemaDraft {
  return { ...draft, columns: draft.columns.map((c) => (c.name === name ? { ...c, semantic_type: type } : c)) };
}

/** Set one offer field; an empty value clears it. Clearing "shown" turns the analysis off. */
export function withOfferField(draft: SchemaDraft, field: OfferField, column: string): SchemaDraft {
  const value = column || null;
  if (field === "shown" && !value) return { ...draft, offer_columns: null };
  const current: OfferColumns = draft.offer_columns ?? { shown: "", other: [] };
  const other = (current.other ?? []).filter((c) => c !== value);
  return { ...draft, offer_columns: { ...current, other, [field]: value } as OfferColumns };
}

export function offerColumnNames(offers: OfferColumns | null): string[] {
  if (!offers) return [];
  const values = [offers.shown, offers.accepted, offers.date, offers.cost, offers.group, ...(offers.other ?? [])];
  return [...new Set(values.flatMap((v) => (Array.isArray(v) ? v : v ? [v] : [])))];
}

export function idColumns(draft: SchemaDraft): string[] {
  return draft.columns.filter((c) => c.semantic_type === "id").map((c) => c.name);
}

/** Quick checks before sending; the server's 422 problems are the final word. */
export function draftProblems(draft: SchemaDraft): string[] {
  const problems: string[] = [];
  if (!draft.target_column) problems.push("Choose the target (churn) column.");
  if (draft.target_column && !draft.positive_label.trim()) {
    problems.push("Choose which target value means the customer churned.");
  }
  const ids = idColumns(draft);
  if (ids.includes(draft.target_column)) problems.push("The target column cannot be an ID column.");
  if (draft.time_column && draft.time_column === draft.target_column) {
    problems.push("The time column cannot be the target column.");
  }
  if (draft.time_column && ids.includes(draft.time_column)) problems.push("The time column cannot be an ID column.");
  const offers = offerColumnNames(draft.offer_columns);
  const reserved = new Set([draft.target_column, draft.time_column, draft.revenue_column, ...ids].filter(Boolean));
  const clash = offers.filter((c) => reserved.has(c));
  if (clash.length) problems.push(`Offer columns cannot also be the target, ID, time or revenue column: ${clash.join(", ")}.`);
  if (draft.offer_columns && !draft.offer_columns.shown) problems.push("Choose the column that names the offer shown.");
  return problems;
}

export function toConfirmed(draft: SchemaDraft): ConfirmedSchema {
  return {
    columns: draft.columns.map(({ name, semantic_type }) => ({ name, semantic_type })),
    target_column: draft.target_column,
    positive_label: draft.positive_label.trim(),
    id_columns: idColumns(draft),
    time_column: draft.time_column,
    revenue_column: draft.revenue_column,
    offer_columns: draft.offer_columns,
  };
}
