import { describe, expect, it } from "vitest";

import type { SchemaProposal } from "./api";
import { draftFromProposal, draftProblems, toConfirmed, withColumnType, withOfferField, withTarget } from "./schema-form";

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
      offer_columns: null,
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

describe("offer columns", () => {
  const withOffers: SchemaProposal = {
    ...proposal,
    columns: [...proposal.columns, { name: "OfferShown", semantic_type: "categorical", confidence: 0.6 }],
    offer_columns: { shown: "OfferShown", accepted: null, other: ["OfferChannel"] },
  };

  it("carries the proposed offer columns through to the confirmed schema", () => {
    expect(toConfirmed(draftFromProposal(withOffers)).offer_columns).toEqual({
      shown: "OfferShown",
      accepted: null,
      other: ["OfferChannel"],
    });
  });

  it("clearing the shown column turns the offer analysis off", () => {
    expect(withOfferField(draftFromProposal(withOffers), "shown", "").offer_columns).toBeNull();
  });

  it("sets a field and removes it from the other campaign columns", () => {
    const draft = withOfferField(draftFromProposal(withOffers), "group", "OfferChannel");
    expect(draft.offer_columns).toMatchObject({ group: "OfferChannel", other: [] });
  });

  it("rejects an offer column that is also the target", () => {
    const draft = withOfferField(draftFromProposal(withOffers), "accepted", "Churn");
    expect(draftProblems(draft)).toContain("Offer columns cannot also be the target, ID, time or revenue column: Churn.");
  });
});
