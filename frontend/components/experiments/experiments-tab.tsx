"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, getExperiment, listExperiments, type Experiment, type ExperimentListItem } from "@/lib/api";
import type { ResultsPayload } from "@/lib/results";

import { Alert, Button, Card, EmptyState, Spinner } from "../ui";
import { DesignWizard } from "./design-wizard";
import { ExperimentDetail, StatusChip } from "./experiment-detail";

const NAME_KEY = "churnlens.experiments.actor";

function readName(): string {
  try {
    return window.localStorage.getItem(NAME_KEY) ?? "";
  } catch {
    return "";
  }
}

function saveName(name: string) {
  try {
    window.localStorage.setItem(NAME_KEY, name);
  } catch {
    // Storage blocked (private window): the name just is not remembered.
  }
}

type View = { kind: "list" } | { kind: "new" } | { kind: "detail"; id: number };

export function ExperimentsTab({ results, sessionId }: { results: ResultsPayload; sessionId: string }) {
  // This tab only renders in the browser (after the results load), so storage is available.
  const [actor, setActor] = useState(readName);
  const [items, setItems] = useState<ExperimentListItem[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [view, setView] = useState<View>({ kind: "list" });
  const [detail, setDetail] = useState<Experiment | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  const refresh = useCallback((signal?: AbortSignal) => {
    listExperiments(signal)
      .then((list) => {
        setItems(list);
        setListError(null);
      })
      .catch((e: unknown) => {
        if (!signal?.aborted) setListError(e instanceof ApiError ? e.message : "Could not load experiments.");
      });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    refresh(controller.signal);
    return () => controller.abort();
  }, [refresh]);

  const detailId = view.kind === "detail" ? view.id : null;
  useEffect(() => {
    if (detailId == null) return;
    const controller = new AbortController();
    getExperiment(detailId, controller.signal)
      .then((exp) => {
        setDetail(exp);
        setDetailError(null);
      })
      .catch((e: unknown) => {
        if (!controller.signal.aborted) setDetailError(e instanceof ApiError ? e.message : "Could not load the experiment.");
      });
    return () => controller.abort();
  }, [detailId]);

  const onChange = (exp: Experiment) => {
    setDetail(exp);
    refresh();
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-xl text-sm text-gray-600 dark:text-gray-400">
            Test a retention offer before rolling it out: design the test, get it approved, assign customers at random,
            upload the outcomes and record a decision. Decided tests feed next best offer.
          </div>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium">Your name (for the audit trail)</span>
            <input
              className="min-h-10 rounded-lg border border-gray-300 bg-white px-3 dark:border-gray-700 dark:bg-gray-900"
              value={actor}
              maxLength={100}
              onChange={(e) => {
                setActor(e.target.value);
                saveName(e.target.value);
              }}
            />
          </label>
        </div>
      </Card>

      {view.kind === "new" ? (
        <DesignWizard
          results={results}
          sessionId={sessionId}
          actor={actor}
          onCancel={() => setView({ kind: "list" })}
          onCreated={(exp) => {
            setDetail(exp);
            setView({ kind: "detail", id: exp.id });
            refresh();
          }}
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
          <Card title="Experiments" actions={<Button onClick={() => setView({ kind: "new" })}>New</Button>}>
            {listError ? <Alert tone="error" title={listError} /> : null}
            {items === null && !listError ? <Spinner label="Loading..." /> : null}
            {items?.length === 0 ? <EmptyState>No experiments yet.</EmptyState> : null}
            <ul className="flex flex-col gap-1">
              {items?.map((e) => (
                <li key={e.id}>
                  <button
                    type="button"
                    aria-current={detailId === e.id}
                    onClick={() => setView({ kind: "detail", id: e.id })}
                    className={`flex w-full flex-col gap-1 rounded-lg p-2 text-left text-sm hover:bg-gray-50 dark:hover:bg-gray-900 ${
                      detailId === e.id ? "bg-gray-100 dark:bg-gray-900" : ""
                    }`}
                  >
                    <span className="font-medium">{e.name}</span>
                    <span className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
                      <StatusChip status={e.status} /> {e.offer}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
          <div className="min-w-0">
            {view.kind === "detail" ? (
              detailError ? (
                <Alert tone="error" title={detailError} />
              ) : detail && detail.id === view.id ? (
                <ExperimentDetail exp={detail} actor={actor} sessionId={sessionId} onChange={onChange} />
              ) : (
                <Spinner label="Loading the experiment..." />
              )
            ) : (
              <EmptyState>Pick an experiment, or start a new one.</EmptyState>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
