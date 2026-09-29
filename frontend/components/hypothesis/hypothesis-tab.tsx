"use client";

import { Fragment, useState } from "react";

import { formatP, formatStat } from "@/lib/format";
import { DEFAULT_ALPHA, significantAt, significantCount, sortTests } from "@/lib/hypothesis";
import type { ResultsPayload } from "@/lib/results";

import { Card, EmptyState } from "../ui";
import { AlphaControl } from "./alpha-control";
import { TestDetail } from "./test-detail";

export function HypothesisTab({ results }: { results: ResultsPayload }) {
  const hyp = results.hypothesis_results;
  const [alpha, setAlpha] = useState(hyp?.alpha ?? DEFAULT_ALPHA);
  const [open, setOpen] = useState<string | null>(null);
  if (!hyp?.tests?.length) return <EmptyState>No hypothesis tests were run for this data.</EmptyState>;
  const tests = sortTests(hyp.tests);
  const skipped = hyp.skipped ?? [];

  return (
    <div className="flex flex-col gap-6">
      <Card title="Hypothesis tests">
        <div className="flex flex-col gap-4">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Each column is tested against churn. p-values are adjusted for running {hyp.n_tests} tests at once (
            {hyp.correction}). Move α to see which results hold up at a stricter or looser level.
          </p>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <AlphaControl alpha={alpha} onChange={setAlpha} />
            <p className="text-sm" aria-live="polite">
              <span className="text-2xl font-semibold tabular-nums">{significantCount(tests, alpha)}</span> of {tests.length}{" "}
              significant at α = {alpha}
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[38rem] text-left text-sm">
              <caption className="sr-only">Hypothesis test results</caption>
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-800">
                  <th className="py-2 pr-3 font-medium">Variable</th>
                  <th className="py-2 pr-3 font-medium">Test</th>
                  <th className="py-2 pr-3 text-right font-medium">Statistic</th>
                  <th className="py-2 pr-3 text-right font-medium">Adj. p</th>
                  <th className="py-2 pr-3 font-medium">Effect size</th>
                  <th className="py-2 font-medium">Significant?</th>
                </tr>
              </thead>
              <tbody>
                {tests.map((t) => {
                  const isOpen = open === t.variable;
                  const sig = significantAt(t, alpha);
                  return (
                    <Fragment key={t.variable}>
                      <tr className="border-b border-gray-100 dark:border-gray-900">
                        <td className="py-1.5 pr-3">
                          <button
                            type="button"
                            className="flex items-center gap-1 text-left font-medium text-blue-700 hover:underline dark:text-blue-300"
                            aria-expanded={isOpen}
                            onClick={() => setOpen(isOpen ? null : t.variable)}
                          >
                            <span aria-hidden>{isOpen ? "▾" : "▸"}</span>
                            <span className="break-all">{t.variable}</span>
                          </button>
                        </td>
                        <td className="py-1.5 pr-3 text-gray-600 dark:text-gray-400">{t.test_name}</td>
                        <td className="py-1.5 pr-3 text-right tabular-nums" title={t.statistic_name}>
                          {formatStat(t.statistic)}
                          {t.df != null ? <span className="block text-xs text-gray-500">df {formatStat(t.df, Number.isInteger(t.df) ? 0 : 1)}</span> : null}
                        </td>
                        <td className="py-1.5 pr-3 text-right tabular-nums">{formatP(t.p_adjusted)}</td>
                        <td className="py-1.5 pr-3">
                          <span className="tabular-nums">{formatStat(t.effect_size.value)}</span>{" "}
                          <span className="text-xs text-gray-500">
                            {t.effect_size.name}, {t.effect_size.band}
                          </span>
                        </td>
                        <td className="py-1.5">
                          <span
                            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                              sig
                                ? "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200"
                                : "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"
                            }`}
                          >
                            {sig ? "Yes" : "No"}
                          </span>
                        </td>
                      </tr>
                      {isOpen ? (
                        <tr className="border-b border-gray-100 dark:border-gray-900">
                          <td colSpan={6} className="py-3">
                            <TestDetail test={t} alpha={alpha} serverAlpha={hyp.alpha} />
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
          {skipped.length ? (
            <details className="text-xs text-gray-500">
              <summary className="cursor-pointer">{skipped.length} columns not tested</summary>
              <ul className="mt-1 list-disc pl-5">
                {skipped.map((s) => (
                  <li key={s.variable}>
                    {s.variable}: {s.reason}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </div>
      </Card>
    </div>
  );
}
