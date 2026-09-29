import { describe, expect, it } from "vitest";

import type { SchemaProposal } from "./api";
import { draftFromProposal, draftProblems, toConfirmed, withColumnType, withTarget } from "./schema-form";

const proposal: SchemaProposal = {
  columns: [
    { name: "customerID", semantic_type: "id", confidence: 0.95 },
    { name: "tenure", semantic_type: "numeric", confidence: 0.6 },
    { name: "Churn", semantic_type: "binary", confidence: 0.9 },
    { name: "Exited", semantic_type: "binary", confidence: 0.6 },
  ],
  target_column: "Churn",
  positive_label: "Yes",
  id_columns: ["customerID"],
  time_column: "tenure",
  revenue_column: null,
  reasoning: "rules",
  source: "rules",
  target_candidates: ["Churn", "Exited"],
  label_options: [
    { column: "Churn", values: ["No", "Yes"] },
    { column: "Exited", values: ["0", "1"] },
  ],
};

describe("schema form", () => {
  it("starts from the proposal and converts back to a confirmed schema", () => {
    const confirmed = toConfirmed(draftFromProposal(proposal));
    expect(confirmed).toEqual({
      columns: proposal.columns.map(({ name, semantic_type }) => ({ name, semantic_type })),
      target_column: "Churn",
      positive_label: "Yes",
      id_columns: ["customerID"],
      time_column: "tenure",
      revenue_column: null,
    });
    expect(draftProblems(draftFromProposal(proposal))).toEqual([]);
  });

  it("picks a sensible positive label when the target changes", () => {
    const draft = withTarget(draftFromProposal(proposal), proposal, "Exited");
    expect(draft.positive_label).toBe("1");
  });

  it("derives ID columns from column types", () => {
    const draft = withColumnType(draftFromProposal(proposal), "customerID", "categorical");
    expect(toConfirmed(draft).id_columns).toEqual([]);
  });

  it("flags a missing target, a missing label and conflicting roles", () => {
    const empty = { ...draftFromProposal(proposal), target_column: "" };
    expect(draftProblems(empty)).toContain("Choose the target (churn) column.");
    const noLabel = { ...draftFromProposal(proposal), positive_label: " " };
    expect(draftProblems(noLabel)).toContain("Choose which target value means the customer churned.");
    const clash = withColumnType(draftFromProposal(proposal), "tenure", "id");
    expect(draftProblems(clash)).toContain("The time column cannot be an ID column.");
  });
});
