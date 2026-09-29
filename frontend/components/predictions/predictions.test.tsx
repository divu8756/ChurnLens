import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PredictionsResponse } from "@/lib/api";
import type { ResultsPayload } from "@/lib/results";

import { PredictionsTab } from "./predictions-tab";

const results = {
  model_metrics: {
    risk_bands: { thresholds: { high: 0.6, medium: 0.3 }, band_counts: { High: 2, Medium: 1, Low: 0 }, total: 3 },
  },
} as unknown as ResultsPayload;

const page = (over: Partial<PredictionsResponse> = {}): PredictionsResponse => ({
  page: 1,
  page_size: 50,
  total: 120,
  pages: 3,
  items: [
    { customer_id: "C00001", churn_probability: 0.912, risk_band: "High", actual_churn: 1, reason_1: "Contract: Month-to-month (+0.74)", reason_2: "tenure = 72 (-1.70)", reason_3: null },
  ],
  ...over,
});

const fetchMock = vi.fn<(url: string) => Promise<Response>>();

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  fetchMock.mockReset();
  fetchMock.mockImplementation(async () => new Response(JSON.stringify(page()), { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const lastUrl = () => String(fetchMock.mock.calls[fetchMock.mock.calls.length - 1][0]);

describe("PredictionsTab", () => {
  it("shows rows with formatted probability and reason chips", async () => {
    render(<PredictionsTab results={results} sessionId="s1" />);
    expect(await screen.findByText("C00001")).toBeTruthy();
    expect(screen.getByText("91.2%")).toBeTruthy();
    expect(screen.getByText("Contract: Month-to-month")).toBeTruthy();
    expect(screen.getByText("-1.70")).toBeTruthy();
    expect(screen.getByText("1–50 of 120")).toBeTruthy();
  });

  it("filters by band from page 1 and pages forward", async () => {
    render(<PredictionsTab results={results} sessionId="s1" />);
    await screen.findByText("C00001");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await vi.waitFor(() => expect(lastUrl()).toMatch(/page=2/));
    fireEvent.click(screen.getByRole("button", { name: /High/ }));
    await vi.waitFor(() => expect(lastUrl()).toMatch(/\?page=1&band=High$/));
    expect(screen.getByRole("link", { name: "Download CSV" }).getAttribute("href")).toMatch(/\/predictions\/s1\/csv\?band=High$/);
  });

  it("debounces the ID search", async () => {
    render(<PredictionsTab results={results} sessionId="s1" />);
    await screen.findByText("C00001");
    const calls = fetchMock.mock.calls.length;
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "c000" } });
    expect(fetchMock.mock.calls.length).toBe(calls);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(350);
    });
    await vi.waitFor(() => expect(lastUrl()).toMatch(/q=c000/));
  });

  it("shows an empty state for a search with no match", async () => {
    fetchMock.mockImplementation(async () => new Response(JSON.stringify(page({ total: 0, pages: 1, items: [] })), { status: 200 }));
    render(<PredictionsTab results={results} sessionId="s1" />);
    expect(await screen.findByText("No customers in this band.")).toBeTruthy();
  });
});
