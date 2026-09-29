import { describe, expect, it } from "vitest";

import type { Analysis, Experiment } from "./api";
import { axisDomain, filterText, forestRows, healthItems, position, segmentText, statusInfo } from "./experiments";

const analysis = {
  itt: { difference: { value: -0.05, ci_low: -0.07, ci_high: -0.03, method: "newcombe", ci_level: 0.95 } },
  segments: {
    label: "Exploratory",
    method: "benjamini-hochberg",
    items: {
      "New customers": { n: 500, difference: { value: -0.08, ci_low: -0.15, ci_high: -0.01, method: "newcombe", ci_level: 0.95 }, p_adjusted: 0.04 },
      Tiny: { n: 3, skipped: "one arm is empty" },
    },
  },
  srm: { failed: true, p_value: 0.0001, observed_control_share: 0.4, planned_control_share: 0.5 },
  guardrails: { complaints: { breached: false }, arpu: { breached: true } },
} as unknown as Analysis;

describe("experiments helpers", () => {
  it("builds forest rows: overall first, skipped segments left out", () => {
    const rows = forestRows(analysis);
    expect(rows.map((r) => r.label)).toEqual(["All assigned (ITT)", "New customers"]);
    expect(rows[0].primary).toBe(true);
    expect(rows[1].note).toBe("adj. p 0.040");
  });

  it("keeps zero on the axis and positions values", () => {
    const domain = axisDomain([-0.07, -0.03]);
    expect(domain[0]).toBeLessThan(-0.07);
    expect(domain[1]).toBeGreaterThan(0);
    expect(position(domain[0], domain)).toBe(0);
    expect(position(domain[1], domain)).toBe(100);
  });

  it("describes segments and statuses", () => {
    expect(filterText({ column: "tenure", op: "lte", value: 12 })).toBe("tenure ≤ 12");
    expect(segmentText([])).toBe("All customers");
    expect(segmentText([{ column: "Contract", op: "in", value: ["One year", "Two year"] }])).toBe(
      "Contract in One year, Two year",
    );
    expect(statusInfo("running").label).toBe("Running");
    expect(statusInfo("unknown").label).toBe("unknown");
  });

  it("puts SRM, balance and guardrails in the health strip", () => {
    const exp = {
      analysis,
      assignment_summary: { balance: { balanced: false, flagged: ["tenure"] } },
    } as unknown as Experiment;
    const items = healthItems(exp);
    expect(items.map((i) => [i.label, i.ok])).toEqual([
      ["Sample ratio", false],
      ["Balance", false],
      ["Complaints guardrail", true],
      ["ARPU guardrail", false],
    ]);
    expect(items[1].detail).toContain("tenure");
  });
});
