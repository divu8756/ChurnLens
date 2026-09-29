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
export type PredictionsResponse = Schemas["PredictionsResponse"];
export type PredictionRow = Schemas["PredictionRow"];
export type NextBestOffer = Schemas["NextBestOffer"];
export type OfferMessage = Schemas["OfferMessageResponse"];
export type NodeFinishEvent = Schemas["NodeFinishEvent"];
export type ErrorEvent = Schemas["ErrorEvent"];
export type DoneEvent = Schemas["DoneEvent"];
export type Experiment = Schemas["ExperimentOut"];
export type ExperimentListItem = Schemas["ExperimentSummary"];
/** Settings the server defaults (alpha 0.05, power 0.8, control share 0.5); omit to keep the default. */
type Defaulted = "alpha" | "power" | "control_share";
type WithDefaults<T extends Record<Defaulted, unknown>> = Omit<T, Defaulted> & Partial<Pick<T, Defaulted>>;
export type ExperimentCreate = WithDefaults<Schemas["ExperimentCreate"]>;
export type ExperimentUpdate = Schemas["ExperimentUpdate"];
export type DesignInputs = WithDefaults<Schemas["DesignInputs"]>;
export type Design = Schemas["DesignOut"];
export type Analysis = Schemas["AnalysisOut"];
export type AnalysisAssumptions = Schemas["AnalysisAssumptions"];
export type ExperimentSummaryText = Schemas["ExperimentSummaryOut"];
export type SegmentColumn = Schemas["SegmentColumn"];
export type SegmentFilter = Schemas["SegmentFilter"];
export type DecideRequest = Schemas["DecideRequest"];
export type OfferEvidence = Schemas["OfferEvidenceOut"];

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
export const REQUEST_TIMEOUT_MS = 30_000;
/** AI-written text: the server may retry a slow model before falling back to a template. */
export const AI_TIMEOUT_MS = 150_000;

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

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH";
  body?: BodyInit;
  json?: unknown;
  signal?: AbortSignal;
  timeoutMs?: number;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const timeoutMs = options.timeoutMs ?? REQUEST_TIMEOUT_MS;
  const timeout = AbortSignal.timeout(timeoutMs);
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
      throw new ApiError("timeout", `The server did not answer within ${timeoutMs / 1000} s.`);
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

export type PredictionsQuery = { page?: number; band?: RiskBand | null; q?: string };

function predictionsQuery({ page, band, q }: PredictionsQuery): URLSearchParams {
  const query = new URLSearchParams();
  if (page) query.set("page", String(page));
  if (band) query.set("band", band);
  if (q && q.trim()) query.set("q", q.trim());
  return query;
}

export function getPredictions(
  sessionId: string,
  options: PredictionsQuery & { signal?: AbortSignal } = {},
): Promise<PredictionsResponse> {
  const query = predictionsQuery({ page: options.page ?? 1, band: options.band, q: options.q });
  return request<PredictionsResponse>(`/predictions/${enc(sessionId)}?${query}`, { signal: options.signal });
}

export function getNextBestOffer(sessionId: string, customerId: string, signal?: AbortSignal): Promise<NextBestOffer> {
  return request<NextBestOffer>(`/predictions/${enc(sessionId)}/offer/${enc(customerId)}`, { signal });
}

/** Written by the LLM on demand (cached per customer on the server). */
export function generateOfferMessage(sessionId: string, customerId: string, signal?: AbortSignal): Promise<OfferMessage> {
  return request<OfferMessage>(`/predictions/${enc(sessionId)}/offer/${enc(customerId)}/message`, {
    method: "POST",
    signal,
    timeoutMs: AI_TIMEOUT_MS,
  });
}

/** Direct download link: the server sends the CSV as an attachment. */
export function predictionsCsvUrl(sessionId: string, options: Omit<PredictionsQuery, "page"> = {}): string {
  const query = predictionsQuery(options).toString();
  return `${API_URL}/predictions/${enc(sessionId)}/csv${query ? `?${query}` : ""}`;
}

