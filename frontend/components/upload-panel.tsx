"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, type DragEvent } from "react";

import { ApiError, chooseSheet, loadSample, uploadFile, type UploadResponse } from "@/lib/api";
import { ACCEPTED_EXTENSIONS, MAX_UPLOAD_MB, uploadProblem } from "@/lib/upload";

import { Alert, Button, Card, Spinner } from "./ui";

type Busy = null | "upload" | "sample" | "sheet";

function describe(error: unknown): { message: string; problems: string[] } {
  if (error instanceof ApiError) return { message: error.message, problems: error.problems };
  return { message: "Something went wrong. Please try again.", problems: [] };
}

export function UploadPanel() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState<{ message: string; problems: string[] } | null>(null);
  const [pending, setPending] = useState<UploadResponse | null>(null);
  const [sheet, setSheet] = useState("");

  const finish = (response: UploadResponse) => {
    if (response.status === "choose_sheet") {
      setPending(response);
      setSheet(response.sheets?.[0] ?? "");
      return;
    }
    router.push(`/analysis/${response.session_id}`);
  };

  const run = async (kind: Exclude<Busy, null>, action: () => Promise<UploadResponse>) => {
    setBusy(kind);
    setError(null);
    try {
      finish(await action());
    } catch (e) {
      setError(describe(e));
    } finally {
      setBusy(null);
    }
  };

  const onFile = (file: File | undefined) => {
    if (!file) return;
    const problem = uploadProblem(file);
    if (problem) {
      setError({ message: problem, problems: [] });
      return;
    }
    setPending(null);
    void run("upload", () => uploadFile(file));
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (!busy) onFile(event.dataTransfer.files[0]);
  };

  return (
    <Card title="Upload customer data">
      <div className="flex flex-col gap-4">
        <Alert tone="warning" title="Use anonymised or sample data only.">
          Remove names, emails, phone numbers and other personal details before uploading. Files are deleted after 2
          hours.
        </Alert>

        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`flex flex-col items-center gap-3 rounded-xl border-2 border-dashed px-4 py-10 text-center transition-colors ${
            dragging ? "border-blue-500 bg-blue-50 dark:bg-blue-950" : "border-gray-300 dark:border-gray-700"
          }`}
        >
          <p className="font-medium">Drag a file here</p>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            CSV or Excel (.xlsx), up to {MAX_UPLOAD_MB} MB, 100 to 100,000 rows, one row per customer with a churn
            column.
          </p>
          <input
            ref={input}
            type="file"
            accept={ACCEPTED_EXTENSIONS.join(",")}
            className="sr-only"
            aria-label="Choose a file"
            onChange={(event) => {
              onFile(event.target.files?.[0]);
              event.target.value = ""; // allow picking the same file again
            }}
          />
          <div className="flex flex-wrap justify-center gap-2">
            <Button onClick={() => input.current?.click()} disabled={busy !== null}>
              Choose a file
            </Button>
            <Button variant="secondary" onClick={() => void run("sample", () => loadSample())} disabled={busy !== null}>
              Try sample data
            </Button>
          </div>
          {busy === "upload" ? <Spinner label="Uploading and checking the file..." /> : null}
          {busy === "sample" ? <Spinner label="Loading the Telco sample..." /> : null}
        </div>

        {pending ? (
          <div className="flex flex-col gap-3 rounded-lg border border-gray-200 p-4 dark:border-gray-800">
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium">{pending.filename} has several sheets. Which one holds the customers?</span>
              <select
                value={sheet}
                onChange={(event) => setSheet(event.target.value)}
                className="min-h-10 rounded-lg border border-gray-300 bg-white px-2 dark:border-gray-700 dark:bg-gray-900"
              >
                {(pending.sheets ?? []).map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex items-center gap-3">
              <Button
                disabled={!sheet || busy !== null}
                onClick={() => void run("sheet", () => chooseSheet(pending.session_id, sheet))}
              >
                Use this sheet
              </Button>
              {busy === "sheet" ? <Spinner label="Reading the sheet..." /> : null}
            </div>
          </div>
        ) : null}

        {error ? (
          <Alert tone="error" title={error.message}>
            {error.problems.length ? (
              <ul className="list-disc pl-5">
                {error.problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            ) : null}
          </Alert>
        ) : null}
      </div>
    </Card>
  );
}
