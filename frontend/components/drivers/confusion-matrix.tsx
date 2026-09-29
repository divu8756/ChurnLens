import { formatCount } from "@/lib/format";
import type { ModelMetrics } from "@/lib/results";

type Matrix = NonNullable<ModelMetrics["test"]["confusion_matrix"]>;

function Cell({ value, label, good }: { value: number; label: string; good: boolean }) {
  return (
    <div
      className={`flex flex-col items-center justify-center rounded-lg p-3 text-center ${
        good ? "bg-blue-50 text-blue-900 dark:bg-blue-950 dark:text-blue-100" : "bg-orange-50 text-orange-900 dark:bg-orange-950 dark:text-orange-100"
      }`}
    >
      <span className="text-xl font-semibold tabular-nums">{formatCount(value)}</span>
      <span className="text-xs">{label}</span>
    </div>
  );
}

export function ConfusionMatrix({ matrix }: { matrix: Matrix }) {
  return (
    <figure>
      <div className="grid grid-cols-[auto_1fr_1fr] gap-2 text-sm">
        <span />
        <span className="text-center text-xs font-medium text-gray-500">Predicted: stays</span>
        <span className="text-center text-xs font-medium text-gray-500">Predicted: churns</span>
        <span className="self-center text-right text-xs font-medium text-gray-500">Actually stayed</span>
        <Cell value={matrix.tn} label="correctly cleared" good />
        <Cell value={matrix.fp} label="false alarms" good={false} />
        <span className="self-center text-right text-xs font-medium text-gray-500">Actually churned</span>
        <Cell value={matrix.fn} label="missed churners" good={false} />
        <Cell value={matrix.tp} label="caught churners" good />
      </div>
      <figcaption className="mt-2 text-xs text-gray-500">
        What this shows: test-set customers by what the model predicted and what actually happened.
      </figcaption>
    </figure>
  );
}
