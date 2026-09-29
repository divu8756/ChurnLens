import { describe, expect, it } from "vitest";

import { curveSeries, distinctiveFeatures, divergingColour, orderByEvidence, topCorrelations, type HypothesisTest, type Segment } from "./insights";

describe("orderByEvidence", () => {
  it("puts the columns with the smallest adjusted p first", () => {
    const tests = [
      { variable: "gender", p_adjusted: 0.4 },
      { variable: "Contract", p_adjusted: 1e-200 },
    ] as HypothesisTest[];
    expect(orderByEvidence(["gender", "Region", "Contract"], tests)).toEqual(["Contract", "gender", "Region"]);
  });
});

describe("topCorrelations", () => {
  it("keeps the columns most correlated with churn and their sub-matrix", () => {
    const corr = {
      columns: ["a", "b", "c"],
      matrix: [
        [1, 0.2, -0.5],
        [0.2, 1, 0.1],
        [-0.5, 0.1, 1],
      ],
      with_target: { a: 0.05, b: -0.3, c: 0.25 },
    };
    expect(topCorrelations(corr, 2)).toEqual({
      columns: ["b", "c"],
      matrix: [
        [1, 0.1],
        [0.1, 1],
      ],
    });
  });
});

describe("divergingColour", () => {
  it("is light at 0 and saturated at the ends", () => {
    expect(divergingColour(0)).toBe("rgb(245, 245, 245)");
    expect(divergingColour(1)).toBe("rgb(213, 94, 0)");
    expect(divergingColour(-1)).toBe("rgb(0, 114, 178)");
    expect(divergingColour(null)).toBe("transparent");
  });
});

describe("distinctiveFeatures", () => {
  it("returns the largest absolute z-scores first", () => {
    const segment = {
      feature_z: { a: 0.1, b: -2.1, c: 1.4, d: null },
      feature_means: { a: 1, b: 2, c: 3, d: null },
    } as unknown as Segment;
    expect(distinctiveFeatures(segment, 2)).toEqual([
      { feature: "b", z: -2.1, mean: 2 },
      { feature: "c", z: 1.4, mean: 3 },
    ]);
  });
});

describe("curveSeries", () => {
  it("pairs times with survival and assigns colours", () => {
    const series = curveSeries([
      { label: "All", n: 2, events: 1, median_reached: false, curve: { time: [0, 5], survival: [1, 0.8], ci_lower: [1, 0.7], ci_upper: [1, 0.9] } },
    ]);
    expect(series[0].points).toEqual([
      { time: 0, survival: 1 },
      { time: 5, survival: 0.8 },
    ]);
    expect(series[0].colour).toBe("#0072B2");
  });
});
