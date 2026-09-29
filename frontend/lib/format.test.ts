import { describe, expect, it } from "vitest";

import { formatCount, formatMoney, formatP, formatPercent, formatStat } from "./format";

describe("format", () => {
  it("formats counts", () => {
    expect(formatCount(7000)).toBe("7,000");
    expect(formatCount(null)).toBe("–");
  });

  it("formats fractions as percentages", () => {
    expect(formatPercent(0.25657142857)).toBe("25.66%");
    expect(formatPercent(1)).toBe("100.00%");
    expect(formatPercent(0.5, 0)).toBe("50%");
    expect(formatPercent(Number.NaN)).toBe("–");
  });

  it("formats statistics to 2 dp", () => {
    expect(formatStat(0.8308140608)).toBe("0.83");
    expect(formatStat(undefined)).toBe("–");
  });

  it("shows tiny p-values as < 0.001", () => {
    expect(formatP(1.171e-202)).toBe("< 0.001");
    expect(formatP(0.0009999)).toBe("< 0.001");
    expect(formatP(0.001)).toBe("0.001");
    expect(formatP(0.29012)).toBe("0.290");
  });

  it("formats money", () => {
    expect(formatMoney(142056.33)).toBe("142,056");
    expect(formatMoney(64.5)).toBe("64.50");
    expect(formatMoney(null)).toBe("–");
  });
});
