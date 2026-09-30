"use client";

import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  createExperiment,
  getSegmentOptions,
  previewDesign,
  type Design,
  type DesignInputs,
  type Experiment,
  type SegmentColumn,
  type SegmentFilter,
} from "@/lib/api";
import { formatCount, formatPercent } from "@/lib/format";
import { segmentText } from "@/lib/experiments";
import type { ResultsPayload } from "@/lib/results";

import { Tex } from "../hypothesis/tex";
import { Alert, Button, Card, Spinner } from "../ui";
import { SegmentBuilder } from "./segment-builder";

const PREVIEW_DELAY_MS = 300;
// Sent only when changed, so the design records them as "default" rather than "user".
const DEFAULTS = { alpha: 0.05, power: 0.8, control_share: 0.5 } as const;
const fieldClass =
  "min-h-10 w-full rounded-lg border border-gray-300 bg-white px-3 text-sm dark:border-gray-700 dark:bg-gray-900";

type Named = { name: string; filters: SegmentFilter[] };

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium">{label}</span>
      {children}
      {hint ? <span className="text-xs text-gray-500">{hint}</span> : null}
    </label>
  );
}

function Slider({
  label,
  value,
  min,
  max,
  step,
  display,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  display: string;
  onChange: (v: number) => void;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="flex justify-between font-medium">
        {label} <span className="tabular-nums">{display}</span>
      </span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  );
}

