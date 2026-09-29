"use client";

import { useEffect, useState } from "react";

import { getPredictions, type PredictionsResponse, type RiskBand } from "./api";

type Loaded = { key: string; data?: PredictionsResponse; error?: unknown };

/** One page of predictions. The previous page stays visible while the next one loads. */
export function usePredictions(sessionId: string, page: number, band: RiskBand | null, q: string) {
  const key = JSON.stringify([sessionId, page, band, q]);
  const [loaded, setLoaded] = useState<Loaded>({ key: "" });
  const [last, setLast] = useState<PredictionsResponse | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const current = JSON.stringify([sessionId, page, band, q]);
    getPredictions(sessionId, { page, band, q, signal: controller.signal })
      .then((data) => {
        setLoaded({ key: current, data });
        setLast(data);
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setLoaded({ key: current, error });
      });
    return () => controller.abort();
  }, [sessionId, page, band, q]);

  const fresh = loaded.key === key;
  return {
    data: fresh ? (loaded.data ?? null) : last,
    error: fresh ? (loaded.error ?? null) : null,
    loading: !fresh,
  };
}
