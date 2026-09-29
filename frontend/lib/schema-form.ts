// Pure helpers for the schema confirmation screen. The server re-validates everything.
import type { ConfirmedSchema, SchemaProposal } from "./api";
import type { components } from "./api-types";

export type SemanticType = components["schemas"]["ConfirmedColumn"]["semantic_type"];

export const SEMANTIC_TYPES: SemanticType[] = ["numeric", "categorical", "binary", "datetime", "text", "id"];

export type SchemaDraft = {
  columns: { name: string; semantic_type: SemanticType; confidence: number }[];
  target_column: string;
  positive_label: string;
  time_column: string | null;
  revenue_column: string | null;
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
  };
}
