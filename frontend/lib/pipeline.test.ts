import { describe, expect, it } from "vitest";

import { cleaningFinished, stepperStages } from "./pipeline";
import { initialProgress, type ProgressState } from "./progress";

const state = (patch: Partial<ProgressState>): ProgressState => ({ ...initialProgress, ...patch });
const flat = (s: ProgressState) => Object.fromEntries(stepperStages(s).flat().map((step) => [step.node, step.status]));

describe("stepperStages", () => {
  it("starts with every step pending and parallel nodes grouped", () => {
    const stages = stepperStages(initialProgress);
    expect(stages.flat().every((step) => step.status === "pending")).toBe(true);
    expect(stages[4].map((step) => step.node)).toEqual(["eda", "segmentation", "survival", "hypothesis"]);
  });

  it("shows running, done and waiting", () => {
    const s = state({
      nodes: {
        ingest: { status: "done", detail: null },
        schema_agent: { status: "done", detail: null },
        human_review: { status: "running", detail: null },
      },
      awaitingConfirmation: true,
    });
    const statuses = flat(s);
    expect(statuses.ingest).toBe("done");
    expect(statuses.human_review).toBe("waiting");
    expect(statuses.cleaning).toBe("pending");
  });

  it("marks nodes that never ran as skipped once the run is done", () => {
    const s = state({ nodes: { eda: { status: "done", detail: null } }, done: { ok: true, final_error: null } });
    expect(flat(s).survival).toBe("skipped");
    expect(flat(s).eda).toBe("done");
  });
});

describe("cleaningFinished", () => {
  it("is true only after cleaning is done", () => {
    expect(cleaningFinished(initialProgress)).toBe(false);
    expect(cleaningFinished(state({ nodes: { cleaning: { status: "running", detail: null } } }))).toBe(false);
    expect(cleaningFinished(state({ nodes: { cleaning: { status: "done", detail: null } } }))).toBe(true);
  });
});
