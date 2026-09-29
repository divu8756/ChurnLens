// Typed client for the ChurnLens API. The base URL is inlined at build time.
// Types come from the backend's OpenAPI schema: run `npm run gen:types` after API changes.
import type { components } from "./api-types";

type Schemas = components["schemas"];

export type Health = { status: string; version: string };
export type UploadResponse = Schemas["UploadResponse"];
export type RunStatusResponse = Schemas["RunStatusResponse"];
export type ConfirmedSchema = Schemas["ConfirmedSchema"];
export type SchemaProposal = Schemas["SchemaProposalOut"];
export type ResultsResponse = Schemas["ResultsResponse"];
export type PredictionsPage = Schemas["PredictionsPage"];
export type RiskBand = NonNullable<PredictionsPage["band"]>;
export type StreamEvents = Schemas["StreamEvents"];
export type NodeFinishEvent = Schemas["NodeFinishEvent"];
export type ErrorEvent = Schemas["ErrorEvent"];
export type DoneEvent = Schemas["DoneEvent"];

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
export const REQUEST_TIMEOUT_MS = 30_000;

export type ApiErrorKind =
  | "expired" // 410: the session is gone; the user must upload again
  | "conflict" // 409
  | "validation" // 422
  | "client" // other 4xx
  | "server" // 5xx
  | "timeout"
  | "network";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  /** Plain-English problems, e.g. why a confirmed schema was rejected. */
  readonly problems: string[];

  constructor(kind: ApiErrorKind, message: string, status: number | null = null, problems: string[] = []) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.problems = problems;
  }
}

function kindForStatus(status: number): ApiErrorKind {
  if (status === 410) return "expired";
  if (status === 409) return "conflict";
  if (status === 422) return "validation";
  return status >= 500 ? "server" : "client";
}

type Detail = { message: string; problems: string[] };

/** FastAPI error bodies: {detail: string}, {detail: {message, problems}} or {detail: [{msg, loc}]}. */
export function parseErrorDetail(body: unknown, fallback: string): Detail {
  const detail = typeof body === "object" && body !== null ? (body as { detail?: unknown }).detail : undefined;
  if (typeof detail === "string") return { message: detail, problems: [] };
  if (Array.isArray(detail)) {
    const problems = detail.map((item) => {
      const { msg, loc } = (item ?? {}) as { msg?: unknown; loc?: unknown };
      const where = Array.isArray(loc) ? loc.filter((p) => p !== "body").join(".") : "";
      const text = typeof msg === "string" ? msg : "Invalid value";
      return where ? `${where}: ${text}` : text;
    });
    return { message: "The request was not valid.", problems };
  }
  if (typeof detail === "object" && detail !== null) {
    const { message, problems } = detail as { message?: unknown; problems?: unknown };
    return {
      message: typeof message === "string" ? message : fallback,
      problems: Array.isArray(problems) ? problems.filter((p): p is string => typeof p === "string") : [],
    };
  }
  return { message: fallback, problems: [] };
}

export async function toApiError(response: Response): Promise<ApiError> {
  const fallback = `Request failed with HTTP ${response.status}`;
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // Not JSON (e.g. a proxy error page); keep the fallback message.
  }
  const { message, problems } = parseErrorDetail(body, fallback);
  return new ApiError(kindForStatus(response.status), message, response.status, problems);
}

type RequestOptions = { method?: "GET" | "POST"; body?: BodyInit; json?: unknown; signal?: AbortSignal };

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  const signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout;
  const headers: Record<string, string> = {};
  let body = options.body;
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  }
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: options.method ?? "GET",
      headers,
      body,
      signal,
      cache: "no-store",
    });
  } catch (error) {
    if (options.signal?.aborted) throw error; // the caller cancelled; not an API failure
    if (timeout.aborted) {
      throw new ApiError("timeout", `The server did not answer within ${REQUEST_TIMEOUT_MS / 1000} s.`);
    }
    throw new ApiError("network", "Could not reach the server. Check your connection and try again.");
  }
  if (!response.ok) throw await toApiError(response);
  return (await response.json()) as T;
}

const enc = encodeURIComponent;

export function getHealth(signal?: AbortSignal): Promise<Health> {
  return request<Health>("/health", { signal });
}

export function uploadFile(file: File, sheetName?: string, signal?: AbortSignal): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  if (sheetName !== undefined) form.append("sheet_name", sheetName);
  return request<UploadResponse>("/upload", { method: "POST", body: form, signal });
}

export function chooseSheet(sessionId: string, sheetName: string, signal?: AbortSignal): Promise<UploadResponse> {
  const form = new FormData();
  form.append("sheet_name", sheetName);
  return request<UploadResponse>(`/upload/${enc(sessionId)}/sheet`, { method: "POST", body: form, signal });
}

export function loadSample(signal?: AbortSignal): Promise<UploadResponse> {
  return request<UploadResponse>("/sample", { method: "POST", signal });
}

export function startAnalysis(sessionId: string, signal?: AbortSignal): Promise<RunStatusResponse> {
  return request<RunStatusResponse>(`/analyze/${enc(sessionId)}`, { method: "POST", signal });
}

export function confirmSchema(
  sessionId: string,
  schema: ConfirmedSchema,
  signal?: AbortSignal,
): Promise<RunStatusResponse> {
  return request<RunStatusResponse>(`/confirm-schema/${enc(sessionId)}`, { method: "POST", json: schema, signal });
}

export function getResults(
  sessionId: string,
  options: { page?: number; band?: RiskBand; signal?: AbortSignal } = {},
): Promise<ResultsResponse> {
  const query = new URLSearchParams({ page: String(options.page ?? 1) });
  if (options.band) query.set("band", options.band);
  return request<ResultsResponse>(`/results/${enc(sessionId)}?${query}`, { signal: options.signal });
}

/** URL for the SSE progress stream; `after` resumes after that event id. */
export function streamUrl(sessionId: string, after = 0): string {
  const query = after > 0 ? `?after=${after}` : "";
  return `${API_URL}/stream/${enc(sessionId)}${query}`;
}