/** URL for the SSE progress stream; `after` resumes after that event id. */
export function streamUrl(sessionId: string, after = 0): string {
  const query = after > 0 ? `?after=${after}` : "";
  return `${API_URL}/stream/${enc(sessionId)}${query}`;
}

// ---------------------------------------------------------------- experiments (Phase 5c)

export function listExperiments(signal?: AbortSignal): Promise<ExperimentListItem[]> {
  return request<ExperimentListItem[]>("/experiments", { signal });
}

export function getExperiment(id: number, signal?: AbortSignal): Promise<Experiment> {
  return request<Experiment>(`/experiments/${id}`, { signal });
}

/** Sample size for a design without saving it (live feedback in the wizard). */
export function previewDesign(inputs: DesignInputs, signal?: AbortSignal): Promise<Design> {
  return request<Design>("/experiments/design", { method: "POST", json: inputs, signal });
}

export function getSegmentOptions(sessionId: string, signal?: AbortSignal): Promise<SegmentColumn[]> {
  return request<SegmentColumn[]>(`/experiments/segment-options/${enc(sessionId)}`, { signal });
}

export function createExperiment(body: ExperimentCreate, signal?: AbortSignal): Promise<Experiment> {
  return request<Experiment>("/experiments", { method: "POST", json: body, signal });
}

export function updateExperiment(id: number, body: ExperimentUpdate, signal?: AbortSignal): Promise<Experiment> {
  return request<Experiment>(`/experiments/${id}`, { method: "PATCH", json: body, signal });
}

export function approveExperiment(
  id: number,
  body: { approver: string; cost_and_eligibility_reviewed: boolean; note?: string | null },
  signal?: AbortSignal,
): Promise<Experiment> {
  return request<Experiment>(`/experiments/${id}/approve`, { method: "POST", json: body, signal });
}

export function assignExperiment(id: number, sessionId: string, actor: string, signal?: AbortSignal): Promise<Experiment> {
  return request<Experiment>(`/experiments/${id}/assign`, {
    method: "POST",
    json: { session_id: sessionId, actor },
    signal,
  });
}

export function assignmentCsvUrl(id: number): string {
  return `${API_URL}/experiments/${id}/assignment.csv`;
}

export function uploadExperimentResults(
  id: number,
  file: File,
  uploadedBy: string,
  assumptions: { customer_value?: number | null; offer_cost?: number | null; arpu_tolerance?: number | null },
  signal?: AbortSignal,
): Promise<Experiment> {
  const form = new FormData();
  form.append("file", file);
  form.append("uploaded_by", uploadedBy);
  for (const [key, value] of Object.entries(assumptions)) {
    if (value != null) form.append(key, String(value));
  }
  return request<Experiment>(`/experiments/${id}/results`, { method: "POST", body: form, signal });
}

/** Recompute the analysis with new money / guardrail assumptions (never in the browser). */
export function reanalyseExperiment(
  id: number,
  actor: string,
  assumptions: AnalysisAssumptions,
  signal?: AbortSignal,
): Promise<Experiment> {
  return request<Experiment>(`/experiments/${id}/analysis`, { method: "POST", json: { actor, assumptions }, signal });
}

/** The validated plain-English summary (written once per analysis, then cached). */
export function getExperimentSummary(id: number, signal?: AbortSignal): Promise<ExperimentSummaryText> {
  return request<ExperimentSummaryText>(`/experiments/${id}/summary`, { method: "POST", signal, timeoutMs: AI_TIMEOUT_MS });
}

export function decideExperiment(id: number, body: DecideRequest, signal?: AbortSignal): Promise<Experiment> {
  return request<Experiment>(`/experiments/${id}/decide`, { method: "POST", json: body, signal });
}

export function listOfferEvidence(signal?: AbortSignal): Promise<OfferEvidence[]> {
  return request<OfferEvidence[]>("/experiments/offer-evidence", { signal });
}
