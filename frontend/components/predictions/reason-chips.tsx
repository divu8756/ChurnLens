import { parseReason } from "@/lib/predictions";

export function ReasonChips({ reasons }: { reasons: (string | null | undefined)[] }) {
  const shown = reasons.filter((r): r is string => Boolean(r));
  if (!shown.length) return <span className="text-gray-500">–</span>;
  return (
    <ul className="flex flex-wrap gap-1">
      {shown.map((reason) => {
        const { text, contribution, raises } = parseReason(reason);
        return (
          <li
            key={reason}
            title={`${raises ? "Raises" : "Lowers"} churn risk (SHAP ${contribution || "n/a"}, log-odds)`}
            className={`rounded-full px-2 py-0.5 text-xs ${
              raises
                ? "bg-orange-100 text-orange-900 dark:bg-orange-950 dark:text-orange-100"
                : "bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-100"
            }`}
          >
            <span aria-hidden>{raises ? "▲ " : "▼ "}</span>
            {text}
            {contribution ? <span className="ml-1 tabular-nums opacity-70">{contribution}</span> : null}
          </li>
        );
      })}
    </ul>
  );
}
