import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MAX_RECONNECTS, RECONNECT_BASE_MS, useProgressStream } from "./use-progress-stream";

type Listener = (event: MessageEvent<string>) => void;

class FakeEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  static instances: FakeEventSource[] = [];

  readonly url: string;
  readyState = FakeEventSource.CONNECTING;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private listeners = new Map<string, Listener[]>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(name: string, listener: Listener) {
    this.listeners.set(name, [...(this.listeners.get(name) ?? []), listener]);
  }

  close() {
    this.readyState = FakeEventSource.CLOSED;
  }

  // Test helpers
  open() {
    this.readyState = FakeEventSource.OPEN;
    this.onopen?.();
  }

  emit(name: string, data: unknown, id = "") {
    const message = { data: JSON.stringify(data), lastEventId: id } as MessageEvent<string>;
    for (const listener of this.listeners.get(name) ?? []) listener(message);
  }

  fail(readyState: number) {
    this.readyState = readyState;
    this.onerror?.();
  }
}

const latest = () => FakeEventSource.instances[FakeEventSource.instances.length - 1];
const fetchMock = vi.fn<(input: string) => Promise<Response>>();

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.useFakeTimers();
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("useProgressStream", () => {
  it("does nothing without a session", () => {
    const { result } = renderHook(() => useProgressStream(null));
    expect(FakeEventSource.instances).toHaveLength(0);
    expect(result.current.connection).toBe("connecting");
  });

  it("parses each event type", () => {
    const { result } = renderHook(() => useProgressStream("abc"));
    const source = latest();
    expect(source.url).toMatch(/\/stream\/abc$/);
    act(() => {
      source.open();
      source.emit("node_start", { node: "ingest" }, "1");
      source.emit("node_finish", { node: "ingest", status: "done", detail: "ok" }, "2");
      source.emit("error", { node: "schema_agent", message: "LLM fallback", fatal: false }, "3");
      source.emit("awaiting_confirmation", { proposal: { columns: [], source: "rules" } }, "4");
      source.emit("heartbeat", {});
    });
    expect(result.current.connection).toBe("open");
    expect(result.current.nodes.ingest).toEqual({ status: "done", detail: "ok" });
    expect(result.current.errors).toHaveLength(1);
    expect(result.current.awaitingConfirmation).toBe(true);
    expect(result.current.proposal).toEqual({ columns: [], source: "rules" });
    expect(result.current.lastEventId).toBe(4);

    act(() => {
      source.emit("resumed", {}, "5");
      source.emit("done", { ok: true, final_error: null }, "6");
    });
    expect(result.current.awaitingConfirmation).toBe(false);
    expect(result.current.done).toEqual({ ok: true, final_error: null });
    expect(result.current.connection).toBe("closed");
    expect(source.readyState).toBe(FakeEventSource.CLOSED);
  });

  it("maps a 410 to the expired state and stops", async () => {
    fetchMock.mockResolvedValue(new Response('{"detail":"Session expired, please re-upload."}', { status: 410 }));
    const { result } = renderHook(() => useProgressStream("gone"));
    await act(async () => {
      latest().fail(FakeEventSource.CLOSED);
    });
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(result.current.connection).toBe("expired");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(FakeEventSource.instances).toHaveLength(1);
  });

  it("reconnects after the last event seen", async () => {
    const { result } = renderHook(() => useProgressStream("abc"));
    act(() => {
      latest().open();
      latest().emit("node_start", { node: "ingest" }, "7");
      latest().fail(FakeEventSource.CONNECTING);
    });
    expect(result.current.connection).toBe("reconnecting");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(RECONNECT_BASE_MS);
    });
    expect(FakeEventSource.instances).toHaveLength(2);
    expect(latest().url).toMatch(/\/stream\/abc\?after=7$/);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it(`gives up after ${MAX_RECONNECTS} failed reconnects in a row`, async () => {
    fetchMock.mockImplementation(async () => new Response("", { status: 502 }));
    const { result } = renderHook(() => useProgressStream("abc"));
    for (let i = 0; i < MAX_RECONNECTS; i += 1) {
      await act(async () => {
        latest().fail(FakeEventSource.CLOSED);
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(20_000);
      });
    }
    expect(FakeEventSource.instances).toHaveLength(MAX_RECONNECTS + 1);
    await act(async () => {
      latest().fail(FakeEventSource.CLOSED);
    });
    expect(result.current.connection).toBe("lost");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(FakeEventSource.instances).toHaveLength(MAX_RECONNECTS + 1);
  });

  it("resets the reconnect budget when an event arrives", async () => {
    renderHook(() => useProgressStream("abc"));
    for (let i = 0; i < MAX_RECONNECTS + 2; i += 1) {
      act(() => {
        latest().fail(FakeEventSource.CONNECTING);
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(20_000);
      });
      act(() => {
        latest().emit("heartbeat", {});
      });
    }
    expect(FakeEventSource.instances).toHaveLength(MAX_RECONNECTS + 3);
  });

  it("closes the stream on unmount", () => {
    const { unmount } = renderHook(() => useProgressStream("abc"));
    const source = latest();
    unmount();
    expect(source.readyState).toBe(FakeEventSource.CLOSED);
  });
});
