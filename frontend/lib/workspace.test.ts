import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.resetModules();
  window.localStorage.clear();
});

describe("workspaceKey", () => {
  it("creates one valid key per browser and keeps it", async () => {
    const { workspaceKey } = await import("./workspace");
    const key = workspaceKey();
    expect(key).toMatch(/^[a-f0-9]{48}$/);
    expect(workspaceKey()).toBe(key);
    vi.resetModules();
    const again = await import("./workspace");
    expect(again.workspaceKey()).toBe(key); // survives a reload via localStorage
  });

  it("still works when storage is blocked", async () => {
    const spy = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const { workspaceKey } = await import("./workspace");
    const key = workspaceKey();
    expect(key).toMatch(/^[a-f0-9]{48}$/);
    expect(workspaceKey()).toBe(key);
    spy.mockRestore();
  });
});
