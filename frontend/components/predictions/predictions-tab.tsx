"use client";

import { useEffect, useState } from "react";

import { ApiError, predictionsCsvUrl, type RiskBand } from "@/lib/api";
import { formatPercent } from "@/lib/format";
import { SEARCH_DEBOUNCE_MS } from "@/lib/predictions";
import type { ResultsPayload } from "@/lib/results";
import { usePredictions } from "@/lib/use-predictions";

import { Alert, Card, EmptyState, Spinner } from "../ui";
import { BandFilter } from "./band-filter";
import { Pagination } from "./pagination";
import { PredictionsTable } from "./predictions-table";

export function PredictionsTab({ results, sessionId }: { results: ResultsPayload; sessionId: string }) {
  const bands = results.model_metrics?.risk_bands ?? null;
  const valueUnit = results.offer_effectiveness?.next_best_offer?.value_unit ?? null;
  const [band, setBand] = useState<RiskBand | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const { data, error, loading } = usePredictions(sessionId, page, band, q);

  useEffect(() => {
    const timer = setTimeout(() => {
      setQ(search.trim());
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [search]);

  if (!bands) return <EmptyState>Risk scores are not available for this run.</EmptyState>;

  return (
    <Card title="Risk predictions">
      <div className="flex flex-col gap-4">
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Every customer scored by the churn model, highest risk first. High ≥ {formatPercent(bands.thresholds.high, 0)}, Medium ≥{" "}
          {formatPercent(bands.thresholds.medium, 0)}. Reasons are the three features that moved each score most (▲ raises risk,
          ▼ lowers it).
        </p>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <BandFilter
            band={band}
            counts={bands.band_counts}
            total={bands.total}
            onChange={(next) => {
              setBand(next);
              setPage(1);
            }}
          />
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="search"
              value={search}
              maxLength={100}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search customer ID"
              aria-label="Search customer ID"
              className="min-h-9 w-48 rounded-lg border border-gray-300 bg-white px-3 text-sm dark:border-gray-700 dark:bg-gray-900"
            />
            <a
              href={predictionsCsvUrl(sessionId, { band, q })}
              className="inline-flex min-h-9 items-center rounded-lg border border-gray-300 px-3 text-sm font-medium hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-900"
            >
              Download CSV
            </a>
          </div>
        </div>

        {error ? (
          <Alert tone="error" title={error instanceof ApiError ? error.message : "Could not load predictions."} />
        ) : null}
        {!data && loading ? <Spinner label="Loading predictions..." /> : null}
        {data ? (
          <div className={loading ? "opacity-60 transition-opacity" : undefined} aria-busy={loading}>
            {data.items.length ? (
              <PredictionsTable rows={data.items} sessionId={sessionId} valueUnit={valueUnit} />
            ) : (
              <EmptyState>{q ? `No customer ID contains “${q}”.` : "No customers in this band."}</EmptyState>
            )}
            <div className="mt-3">
              <Pagination page={data.page} pages={data.pages} total={data.total} pageSize={data.page_size} onPage={setPage} />
            </div>
          </div>
        ) : null}
      </div>
    </Card>
  );
}
