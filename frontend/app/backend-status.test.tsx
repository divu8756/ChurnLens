import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BackendStatus, GIVE_UP_AFTER_MS } from "./backend-status";

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const ok = () => new Response(JSON.stringify({ status: "ok", version: "0.1.0" }), {
  status: 200,
  headers: { "Content-Type": "application/json" },
});

describe("BackendStatus", () => {
  it("says the server is waking up, keeps trying, then shows online", async () => {
    let calls = 0;
    vi.stubGlobal("fetch", vi.fn(async () => {
      calls += 1;
      if (calls < 3) throw new TypeError("Failed to fetch"); // still asleep
      return ok();
    }));
    render(<BackendStatus />);
    expect(screen.getByTestId("backend-status").textContent).toContain("checking");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_100);
    });
    expect(screen.getByTestId("backend-status").textContent).toContain("Waking up the server (up to a minute)");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    expect(screen.getByTestId("backend-status").textContent).toContain("Backend: online");
    expect(calls).toBe(3);
  });

  it("gives up after the limit and says so", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    }));
    render(<BackendStatus />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(GIVE_UP_AFTER_MS + 5_000);
    });
    expect(screen.getByTestId("backend-status").textContent).toContain("offline");
  });
});
