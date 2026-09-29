import type { Step, StepStatus } from "@/lib/pipeline";

const ICON: Record<StepStatus, { symbol: string; className: string; label: string }> = {
  pending: { symbol: "", className: "border-gray-300 dark:border-gray-700", label: "pending" },
  running: { symbol: "", className: "border-blue-600 border-t-transparent animate-spin", label: "running" },
  waiting: { symbol: "!", className: "border-amber-500 bg-amber-500 text-white", label: "waiting for you" },
  done: { symbol: "✓", className: "border-green-600 bg-green-600 text-white", label: "done" },
  skipped: { symbol: "–", className: "border-gray-300 bg-gray-100 text-gray-500 dark:border-gray-700 dark:bg-gray-800", label: "skipped" },
  failed: { symbol: "✕", className: "border-red-600 bg-red-600 text-white", label: "failed" },
};

function StepItem({ step }: { step: Step }) {
  const icon = ICON[step.status];
  return (
    <div className="flex min-w-0 items-start gap-2">
      <span
        className={`mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 text-xs font-bold ${icon.className}`}
        aria-hidden
      >
        {icon.symbol}
      </span>
      <div className="min-w-0">
        <p className={`text-sm ${step.status === "pending" || step.status === "skipped" ? "text-gray-500" : "font-medium"}`}>
          {step.label}
          <span className="sr-only">: {icon.label}</span>
        </p>
        {step.detail ? <p className="truncate text-xs text-gray-500" title={step.detail}>{step.detail}</p> : null}
      </div>
    </div>
  );
}

/** Vertical stepper; nodes that run in parallel sit side by side in one row. */
export function ProgressStepper({ stages }: { stages: Step[][] }) {
  return (
    <ol className="flex flex-col gap-3" aria-label="Analysis progress">
      {stages.map((stage) => (
        <li
          key={stage.map((s) => s.node).join("+")}
          className={stage.length > 1 ? "grid grid-cols-2 gap-3 border-l-2 border-gray-200 pl-3 dark:border-gray-800" : ""}
        >
          {stage.map((step) => (
            <StepItem key={step.node} step={step} />
          ))}
        </li>
      ))}
    </ol>
  );
}
