import { formatCount, formatStat } from "@/lib/format";
import type { ModelMetrics } from "@/lib/results";

const TEST_ROWS: { key: "accuracy" | "precision" | "recall" | "f1" | "roc_auc" | "pr_auc"; label: string; help: string }[] = [
  { key: "roc_auc", label: "ROC-AUC", help: "Ranking quality: 0.5 is chance, 1 is perfect." },
  { key: "pr_auc", label: "PR-AUC", help: "Precision-recall area; more informative when churners are rare." },
  { key: "accuracy", label: "Accuracy", help: "Share of all test customers classified correctly." },
  { key: "precision", label: "Precision", help: "Of customers flagged as churners, the share who did churn." },
  { key: "recall", label: "Recall", help: "Of customers who churned, the share the model flagged." },
  { key: "f1", label: "F1", help: "Balance of precision and recall." },
];

export function MetricsTable({ metrics }: { metrics: ModelMetrics }) {
  const cv = Object.entries(metrics.cv ?? {});
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-gray-600 dark:text-gray-400">
        {metrics.chosen_model_name} was chosen. {metrics.selection_rule} Trained on {formatCount(metrics.n_train)}{" "}
        customers, tested once on {formatCount(metrics.n_test)} it never saw
        {metrics.test.threshold != null ? `, flagging churn at a probability of ${formatStat(metrics.test.threshold)}` : ""}.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Held-out test metrics</caption>
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-800">
              <th className="py-2 pr-3 font-medium">Metric (test set)</th>
              <th className="py-2 pr-3 text-right font-medium">Value</th>
              <th className="hidden py-2 font-medium sm:table-cell">Meaning</th>
            </tr>
          </thead>
          <tbody>
            {TEST_ROWS.map((row) => (
              <tr key={row.key} className="border-b border-gray-100 dark:border-gray-900">
                <td className="py-1.5 pr-3" title={row.help}>
                  {row.label}
                </td>
                <td className="py-1.5 pr-3 text-right tabular-nums">{formatStat(metrics.test[row.key])}</td>
                <td className="hidden py-1.5 text-gray-500 sm:table-cell">{row.help}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {cv.length ? (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="mb-1 text-left text-xs text-gray-500">
              Model comparison: 5-fold cross-validation on the training split (mean ± SD)
            </caption>
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-800">
                <th className="py-2 pr-3 font-medium">Model</th>
                <th className="py-2 pr-3 text-right font-medium">ROC-AUC</th>
                <th className="py-2 text-right font-medium">PR-AUC</th>
              </tr>
            </thead>
            <tbody>
              {cv.map(([key, scores]) => (
                <tr key={key} className="border-b border-gray-100 dark:border-gray-900">
                  <td className="py-1.5 pr-3">
                    {scores.name}
                    {key === metrics.chosen_model ? <span className="ml-2 text-xs text-blue-600">chosen</span> : null}
                  </td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">
                    {formatStat(scores.roc_auc_mean)} ± {formatStat(scores.roc_auc_std)}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {formatStat(scores.pr_auc_mean)} ± {formatStat(scores.pr_auc_std)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
