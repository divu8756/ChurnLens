import { describe, expect, it } from "vitest";

import type { ScoreSet } from "./api";
import { calibrationTraces, isEdited, liftTraces, prTraces, rocTraces, sameAssumptions } from "./metrics";

const scores = {
  n: 4,
  churn_rate: 0.25,
  roc_auc: 0.8,
  pr_auc: 0.6,
  brier: 0.1,
  top_10pct: { share: 0.1, k: 1, churners_in_top: 1, precision: 1, recall: 1 },
  deciles: [
    { decile: 1, n: 2, churners: 1, churn_rate: 0.5, lift: 2, cumulative_gain: 1, cumulative_share: 0.5 },
    { decile: 2, n: 2, churners: 0, churn_rate: 0, lift: 0, cumulative_gain: 1, cumulative_share: 1 },
  ],
  calibration: [
    { bin: 1, low: 0, high: 0.1, n: 0, mean_predicted: null, observed_rate: null },
    { bin: 2, low: 0.1, high: 0.2, n: 3, mean_predicted: 0.15, observed_rate: 0.2 },
  ],
  roc_curve: { fpr: [0, 0.5, 1], tpr: [0, 0.9, 1] },
  pr_curve: { recall: [0, 1], precision: [1, 0.25] },
} as ScoreSet;

describe("metrics helpers", () => {
  it("builds curves straight from the API values with a baseline", () => {
    const [model, random] = rocTraces(scores);
    expect(model.x).toEqual([0, 0.5, 1]);
    expect(random.y).toEqual([0, 1]);
    expect(prTraces(scores)[1].y).toEqual([0.25, 0.25]); // random = churn rate
  });

  it("puts lift and cumulative gain on two axes", () => {
    const [lift, gains] = liftTraces(scores);
    expect(lift.x).toEqual(["D1", "D2"]);
    expect(lift.y).toEqual([2, 0]);
    expect(gains.yaxis).toBe("y2");
  });

  it("drops empty calibration bins and keeps the perfect line", () => {
    const traces = calibrationTraces(scores, scores);
    expect(traces[0].name).toBe("Perfect");
    expect(traces[1].x).toEqual([0.15]);
    expect(traces[1].text).toEqual(["3 customers"]);
  });

  it("knows when assumptions were edited and when two sets match", () => {
    expect(isEdited({})).toBe(false);
    expect(isEdited({ offers: { A: { cost: null } } })).toBe(false);
    expect(isEdited({ months_remaining: 24 })).toBe(true);
    expect(isEdited({ offers: { A: { cost: 3 } } })).toBe(true);
    expect(sameAssumptions({ months_remaining: 24, power: 0.9 }, { power: 0.9, months_remaining: 24 })).toBe(true);
    expect(sameAssumptions({ months_remaining: 24 }, {})).toBe(false);
  });
});
