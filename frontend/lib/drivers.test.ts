import { describe, expect, it } from "vitest";

import { beeswarmPoints, forestAxis, forestRows, shortLabel, topImportance, type OddsRatioTerm } from "./drivers";

const term = (label: string, or: number | null, lo: number | null, hi: number | null, p: number | null): OddsRatioTerm => ({
  feature: label,
  kind: "categorical",
  label,
  term: label,
  odds_ratio: or,
  ci_lower: lo,
  ci_upper: hi,
  p_value: p,
});

describe("forestRows", () => {
  it("keeps complete terms, strongest evidence first, with whisker lengths", () => {
    const rows = forestRows([
      term("weak", 1.1, 0.9, 1.3, 0.2),
      term("strong", 0.08, 0.06, 0.11, 1e-51),
      term("no CI", 2, null, null, 0.01),
    ]);
    expect(rows.map((r) => r.label)).toEqual(["strong", "weak"]);
    expect(rows[0].whisker[0]).toBeCloseTo(0.02, 12);
    expect(rows[0].whisker[1]).toBeCloseTo(0.03, 12);
  });

  it("caps the number of rows", () => {
    const many = Array.from({ length: 30 }, (_, i) => term(`t${i}`, 1.5, 1.2, 1.8, i / 100));
    expect(forestRows(many, 5)).toHaveLength(5);
  });
});

describe("forestAxis", () => {
  it("covers every whisker and 1 with round log ticks", () => {
    const rows = forestRows([term("a", 0.08, 0.057, 0.11, 1e-9), term("b", 1.9, 1.4, 2.6, 1e-4)]);
    const axis = forestAxis(rows);
    expect(axis.domain).toEqual([0.05, 5]);
    expect(axis.ticks).toEqual([0.05, 0.1, 0.2, 0.5, 1, 2, 5]);
  });

  it("always includes 1", () => {
    expect(forestAxis(forestRows([term("a", 1.5, 1.2, 1.8, 0.01)])).domain).toEqual([1, 2]);
  });
});

describe("shortLabel", () => {
  it("keeps short labels and trims long ones", () => {
    expect(shortLabel("tenure")).toBe("tenure");
    expect(shortLabel("DataUsageChange3mPct (per 1 SD)", 12)).toBe("DataUsageCh…");
  });
});

describe("topImportance", () => {
  it("orders by rank and caps", () => {
    const items = [3, 1, 2].map((rank) => ({ feature: `f${rank}`, importance_mean: 1 / rank, importance_std: 0, rank }));
    expect(topImportance(items, 2).map((i) => i.feature)).toEqual(["f1", "f2"]);
  });
});

describe("beeswarmPoints", () => {
  it("puts the first feature on the top row and colours numerics low to high", () => {
    const { points, levels } = beeswarmPoints([
      { feature: "tenure", kind: "numeric", points: [{ shap: 1, value: 1 }, { shap: -1, value: 72 }] },
      { feature: "Contract", kind: "categorical", points: [{ shap: 0.7, value: "Month-to-month" }, { shap: -1.8, value: "Two year" }] },
    ]);
    const tenure = points.filter((p) => p.label.startsWith("tenure"));
    expect(tenure.map((p) => p.tone)).toEqual([0, 1]);
    expect(Math.round(tenure[0].row)).toBe(1);
    expect(levels.Contract).toEqual(["Month-to-month", "Two year"]);
    expect(points.every((p) => Math.abs(p.row - Math.round(p.row)) <= 0.3 + 1e-9)).toBe(true);
  });
});
