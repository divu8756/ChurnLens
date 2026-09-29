import { describe, expect, it } from "vitest";

import { predictionsCsvUrl } from "./api";
import { parseReason } from "./predictions";

describe("parseReason", () => {
  it("splits text and signed contribution", () => {
    expect(parseReason("Contract: Month-to-month (+0.74)")).toEqual({ text: "Contract: Month-to-month", contribution: "+0.74", raises: true });
    expect(parseReason("tenure = 72 (-1.70)")).toEqual({ text: "tenure = 72", contribution: "-1.70", raises: false });
  });

  it("keeps odd text as is", () => {
    expect(parseReason("something else")).toEqual({ text: "something else", contribution: "", raises: true });
  });
});

describe("predictionsCsvUrl", () => {
  it("carries the current filter", () => {
    expect(predictionsCsvUrl("s1")).toMatch(/\/predictions\/s1\/csv$/);
    expect(predictionsCsvUrl("s1", { band: "High", q: " c01 " })).toMatch(/\/predictions\/s1\/csv\?band=High&q=c01$/);
  });
});
