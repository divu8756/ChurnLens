// The analysis graph as the progress view shows it. Node names match backend/app/graph/builder.py.
import type { NodeStatus, ProgressState } from "./progress";

export type StepStatus = "pending" | NodeStatus | "waiting";

export type Step = { node: string; label: string; status: StepStatus; detail: string | null };

/** Stages run in order; the nodes inside one stage run in parallel. */
export const STAGES: { node: string; label: string }[][] = [
  [{ node: "ingest", label: "Read the file" }],
  [{ node: "schema_agent", label: "Describe the columns" }],
  [{ node: "human_review", label: "Confirm the columns" }],
  [{ node: "cleaning", label: "Clean the data" }],
  [
    { node: "eda", label: "Explore" },
    { node: "segmentation", label: "Find segments" },
    { node: "survival", label: "Survival curves" },
    { node: "hypothesis", label: "Hypothesis tests" },
  ],
  [{ node: "modelling", label: "Train the churn model" }],
  [{ node: "impact", label: "Estimate impact" }],
  [{ node: "offer", label: "Offer effectiveness" }],
  [{ node: "insight_agent", label: "Write insights" }],
  [{ node: "recommendation_agent", label: "Write recommendations" }],
  [{ node: "validator", label: "Check every number" }],
  [{ node: "report", label: "Build the report" }],
];

export function stepStatus(node: string, state: ProgressState): Pick<Step, "status" | "detail"> {
  const seen = state.nodes[node];
  if (node === "human_review" && state.awaitingConfirmation) {
    return { status: "waiting", detail: "Waiting for you to confirm the columns" };
  }
  if (seen) return { status: seen.status, detail: seen.detail };
  // Once the run has finished, a node that never ran was skipped by a branch (or by a fatal error).
  if (state.done) return { status: "skipped", detail: null };
  return { status: "pending", detail: null };
}

export function stepperStages(state: ProgressState): Step[][] {
  return STAGES.map((stage) => stage.map(({ node, label }) => ({ node, label, ...stepStatus(node, state) })));
}

/** Data Health can be shown once cleaning has finished. */
export function cleaningFinished(state: ProgressState): boolean {
  return state.nodes.cleaning?.status === "done";
}
