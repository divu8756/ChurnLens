import { describe, expect, it } from "vitest";

import { initialProgress, parseStreamMessage, progressReducer, type ProgressAction } from "./progress";

const event = (name: Parameters<typeof parseStreamMessage>[0], data: unknown, id: number | null = null): ProgressAction => ({
  type: "event",
  name,
  data,
  id,
});

const run = (...actions: ProgressAction[]) => actions.reduce(progressReducer, initialProgress);

describe("progressReducer", () => {
  it("tracks node start and finish in first-seen order", () => {
    const state = run(
      event("node_start", { node: "ingest" }, 1),
      event("node_finish", { node: "ingest", status: "done", detail: "7,014 rows" }, 2),
      event("node_start", { node: "schema_agent" }, 3),
    );
    expect(state.order).toEqual(["ingest", "schema_agent"]);
    expect(state.nodes.ingest).toEqual({ status: "done", detail: "7,014 rows" });
    expect(state.nodes.schema_agent).toEqual({ status: "running", detail: null });
    expect(state.connection).toBe("open");
    expect(state.lastEventId).toBe(3);
  });

  it("keeps skipped and failed node statuses", () => {
    const state = run(
      event("node_finish", { node: "survival", status: "skipped", detail: "no time column" }),
      event("node_finish", { node: "segmentation", status: "failed", detail: null }),
    );
    expect(state.nodes.survival.status).toBe("skipped");
    expect(state.nodes.segmentation.status).toBe("failed");
  });

  it("collects errors", () => {
    const state = run(event("error", { node: "schema_agent", message: "LLM fallback", fatal: false }));
    expect(state.errors).toEqual([{ node: "schema_agent", message: "LLM fallback", fatal: false }]);
  });

  it("stores the proposal while awaiting confirmation and clears the flag on resume", () => {
    const proposal = { columns: [], target_column: "Churn", positive_label: "Yes", source: "rules" };
    const paused = run(event("awaiting_confirmation", { proposal }, 5));
    expect(paused.awaitingConfirmation).toBe(true);
    expect(paused.proposal).toEqual(proposal);
    const resumed = progressReducer(paused, event("resumed", {}, 6));
    expect(resumed.awaitingConfirmation).toBe(false);
    expect(resumed.proposal).toEqual(proposal);
  });

  it("ignores heartbeats apart from resetting the reconnect budget", () => {
    const reconnecting = run({ type: "reconnecting" }, { type: "reconnecting" });
    expect(reconnecting.reconnectAttempts).toBe(2);
    const state = progressReducer(reconnecting, event("heartbeat", {}));
    expect(state.reconnectAttempts).toBe(0);
    expect(state.connection).toBe("open");
    expect(state.nodes).toEqual({});
  });

  it("closes on done and keeps the outcome", () => {
    const state = run(event("done", { ok: false, final_error: "Only one class in the target." }, 9));
    expect(state.done).toEqual({ ok: false, final_error: "Only one class in the target." });
    expect(state.connection).toBe("closed");
  });

  it("maps expiry and lost connections", () => {
    expect(run({ type: "expired" }).connection).toBe("expired");
    expect(run({ type: "lost" }).connection).toBe("lost");
  });
});

describe("parseStreamMessage", () => {
  it("parses data and numeric ids", () => {
    expect(parseStreamMessage("node_start", { data: '{"node":"eda"}', lastEventId: "12" })).toEqual(
      event("node_start", { node: "eda" }, 12),
    );
  });

  it("treats empty data as {} and a missing id as null", () => {
    expect(parseStreamMessage("heartbeat", { data: "", lastEventId: "" })).toEqual(event("heartbeat", {}, null));
  });

  it("drops malformed JSON", () => {
    expect(parseStreamMessage("node_start", { data: "{oops", lastEventId: "1" })).toBeNull();
    expect(parseStreamMessage("node_start", { data: "42", lastEventId: "1" })).toBeNull();
  });
});
