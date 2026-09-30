"use client";

import { useEffect, useState } from "react";

import { getHealth } from "@/lib/api";

type Status = "checking" | "waking" | "online" | "offline";

/** The free backend sleeps when idle and takes up to a minute to wake: keep trying. */
export const WAKING_AFTER_MS = 3_000;
export const GIVE_UP_AFTER_MS = 90_000;
const ATTEMPT_TIMEOUT_MS = 15_000;
const RETRY_DELAY_MS = 2_000;

export function BackendStatus() {
  const [status, setStatus] = useState<Status>("checking");
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    let stopped = false;
    const started = Date.now();
    const waking = setTimeout(() => {
      if (!stopped) setStatus((s) => (s === "checking" ? "waking" : s));
    }, WAKING_AFTER_MS);

    const attempt = async () => {
      while (!stopped) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), ATTEMPT_TIMEOUT_MS);
        try {
          const health = await getHealth(controller.signal);
          if (stopped) return;
          setVersion(health.version);
          setStatus(health.status === "ok" ? "online" : "offline");
          return;
        } catch {
          if (stopped) return;
          if (Date.now() - started >= GIVE_UP_AFTER_MS) {
            setStatus("offline");
            return;
          }
          await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
        } finally {
          clearTimeout(timer);
        }
      }
    };
    void attempt().finally(() => clearTimeout(waking));
    return () => {
      stopped = true;
      clearTimeout(waking);
    };
  }, []);

  const colour =
    status === "online" ? "bg-green-600" : status === "offline" ? "bg-red-600" : "bg-amber-500";
  const text = {
    checking: "Backend: checking...",
    waking: "Waking up the server (up to a minute)...",
    online: "Backend: online",
    offline: "Backend: offline. Reload the page to try again.",
  }[status];

  return (
    <p className="flex items-center gap-2 text-sm" data-testid="backend-status" role="status">
      <span
        className={`inline-block h-2.5 w-2.5 rounded-full ${colour} ${status === "waking" ? "animate-pulse" : ""}`}
        aria-hidden
      />
      {text}
      {version ? <span className="text-gray-500">(v{version})</span> : null}
    </p>
  );
}
