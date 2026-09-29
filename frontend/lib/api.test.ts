import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, confirmSchema, getResults, parseErrorDetail, streamUrl, toApiError } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

const json = (body: unknown, status: number) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("toApiError", () => {
  it("maps 410 to the expired kind", async () => {
    const error = await toApiError(json({ detail: "Session expired, please re-upload." }, 410));
    expect(error).toBeInstanceOf(ApiError);
    expect(error.kind).toBe("expired");
    expect(error.status).toBe(410);
    expect(error.message).toBe("Session expired, please re-upload.");
  });

  it.each([
    [409, "conflict"],
    [413, "client"],
    [422, "validation"],
    [503, "server"],
  ])("maps HTTP %i to %s", async (status, kind) => {
    expect((await toApiError(json({ detail: "x" }, status))).kind).toBe(kind);
  });

  it("keeps a non-JSON body as a generic message", async () => {
    const error = await toApiError(new Response("<html>Bad gateway</html>", { status: 502 }));
    expect(error.message).toBe("Request failed with HTTP 502");
  });
});

describe("parseErrorDetail", () => {
  it("reads schema problems", () => {
    expect(parseErrorDetail({ detail: { message: "The schema needs changes.", problems: ["a", "b"] } }, "f")).toEqual({
      message: "The schema needs changes.",
      problems: ["a", "b"],
    });
  });

  it("reads FastAPI validation errors", () => {
    const body = { detail: [{ loc: ["body", "target_column"], msg: "Field required" }] };
    expect(parseErrorDetail(body, "f").problems).toEqual(["target_column: Field required"]);
  });
});

describe("requests", () => {
  it("sends the confirmed schema as JSON and surfaces 422 problems", async () => {
    const fetchMock = vi.fn(async () => json({ detail: { message: "Needs changes.", problems: ["bad target"] } }, 422));
    vi.stubGlobal("fetch", fetchMock);
    const schema = { target_column: "Churn", positive_label: "Yes" };
    const error = await confirmSchema("s1", schema).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).problems).toEqual(["bad target"]);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/\/confirm-schema\/s1$/);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual(schema);
  });

  it("builds the results query", async () => {
    const fetchMock = vi.fn(async () => json({}, 200));
    vi.stubGlobal("fetch", fetchMock);
    await getResults("s1", { page: 2, band: "High" });
    const [url] = fetchMock.mock.calls[0] as unknown as [string];
    expect(url).toMatch(/\/results\/s1\?page=2&band=High$/);
  });

  it("reports network failures as ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    await expect(getResults("s1")).rejects.toMatchObject({ kind: "network" });
  });
});

describe("streamUrl", () => {
  it("adds after only when resuming", () => {
    expect(streamUrl("s1")).toMatch(/\/stream\/s1$/);
    expect(streamUrl("s1", 4)).toMatch(/\/stream\/s1\?after=4$/);
  });
});
