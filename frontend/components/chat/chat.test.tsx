import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatTab } from "./chat-tab";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("ChatTab", () => {
  it("sends a question and shows the answer with the tools used", async () => {
    const answer = {
      role: "assistant",
      text: "Overall churn is 25.66% (from get_stat).",
      status: "answered",
      tools_used: [{ tool: "get_stat", args: { key: "impact_estimates.overall.churn_rate" }, error: null }],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) =>
        init?.method === "POST"
          ? json({ answer, history: [{ role: "user", text: "What is the churn rate?", tools_used: [] }, answer] })
          : json([]),
      ),
    );
    render(<ChatTab sessionId={"a".repeat(32)} />);
    fireEvent.click(await screen.findByRole("button", { name: "What is the overall churn rate?" }));
    expect(await screen.findByText("Overall churn is 25.66% (from get_stat).")).toBeTruthy();
    expect(screen.getByText("Tools used: get_stat")).toBeTruthy();
    expect(screen.getByText(/get_stat\(key=impact_estimates.overall.churn_rate\)/)).toBeTruthy();
  });

  it("explains a refusal and keeps the question after an error", async () => {
    let calls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) => {
        if (init?.method !== "POST") return json([]);
        calls += 1;
        if (calls === 1) return json({ detail: "Too many chat requests; try again in 5 s." }, 429);
        const answer = { role: "assistant", text: "I can only help with this dataset.", status: "refused", tools_used: [] };
        return json({ answer, history: [{ role: "user", text: "weather?", tools_used: [] }, answer] });
      }),
    );
    render(<ChatTab sessionId={"a".repeat(32)} />);
    const input = await screen.findByRole("textbox", { name: "Your question" });
    fireEvent.change(input, { target: { value: "weather?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText(/Too many chat requests/)).toBeTruthy();
    expect((input as HTMLInputElement).value).toBe("weather?");
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText(/Declined: not about this dataset/)).toBeTruthy();
  });
});
