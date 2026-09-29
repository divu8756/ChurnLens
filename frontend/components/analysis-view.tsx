"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiError, getResults, startAnalysis, type ResultsResponse } from "@/lib/api";
import { cleaningFinished, stepperStages } from "@/lib/pipeline";
import { useProgressStream } from "@/lib/use-progress-stream";

import { Dashboard } from "./dashboard/dashboard";
import { DataHealthView } from "./data-health";
import { ProgressStepper } from "./progress-stepper";
import { SchemaConfirmation } from "./schema-confirmation";
import { Alert, Button, Card, Spinner } from "./ui";

type Start = { state: "starting" } | { state: "started" } | { state: "expired" } | { state: "error"; message: string };

function Expired() {
  return (
    <Alert tone="warning" title="This session has expired">
      Uploads are kept for 2 hours, and a server restart also ends them.{" "}
      <Link href="/" className="font-medium underline">
        Upload the data again
      </Link>
      .
    </Alert>
  );
}

export function AnalysisView({ sessionId }: { sessionId: string }) {
  const [start, setStart] = useState<Start>({ state: "starting" });
  const [attempt, setAttempt] = useState(0);
  const [expired, setExpired] = useState(false);
  const progress = useProgressStream(start.state === "started" ? sessionId : null);
  const [results, setResults] = useState<ResultsResponse | null>(null);
  const [resultsError, setResultsError] = useState<string | null>(null);
  // True once the results in state were loaded after the run finished.
  const [finishedResults, setFinishedResults] = useState(false);
  const showHealth = cleaningFinished(progress);
  const finished = progress.done !== null;

  // Starting is idempotent on the server, so a reload simply re-attaches to the run.
  useEffect(() => {
    const controller = new AbortController();
    startAnalysis(sessionId, controller.signal)
      .then(() => setStart({ state: "started" }))
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        if (e instanceof ApiError && e.kind === "expired") setStart({ state: "expired" });
        else setStart({ state: "error", message: e instanceof ApiError ? e.message : "Could not start the analysis." });
      });
    return () => controller.abort();
  }, [sessionId, attempt]);

  // Load results once cleaning is done (Data Health), and again when the run finishes.
  useEffect(() => {
    if (!showHealth) return;
    const controller = new AbortController();
    getResults(sessionId, { signal: controller.signal })
      .then((r) => {
        setResults(r);
        setFinishedResults(finished);
        setResultsError(null);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        if (e instanceof ApiError && e.kind === "expired") setExpired(true);
        else setResultsError(e instanceof ApiError ? e.message : "Could not load the results.");
      });
    return () => controller.abort();
  }, [sessionId, showHealth, finished]);

  if (start.state === "expired" || expired || progress.connection === "expired") return <Expired />;

  const health = results?.results.data_health;
  const fatal = progress.errors.filter((e) => e.fatal);

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">Analysis</h1>
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          New upload
        </Link>
      </div>

      {start.state === "starting" ? <Spinner label="Starting the analysis..." /> : null}
      {start.state === "error" ? (
        <Alert tone="error" title={start.message}>
          <Button
            variant="secondary"
            className="mt-2"
            onClick={() => {
              setStart({ state: "starting" });
              setAttempt((n) => n + 1);
            }}
          >
            Try again
          </Button>
        </Alert>
      ) : null}
      {progress.connection === "reconnecting" ? (
        <Alert tone="warning" title="Connection lost. Reconnecting..." />
      ) : null}
      {progress.connection === "lost" ? (
        <Alert tone="error" title="Lost the connection to the server">
          The analysis may still be running. Reload the page to reconnect.
        </Alert>
      ) : null}

      {progress.done && !progress.done.ok ? (
        <Alert tone="error" title="The analysis stopped">
          {progress.done.final_error ?? "An unexpected error occurred."}
          {fatal.length ? (
            <ul className="mt-1 list-disc pl-5">
              {fatal.map((e, i) => (
                <li key={i}>{e.message}</li>
              ))}
            </ul>
          ) : null}
        </Alert>
      ) : null}

      {progress.awaitingConfirmation && progress.proposal ? (
        <SchemaConfirmation
          sessionId={sessionId}
          proposal={progress.proposal}
          onExpired={() => setExpired(true)}
        />
      ) : null}

      {progress.done?.ok ? (
        results && finishedResults ? (
          <Dashboard results={results.results} sessionId={sessionId} sample={results.sample ?? false} />
        ) : resultsError ? (
          <Alert tone="error" title={resultsError} />
        ) : (
          <Spinner label="Loading the dashboard..." />
        )
      ) : null}

      {progress.done?.ok ? null : (
        <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
          <Card title="Progress">
            {start.state === "started" && progress.connection === "connecting" && progress.order.length === 0 ? (
              <Spinner label="Connecting..." />
            ) : (
              <ProgressStepper stages={stepperStages(progress)} />
            )}
          </Card>
          <div className="flex min-w-0 flex-col gap-6">
            {showHealth && !results && !resultsError ? <Spinner label="Loading data health..." /> : null}
            {resultsError ? <Alert tone="error" title={resultsError} /> : null}
            {health ? <DataHealthView health={health} log={results?.results.cleaning_log ?? []} /> : null}
            {!showHealth && !progress.awaitingConfirmation && start.state === "started" ? (
              <Card>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Data health appears here once the data is cleaned.
                </p>
              </Card>
            ) : null}
          </div>
        </div>
      )}
    </>
  );
}
