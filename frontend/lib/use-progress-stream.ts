"use client";

import { useEffect, useReducer, useRef } from "react";

import { streamUrl } from "./api";
import { STREAM_EVENTS, initialProgress, parseStreamMessage, progressReducer, type ProgressState } from "./progress";

export const MAX_RECONNECTS = 5;
export const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS = 10_000;

/** Ask the server why the stream closed: 410 means the session is gone for good. */
async function isExpired(url: string): Promise<boolean> {
  const controller = new AbortController();
  try {
    const response = await fetch(url, { signal: controller.signal, cache: "no-store" });
    return response.status === 410;
  } catch {
    return false; // unreachable: treat as a network problem and keep retrying
  } finally {
    controller.abort(); // never read a live event stream here
  }
}

/**
 * Live progress of an analysis run over SSE. Reconnects on its own (resuming after the last
 * event seen) up to MAX_RECONNECTS times in a row, and stops for good on done or 410.
 * The stream is closed when the component unmounts or the session changes.
 */
export function useProgressStream(sessionId: string | null): ProgressState {
  const [state, dispatch] = useReducer(progressReducer, initialProgress);
  const lastEventId = useRef(0);

  useEffect(() => {
    dispatch({ type: "reset" });
    lastEventId.current = 0;
    if (!sessionId) return;

    let source: EventSource | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let stopped = false;
    let attempts = 0;

    const stop = () => {
      stopped = true;
      source?.close();
      if (retryTimer !== null) clearTimeout(retryTimer);
    };

    const connect = () => {
      const current = new EventSource(streamUrl(sessionId, lastEventId.current));
      source = current;
      current.onopen = () => dispatch({ type: "open" });
      for (const name of STREAM_EVENTS) {
        current.addEventListener(name, (event) => {
          const action = parseStreamMessage(name, event as MessageEvent<string>);
          if (!action || stopped) return;
          attempts = 0;
          if (action.type === "event" && action.id !== null) {
            lastEventId.current = Math.max(lastEventId.current, action.id);
          }
          dispatch(action);
          if (name === "done") stop();
        });
      }
      current.onerror = () => {
        if (stopped) return;
        // CONNECTING: a dropped connection. CLOSED: the server refused it (e.g. 410).
        const refused = current.readyState === EventSource.CLOSED;
        current.close();
        attempts += 1;
        if (attempts > MAX_RECONNECTS) {
          dispatch({ type: "lost" });
          stop();
          return;
        }
        const retry = () => {
          if (stopped) return;
          dispatch({ type: "reconnecting" });
          const delay = Math.min(RECONNECT_BASE_MS * 2 ** (attempts - 1), RECONNECT_MAX_MS);
          retryTimer = setTimeout(connect, delay);
        };
        if (!refused) {
          retry();
          return;
        }
        void isExpired(streamUrl(sessionId)).then((expired) => {
          if (stopped) return;
          if (expired) {
            dispatch({ type: "expired" });
            stop();
          } else {
            retry();
          }
        });
      };
    };

    connect();
    return stop;
  }, [sessionId]);

  return state;
}