function DesignPreview({ design, error, busy }: { design: Design | null; error: string | null; busy: boolean }) {
  if (error) return <Alert tone="error" title={error} />;
  if (!design) return busy ? <Spinner label="Calculating the sample size..." /> : null;
  const d = design;
  return (
    <div className="flex flex-col gap-3 text-sm" aria-live="polite">
      <div className="grid grid-cols-3 gap-2">
        {[
          ["Treatment", d.n_treatment],
          ["Control", d.n_control],
          ["Total", d.n_total],
        ].map(([label, n]) => (
          <div key={label} className="rounded-lg bg-gray-50 p-2 dark:bg-gray-900">
            <p className="text-xs text-gray-500">{label}</p>
            <p className="text-xl font-semibold tabular-nums">{formatCount(n as number)}</p>
          </div>
        ))}
      </div>
      <p>
        Detects a drop from {formatPercent(d.inputs.baseline_rate, 1)} to {formatPercent(d.treatment_rate, 1)} churn (
        {formatPercent(d.absolute_mde, 1)} points, {formatPercent(d.relative_mde, 0)} relative) with{" "}
        {formatPercent(d.inputs.power, 0)} power at α = {d.inputs.alpha}.
      </p>
      {d.inputs.n_available != null ? (
        <p className={d.feasible ? "text-green-700 dark:text-green-300" : "text-amber-800 dark:text-amber-200"}>
          {formatCount(d.inputs.n_available)} customers match the segment
          {d.feasible ? ": enough." : "."}
          {d.detectable_with_available
            ? ` Smallest detectable drop with them: ${formatPercent(d.detectable_with_available.absolute, 1)} points.`
            : ""}
        </p>
      ) : null}
      {d.duration_days != null ? <p>Expected duration: about {formatCount(d.duration_days)} days of new customers.</p> : null}
      {(d.warnings ?? []).map((w) => (
        <Alert key={w} tone="warning">
          {w}
        </Alert>
      ))}
      <div className="overflow-x-auto">
        <Tex latex={d.formula} block />
      </div>
      <ul className="flex flex-wrap gap-2 text-xs text-gray-600 dark:text-gray-400">
        {(d.assumptions ?? []).map((a) => (
          <li key={a.name}>
            <span className="mr-1 rounded bg-gray-100 px-1.5 py-0.5 font-medium dark:bg-gray-800">{a.source}</span>
            {a.name.replace("_", " ")}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function DesignWizard({
  results,
  sessionId,
  actor,
  onCreated,
  onCancel,
}: {
  results: ResultsPayload;
  sessionId: string;
  actor: string;
  onCreated: (exp: Experiment) => void;
  onCancel: () => void;
}) {
  const recommendations = results.final_recommendations ?? [];
  const catalog = (results.offer_effectiveness?.offers ?? []).map((o) => o.offer);
  const [columns, setColumns] = useState<SegmentColumn[]>([]);
  const [columnsError, setColumnsError] = useState<string | null>(null);

  const [recId, setRecId] = useState("");
  const [name, setName] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [offer, setOffer] = useState(catalog[0] ?? "");
  const [filters, setFilters] = useState<SegmentFilter[]>([]);
  const [prereg, setPrereg] = useState<Named[]>([]);
  const [mdeType, setMdeType] = useState<"absolute" | "relative">("absolute");
  const [mde, setMde] = useState(0.05);
  const [power, setPower] = useState(0.8);
  const [alpha, setAlpha] = useState(0.05);
  const [controlShare, setControlShare] = useState(0.5);
  const [monthlyVolume, setMonthlyVolume] = useState("");
  const [windowDays, setWindowDays] = useState(90);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [guardrails, setGuardrails] = useState<("complaints" | "arpu")[]>(["complaints", "arpu"]);

  const [design, setDesign] = useState<Design | null>(null);
  const [designError, setDesignError] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<ApiError | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getSegmentOptions(sessionId, controller.signal)
      .then(setColumns)
      .catch((e: unknown) => {
        if (!controller.signal.aborted) setColumnsError(e instanceof ApiError ? e.message : "Could not load the columns.");
      });
    return () => controller.abort();
  }, [sessionId]);

  const inputs: DesignInputs = useMemo(
    () => ({
      session_id: sessionId,
      source_recommendation_id: recId || null,
      segment_definition: { description: "", filters },
      mde,
      mde_type: mdeType,
      ...(alpha !== DEFAULTS.alpha ? { alpha } : {}),
      ...(power !== DEFAULTS.power ? { power } : {}),
      ...(controlShare !== DEFAULTS.control_share ? { control_share: controlShare } : {}),
      monthly_volume: monthlyVolume ? Number(monthlyVolume) : null,
      preregistered_segments: prereg.filter((p) => p.name.trim() && p.filters.length),
    }),
    [sessionId, recId, filters, mde, mdeType, alpha, power, controlShare, monthlyVolume, prereg],
  );

  // Live sample size: recomputed in Python as the sliders move (debounced).
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setPreviewing(true);
      previewDesign(inputs, controller.signal)
        .then((d) => {
          setDesign(d);
          setDesignError(null);
        })
        .catch((e: unknown) => {
          if (controller.signal.aborted) return;
          setDesign(null);
          setDesignError(e instanceof ApiError ? e.message : "Could not calculate the sample size.");
        })
        .finally(() => {
          if (!controller.signal.aborted) setPreviewing(false);
        });
    }, PREVIEW_DELAY_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [inputs]);

  const chooseRecommendation = (id: string) => {
    setRecId(id);
    const rec = recommendations.find((r) => r.id === id);
    if (rec) {
      if (!name) setName(rec.action.slice(0, 120));
      if (!hypothesis) {
        setHypothesis(`Offering this lowers churn among ${rec.target_segment}: ${rec.action.replace(/\.$/, "")}.`);
      }
    }
  };

  const save = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const exp = await createExperiment({
        ...inputs,
        name,
        hypothesis,
        offer,
        outcome_window_days: windowDays,
        guardrail_metrics: guardrails,
        planned_start: start || null,
        planned_end: end || null,
        segment_definition: { description: segmentText(filters), filters },
        created_by: actor,
      });
      onCreated(exp);
    } catch (e) {
      setSaveError(e instanceof ApiError ? e : new ApiError("network", "Could not save the experiment."));
    } finally {
      setSaving(false);
    }
  };

  const canSave = Boolean(name.trim() && hypothesis.trim() && offer.trim() && actor.trim() && design && !saving);

  return (
    <Card title="New experiment" actions={<Button variant="secondary" onClick={onCancel}>Cancel</Button>}>
      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <div className="flex flex-col gap-4">
          {recommendations.length ? (
            <Field label="Start from a recommendation" hint="Optional: fills in the name and hypothesis.">
              <select className={fieldClass} value={recId} onChange={(e) => chooseRecommendation(e.target.value)}>
                <option value="">None</option>
                {recommendations.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.action}
                  </option>
                ))}
              </select>
            </Field>
          ) : null}
          <Field label="Name">
            <input className={fieldClass} value={name} maxLength={200} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Hypothesis">
            <textarea className={`${fieldClass} py-2`} rows={2} value={hypothesis} maxLength={2000} onChange={(e) => setHypothesis(e.target.value)} />
          </Field>
          <Field
            label="Offer"
            hint={catalog.length ? "Use a name from the offer data so the result can feed next best offer." : undefined}
          >
            <input className={fieldClass} list="offer-catalog" value={offer} maxLength={200} onChange={(e) => setOffer(e.target.value)} />
            <datalist id="offer-catalog">
              {catalog.map((o) => (
                <option key={o} value={o} />
              ))}
            </datalist>
          </Field>

          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-sm font-medium">Who is eligible</legend>
            {columnsError ? <Alert tone="error" title={columnsError} /> : null}
            <SegmentBuilder columns={columns} filters={filters} onChange={setFilters} />
          </fieldset>

          <fieldset className="flex flex-col gap-3">
            <legend className="mb-1 text-sm font-medium">Sensitivity</legend>
            <div className="flex gap-4 text-sm">
              {(["absolute", "relative"] as const).map((t) => (
                <label key={t} className="flex items-center gap-1">
                  <input
                    type="radio"
                    name="mde-type"
                    checked={mdeType === t}
                    onChange={() => {
                      setMdeType(t);
                      setMde(t === "absolute" ? 0.05 : 0.2);
                    }}
                  />
                  {t === "absolute" ? "Percentage points" : "Relative drop"}
                </label>
              ))}
            </div>
            <Slider
              label="Minimum detectable effect"
              value={mde}
              min={mdeType === "absolute" ? 0.005 : 0.02}
              max={mdeType === "absolute" ? 0.2 : 0.6}
              step={mdeType === "absolute" ? 0.005 : 0.01}
              display={mdeType === "absolute" ? `${(mde * 100).toFixed(1)} points` : formatPercent(mde, 0)}
              onChange={setMde}
            />
            <Slider label="Power" value={power} min={0.5} max={0.99} step={0.01} display={formatPercent(power, 0)} onChange={setPower} />
            <Slider
              label="Control share"
              value={controlShare}
              min={0.1}
              max={0.9}
              step={0.05}
              display={formatPercent(controlShare, 0)}
              onChange={setControlShare}
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Significance level (α)">
                <select className={fieldClass} value={alpha} onChange={(e) => setAlpha(Number(e.target.value))}>
                  {[0.01, 0.05, 0.1].map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="New eligible customers per month" hint="Optional: estimates the duration.">
                <input className={fieldClass} type="number" min={1} value={monthlyVolume} onChange={(e) => setMonthlyVolume(e.target.value)} />
              </Field>
            </div>
          </fieldset>

          <fieldset className="grid gap-3 sm:grid-cols-3">
            <legend className="mb-1 text-sm font-medium">Timing</legend>
            <Field label="Outcome window (days)">
              <input className={fieldClass} type="number" min={1} max={730} value={windowDays} onChange={(e) => setWindowDays(Number(e.target.value))} />
            </Field>
            <Field label="Planned start">
              <input className={fieldClass} type="date" value={start} onChange={(e) => setStart(e.target.value)} />
            </Field>
            <Field label="Planned end">
              <input className={fieldClass} type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
            </Field>
          </fieldset>

          <fieldset className="flex flex-col gap-1 text-sm">
            <legend className="mb-1 font-medium">Guardrails</legend>
            {(["complaints", "arpu"] as const).map((g) => (
              <label key={g} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={guardrails.includes(g)}
                  onChange={(e) => setGuardrails(e.target.checked ? [...guardrails, g] : guardrails.filter((x) => x !== g))}
                />
                {g === "complaints" ? "Complaints must not rise" : "Revenue per customer (ARPU) must not fall"}
              </label>
            ))}
          </fieldset>

          <fieldset className="flex flex-col gap-3">
            <legend className="mb-1 text-sm font-medium">Pre-registered segments (optional)</legend>
            <p className="text-xs text-gray-500">
              Segments you want broken out in the results. They are fixed at approval and reported as exploratory.
            </p>
            {prereg.map((seg, i) => (
              <div key={i} className="flex flex-col gap-2 rounded-lg border border-gray-200 p-3 dark:border-gray-800">
                <div className="flex gap-2">
                  <input
                    aria-label={`Segment ${i + 1} name`}
                    placeholder="Segment name"
                    className={fieldClass}
                    value={seg.name}
                    maxLength={100}
                    onChange={(e) => setPrereg(prereg.map((p, j) => (j === i ? { ...p, name: e.target.value } : p)))}
                  />
                  <Button variant="secondary" onClick={() => setPrereg(prereg.filter((_, j) => j !== i))}>
                    Remove
                  </Button>
                </div>
                <SegmentBuilder
                  columns={columns}
                  filters={seg.filters}
                  emptyText="Add at least one filter."
                  onChange={(f) => setPrereg(prereg.map((p, j) => (j === i ? { ...p, filters: f } : p)))}
                />
              </div>
            ))}
            {prereg.length < 5 && columns.length ? (
              <div>
                <Button variant="secondary" onClick={() => setPrereg([...prereg, { name: "", filters: [] }])}>
                  Add segment
                </Button>
              </div>
            ) : null}
          </fieldset>
        </div>

        <aside className="flex flex-col gap-4 lg:sticky lg:top-4 lg:self-start">
          <h3 className="font-semibold">Sample size</h3>
          <DesignPreview design={design} error={designError} busy={previewing} />
          {saveError ? (
            <Alert tone="error" title={saveError.message}>
              {saveError.problems.length ? (
                <ul className="list-disc pl-5">
                  {saveError.problems.map((p) => (
                    <li key={p}>{p}</li>
                  ))}
                </ul>
              ) : null}
            </Alert>
          ) : null}
          {!actor.trim() ? <p className="text-xs text-amber-700 dark:text-amber-300">Enter your name at the top to save.</p> : null}
          <Button onClick={() => void save()} disabled={!canSave}>
            {saving ? "Saving..." : "Save draft"}
          </Button>
        </aside>
      </div>
    </Card>
  );
}
