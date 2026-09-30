"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { ApiError, askData, getChatHistory, type ChatMessage } from "@/lib/api";

import { Alert, Button, Card, Spinner } from "../ui";

const EXAMPLES = [
  "What is the overall churn rate?",
  "Churn rate by Contract for customers with tenure under 12 months",
  "Is PaymentMethod significantly related to churn?",
  "Describe segment 1",
];

const STATUS_NOTE: Record<string, string> = {
  refused: "Declined: not about this dataset or against the rules.",
  unverified: "The draft answer used numbers not found in the analysis, so it was withheld.",
  limit: "Stopped after the maximum number of lookups.",
  unavailable: "The AI service was unavailable.",
};

function toolLabel(t: NonNullable<ChatMessage["tools_used"]>[number]): string {
  const args = Object.entries(t.args ?? {})
    .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(", ");
  return `${t.tool}(${args})`;
}

function Message({ message }: { message: ChatMessage }) {
  const user = message.role === "user";
  const tools = message.tools_used ?? [];
  return (
    <li className={`flex ${user ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-xl px-3 py-2 text-sm ${
          user ? "bg-blue-600 text-white" : "border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-950"
        }`}
      >
        <p className="whitespace-pre-wrap">{message.text}</p>
        {!user && message.status && STATUS_NOTE[message.status] ? (
          <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">{STATUS_NOTE[message.status]}</p>
        ) : null}
        {!user && tools.length ? (
          <details className="mt-1 text-xs text-gray-500">
            <summary className="cursor-pointer">
              Tools used: {Array.from(new Set(tools.map((t) => t.tool))).join(", ")}
            </summary>
            <ul className="mt-1 flex flex-col gap-0.5 break-all font-mono">
              {tools.map((t, i) => (
                <li key={i}>
                  {toolLabel(t)}
                  {t.error ? <span className="text-red-700 dark:text-red-300"> → {t.error}</span> : null}
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </div>
    </li>
  );
}

export function ChatTab({ sessionId }: { sessionId: string }) {
  const [messages, setMessages] = useState<ChatMessage[] | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    getChatHistory(sessionId, controller.signal)
      .then(setMessages)
      .catch(() => {
        if (!controller.signal.aborted) setMessages([]);
      });
    return () => controller.abort();
  }, [sessionId]);

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "nearest" });
  }, [messages, busy]);

  const send = async (text: string) => {
    const question = text.trim();
    if (!question || busy) return;
    setBusy(true);
    setError(null);
    setMessages((m) => [...(m ?? []), { role: "user", text: question, tools_used: [] }]);
    setDraft("");
    try {
      const res = await askData(sessionId, question);
      setMessages(res.history);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not get an answer.");
      setMessages((m) => (m ?? []).slice(0, -1));
      setDraft(question);
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void send(draft);
  };

  return (
    <Card title="Ask the Data">
      <div className="flex flex-col gap-4">
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Answers come only from the computed analysis through a few whitelisted lookups; the tools used are shown under
          each answer. The AI never sees your raw rows.
        </p>
        {messages === null ? <Spinner label="Loading the conversation..." /> : null}
        {messages?.length === 0 ? (
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => void send(q)}
                className="rounded-full border border-gray-300 px-3 py-1 text-xs hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-900"
              >
                {q}
              </button>
            ))}
          </div>
        ) : null}
        <ol className="flex flex-col gap-3" aria-live="polite" aria-label="Conversation">
          {(messages ?? []).map((m, i) => (
            <Message key={i} message={m} />
          ))}
        </ol>
        {busy ? <Spinner label="Looking it up..." /> : null}
        {error ? <Alert tone="error" title={error} /> : null}
        <div ref={end} />
        <form onSubmit={onSubmit} className="flex gap-2">
          <label className="sr-only" htmlFor={`chat-${sessionId}`}>
            Your question
          </label>
          <input
            id={`chat-${sessionId}`}
            className="min-h-10 flex-1 rounded-lg border border-gray-300 bg-white px-3 text-sm dark:border-gray-700 dark:bg-gray-900"
            placeholder="Ask about this data..."
            value={draft}
            maxLength={1000}
            onChange={(e) => setDraft(e.target.value)}
            disabled={busy}
          />
          <Button type="submit" disabled={busy || !draft.trim()}>
            Ask
          </Button>
        </form>
      </div>
    </Card>
  );
}
