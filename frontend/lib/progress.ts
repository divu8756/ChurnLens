// Pure state for the live progress view, driven by SSE events from GET /stream/{id}.
import type { DoneEvent, ErrorEvent, SchemaProposal, StreamEvents } from "./api";

export type StreamEventName = keyof StreamEvents;
export const STREAM_EVENTS: StreamEventName[] = [
  "node_start",
  "node_finish",
  "error",
  "awaiting_confirmation",
  "resumed",
  "heartbeat",
  "done",
];

export type NodeStatus = "running" | "done" | "skipped" | "failed";
export type NodeProgress = { status: NodeStatus; detail: string | null };

export type Connection =
  | "connecting"
  | "open"
  | "reconnecting"
  | "closed" // the run finished and the stream ended normally
  | "expired" // 410: the session or run is gone
  | "lost"; // gave up after the maximum number of reconnects

export type ProgressState = {
  connection: Connection;
  /** Node name -> latest status, in the order nodes first appeared. */
  nodes: Record<string, NodeProgress>;
  order: string[];
  errors: ErrorEvent[];
  awaitingConfirmation: boolean;
  proposal: SchemaProposal | null;
  done: DoneEvent | null;
  lastEventId: number;
  reconnectAttempts: number;
};

export const initialProgress: ProgressState = {
  connection: "connecting",
  nodes: {},
  order: [],
  errors: [],
  awaitingConfirmation: false,
  proposal: null,
  done: null,
  lastEventId: 0,
  reconnectAttempts: 0,
};

export type ProgressAction =
  | { type: "event"; name: StreamEventName; data: unknown; id: number | null }
  | { type: "open" }
  | { type: "reconnecting" }
  | { type: "expired" }
  | { type: "lost" }
  | { type: "reset" };

function setNode(state: ProgressState, node: string, progress: NodeProgress): Pick<ProgressState, "nodes" | "order"> {
  return {
    nodes: { ...state.nodes, [node]: progress },
    order: state.order.includes(node) ? state.order : [...state.order, node],
  };
}

function applyEvent(state: ProgressState, name: StreamEventName, data: unknown): ProgressState {
  switch (name) {
    case "node_start": {
      const { node } = data as StreamEvents["node_start"];
      return { ...state, ...setNode(state, node, { status: "running", detail: null }) };
    }
    case "node_finish": {
      const { node, status, detail } = data as StreamEvents["node_finish"];
      const mapped: NodeStatus = status === "started" ? "running" : status;
      return { ...state, ...setNode(state, node, { status: mapped, detail: detail ?? null }) };
    }
    case "error":
      return { ...state, errors: [...state.errors, data as ErrorEvent] };
    case "awaiting_confirmation": {
      const { proposal } = data as StreamEvents["awaiting_confirmation"];
      return { ...state, awaitingConfirmation: true, proposal: proposal ?? null };
    }
    case "resumed":
      return { ...state, awaitingConfirmation: false };
    case "heartbeat":
      return state;
    case "done":
      return { ...state, done: data as DoneEvent, awaitingConfirmation: false, connection: "closed" };
  }
}

export function progressReducer(state: ProgressState, action: ProgressAction): ProgressState {
  switch (action.type) {
    case "event": {
      const next = applyEvent(state, action.name, action.data);
      // Any event proves the connection works, so the reconnect budget starts again.
      return {
        ...next,
        connection: next.connection === "closed" ? "closed" : "open",
        reconnectAttempts: 0,
        lastEventId: action.id !== null && action.id > state.lastEventId ? action.id : state.lastEventId,
      };
    }
    case "open":
      return { ...state, connection: "open" };
    case "reconnecting":
      return { ...state, connection: "reconnecting", reconnectAttempts: state.reconnectAttempts + 1 };
    case "expired":
      return { ...state, connection: "expired" };
    case "lost":
      return { ...state, connection: "lost" };
    case "reset":
      return initialProgress;
  }
}

/** Parse one SSE message; returns null for malformed data so one bad event cannot break the view. */
export function parseStreamMessage(
  name: StreamEventName,
  message: { data: string; lastEventId: string },
): ProgressAction | null {
  let data: unknown;
  try {
    data = JSON.parse(message.data || "{}");
  } catch {
    return null;
  }
  if (typeof data !== "object" || data === null) return null;
  const id = /^\d+$/.test(message.lastEventId) ? Number(message.lastEventId) : null;
  return { type: "event", name, data, id };
}
