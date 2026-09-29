import type { ValidationReport } from "@/lib/results";

/** Every AI figure shown was checked against the computed results. */
export function ValidatorBadge({ report }: { report: ValidationReport | null }) {
  if (!report) return null;
  const allPassed = report.passed === report.checked;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium ${
        allPassed
          ? "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200"
          : "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-100"
      }`}
      title="The validator checks every number in the AI text against the computed results. Items that fail are retried, then dropped."
    >
      ✓ {report.passed}/{report.checked} AI items verified
      {report.dropped ? ` · ${report.dropped} dropped` : ""}
    </span>
  );
}
