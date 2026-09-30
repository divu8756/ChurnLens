"use client";

import { useEffect, useState } from "react";

import {
  ApiError,
  explainBusinessMetrics,
  getBusinessMetrics,
  recomputeBusinessMetrics,
  type BusinessAssumptions,
  type BusinessExplanation,
  type BusinessMetrics,
} from "@/lib/api";
import { formatCount, formatMoney, formatPercent, formatStat } from "@/lib/format";
import { isEdited, KPI_HELP, sameAssumptions } from "@/lib/metrics";
import { PALETTE } from "@/lib/palette";

import { PlotlyChart } from "../charts/plotly-chart";
import { Tex } from "../hypothesis/tex";
import { KpiTile, SourceChip } from "../metrics/kpi-tile";
import { Alert, Button, Card, EmptyState, Spinner } from "../ui";

const DEBOUNCE_MS = 400;
type OfferField = "acceptance" | "save_rate" | "cost";
const fieldClass =
  "min-h-10 w-full rounded-lg border border-gray-300 bg-white px-2 text-sm tabular-nums dark:border-gray-700 dark:bg-gray-900";

function num(text: string): number | null {
  if (text.trim() === "") return null;
  const value = Number(text);
  return Number.isFinite(value) ? value : null;
}

function NumberInput({
  label,
  value,
  placeholder,
  step,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number | null | undefined;
  placeholder: string;
  step: number;
  min: number;
  max?: number;
  onChange: (v: number | null) => void;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="font-medium">{label}</span>
      <input
        type="number"
        className={fieldClass}
        value={value ?? ""}
        placeholder={placeholder}
        step={step}
        min={min}
        max={max}
        onChange={(e) => onChange(num(e.target.value))}
      />
    </label>
  );
}

function AssumptionsPanel({
  metrics,
  assumptions,
  onChange,
}: {
  metrics: BusinessMetrics;
  assumptions: BusinessAssumptions;
  onChange: (a: BusinessAssumptions) => void;
}) {
  const months = metrics.revenue_at_risk?.months_remaining ?? 12;
  const plan = metrics.ab_plan;
  const setOffer = (name: string, field: OfferField, value: number | null) => {
    const offers = { ...(assumptions.offers ?? {}) };
    offers[name] = { ...(offers[name] ?? {}), [field]: value };
    onChange({ ...assumptions, offers });
  };
  return (
    <Card
      title="Assumptions"
      actions={
        isEdited(assumptions) ? (
          <Button variant="secondary" onClick={() => onChange({})}>
            Reset to defaults
          </Button>
        ) : null
      }
    >
      <div className="flex flex-col gap-4 text-sm">
        <p className="text-xs text-gray-600 dark:text-gray-400">
          Every number on this tab rests on these ASSUMPTIONS. Edits are recomputed on the server. Chips show where each
          value comes from: default (offers.yaml), data (your offer data or a decided experiment) or user (your edit).
        </p>
        <div className="grid gap-3 sm:grid-cols-3">
          <NumberInput
            label="Months of revenue per saved customer"
            value={assumptions.months_remaining}
            placeholder={String(months)}
            step={1}
            min={1}
            max={60}
            onChange={(v) => onChange({ ...assumptions, months_remaining: v })}
          />
          <NumberInput
            label="A/B test: relative drop to detect"
            value={assumptions.relative_lift}
            placeholder={String(plan?.relative_lift ?? 0.2)}
            step={0.05}
            min={0.01}
            max={0.9}
            onChange={(v) => onChange({ ...assumptions, relative_lift: v })}
          />
          <NumberInput
            label="A/B test: power"
            value={assumptions.power}
            placeholder={String(plan?.power ?? 0.8)}
            step={0.05}
            min={0.5}
            max={0.99}
            onChange={(v) => onChange({ ...assumptions, power: v })}
          />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[34rem] text-left text-sm">
            <caption className="sr-only">Offer assumptions</caption>
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-800">
                <th className="py-2 pr-3 font-medium">Offer</th>
                <th className="py-2 pr-3 font-medium">Acceptance</th>
                <th className="py-2 pr-3 font-medium">Save rate</th>
                <th className="py-2 font-medium">Cost</th>
              </tr>
            </thead>
            <tbody>
              {(metrics.offers ?? []).map((o) => {
                const edit = assumptions.offers?.[o.name] ?? {};
                const cell = (field: OfferField, current: number, step: number, max?: number) => (
                  <td className="py-1.5 pr-3 align-top">
                    <div className="flex flex-col gap-1">
                      <input
                        type="number"
                        aria-label={`${o.name}: ${field.replace("_", " ")}`}
                        className={fieldClass}
                        value={edit[field] ?? ""}
                        placeholder={String(Number(current.toFixed(3)))}
                        step={step}
                        min={0}
                        max={max}
                        onChange={(e) => setOffer(o.name, field, num(e.target.value))}
                      />
                      <SourceChip source={o.sources[field] ?? "default"} />
                    </div>
                  </td>
                );
                return (
                  <tr key={o.name} className="border-b border-gray-100 dark:border-gray-900">
                    <td className="py-1.5 pr-3 align-top">
                      {o.name}
                      <span className="block text-xs text-gray-500">{o.cost_basis === "per_accepted" ? "cost per accepted offer" : "cost per targeted customer"}</span>
                    </td>
                    {cell("acceptance", o.acceptance, 0.05, 1)}
                    {cell("save_rate", o.save_rate, 0.05, 1)}
                    {cell("cost", o.cost, 1)}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  );
}

function ExplanationCard({ sessionId, assumptions }: { sessionId: string; assumptions: BusinessAssumptions }) {
  const [shown, setShown] = useState<{ text: BusinessExplanation; for: BusinessAssumptions } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const stale = shown !== null && !sameAssumptions(shown.for, assumptions);

  const write = async () => {
    setBusy(true);
    setError(null);
    const snapshot = assumptions;
    try {
      setShown({ text: await explainBusinessMetrics(sessionId, snapshot), for: snapshot });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not write the explanation.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="In plain English">
      <div className="flex flex-col gap-3 text-sm">
        {stale ? (
          <Alert tone="warning" title={isEdited(shown.for) ? "Based on earlier assumptions" : "Based on default assumptions"}>
            The numbers changed since this was written.
          </Alert>
        ) : null}
        {shown ? (
          <>
            <p>{shown.text.sentences.join(" ")}</p>
            <p className="text-xs text-gray-500">
              {shown.text.source === "ai"
                ? "Written by AI; every number was checked against the computed metrics."
                : "Standard wording (the AI version was unavailable or did not pass the checks)."}
            </p>
          </>
        ) : null}
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={() => void write()} disabled={busy}>
            {shown ? (stale ? "Regenerate explanation" : "Write again") : "Explain these numbers"}
          </Button>
          {busy ? <Spinner label="Writing..." /> : null}
        </div>
        {error ? <Alert tone="error" title={error} /> : null}
      </div>
    </Card>
  );
}

function AbPlanCard({ metrics }: { metrics: BusinessMetrics }) {
  const plan = metrics.ab_plan;
  if (!plan) return null;
  return (
    <Card title="A/B test plan">
      {!plan.available ? (
        <EmptyState>{plan.reason}</EmptyState>
      ) : (
        <div className="flex flex-col gap-3 text-sm">
          <p>
            To confirm the offers work for {plan.segment} ({formatCount(plan.segment_customers)} customers, churn{" "}
            {formatPercent(plan.p1, 1)}), test with{" "}
            <span className="font-semibold tabular-nums">{formatCount(plan.n_per_arm)}</span> customers per group (
            {formatCount(plan.total_n)} in total).
          </p>
          <div className="overflow-x-auto">
            <Tex latex={plan.formula_latex ?? ""} block />
          </div>
          <dl className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            {[
              ["p1 (now)", formatPercent(plan.p1, 2)],
              ["p2 (target)", formatPercent(plan.p2, 2)],
              ["Cohen's h", formatStat(plan.cohens_h, 4)],
              ["z (1 - α/2)", formatStat(plan.z_alpha, 3)],
              ["z (1 - β)", formatStat(plan.z_beta, 3)],
              ["α", String(plan.alpha)],
              ["Power", formatPercent(plan.power, 0)],
              ["Relative drop", formatPercent(plan.relative_lift, 0)],
            ].map(([k, v]) => (
              <div key={k} className="rounded bg-gray-50 p-2 dark:bg-gray-900">
                <dt className="text-gray-500">{k}</dt>
                <dd className="tabular-nums">{v}</dd>
              </div>
            ))}
          </dl>
          {(plan.warnings ?? []).map((w) => (
            <Alert key={w} tone="warning">
              {w}
            </Alert>
          ))}
        </div>
      )}
    </Card>
  );
}

export function BusinessImpactTab({ sessionId }: { sessionId: string }) {
  const [metrics, setMetrics] = useState<BusinessMetrics | null>(null);
  // null = untouched: the defaults from GET; any edit (including a reset) is recomputed.
  const [edits, setEdits] = useState<BusinessAssumptions | null>(null);
  const assumptions = edits ?? {};
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getBusinessMetrics(sessionId, controller.signal)
      .then(setMetrics)
      .catch((e: unknown) => {
        if (!controller.signal.aborted) setError(e instanceof ApiError ? e.message : "Could not load the business metrics.");
      });
    return () => controller.abort();
  }, [sessionId]);

  // Edited assumptions are recomputed in Python (debounced 400 ms); nothing is computed here.
  useEffect(() => {
    if (edits === null) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setUpdating(true);
      recomputeBusinessMetrics(sessionId, edits, controller.signal)
        .then((m) => {
          setMetrics(m);
          setError(null);
        })
        .catch((e: unknown) => {
          if (!controller.signal.aborted) setError(e instanceof ApiError ? e.message : "Could not recompute.");
        })
        .finally(() => {
          if (!controller.signal.aborted) setUpdating(false);
        });
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [sessionId, edits]);

  if (!metrics) return error ? <Alert tone="error" title={error} /> : <Spinner label="Loading business metrics..." />;
  if (!metrics.enabled) return <Alert tone="info" title="Business metrics are off for this data">{metrics.reason}</Alert>;
  const k = metrics.kpis!;
  const segments = (metrics.roi_by_segment ?? []).slice(0, 15);

  return (
    <div className="flex flex-col gap-6">
      {error ? <Alert tone="error" title={error} /> : null}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" aria-busy={updating}>
        <KpiTile
          label="Revenue at risk"
          value={formatMoney(k.revenue_at_risk)}
          note={`over ${metrics.revenue_at_risk?.months_remaining} months · ASSUMPTION`}
          help={KPI_HELP.revenue_at_risk}
        />
        <KpiTile label="Expected saving" value={formatMoney(k.expected_saving)} note="ASSUMPTION-based estimate" help={KPI_HELP.expected_saving} />
        <KpiTile
          label="Customers with an offer"
          value={formatCount(k.customers_with_offer)}
          note={`of ${formatCount(k.customers_scored)} scored`}
          help={KPI_HELP.customers_with_offer}
        />
        <KpiTile label="Overall ROI" value={k.overall_roi == null ? "–" : `${formatStat(k.overall_roi, 2)}x`} help={KPI_HELP.overall_roi} />
      </div>
      {updating ? <Spinner label="Recomputing..." /> : null}
      {(metrics.warnings ?? []).map((w) => (
        <Alert key={w} tone="warning">
          {w}
        </Alert>
      ))}

      <ExplanationCard sessionId={sessionId} assumptions={assumptions} />
      <AssumptionsPanel metrics={metrics} assumptions={assumptions} onChange={setEdits} />

      <Card title="ROI by segment">
        {segments.length ? (
          <PlotlyChart
            label="Expected net saving by segment"
            height={Math.max(260, 40 + segments.length * 28)}
            data={[
              {
                type: "bar",
                orientation: "h",
                name: "Expected saving",
                y: segments.map((s) => s.segment),
                x: segments.map((s) => s.total_expected_saving),
                text: segments.map((s) => `${formatCount(s.customers)} customers, ROI ${s.roi == null ? "–" : formatStat(s.roi, 2)}x`),
                hovertemplate: "%{y}: %{x:,.0f} (%{text})<extra></extra>",
                textposition: "none", // details on hover only; labels do not fit on a phone
                marker: { color: PALETTE.blue },
              },
            ]}
            layout={{ yaxis: { automargin: true, autorange: "reversed" }, xaxis: { title: { text: "Expected net saving" } }, showlegend: false }}
          />
        ) : (
          <EmptyState>No customer has an offer with a positive expected saving.</EmptyState>
        )}
      </Card>

      <AbPlanCard metrics={metrics} />

      <Card title="Next best offer (top 50 by expected saving)">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[36rem] text-left text-sm">
            <caption className="sr-only">Customers with the highest expected saving and their best offer</caption>
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-800">
                <th className="py-2 pr-3 font-medium">Customer</th>
                <th className="py-2 pr-3 font-medium">Risk</th>
                <th className="py-2 pr-3 text-right font-medium">P(churn)</th>
                <th className="py-2 pr-3 font-medium">Best offer</th>
                <th className="py-2 text-right font-medium">Expected saving</th>
              </tr>
            </thead>
            <tbody>
              {(metrics.next_best_offers ?? []).map((r) => (
                <tr key={r.customer_id} className="border-b border-gray-100 dark:border-gray-900">
                  <td className="py-1.5 pr-3 font-mono text-xs">{r.customer_id}</td>
                  <td className="py-1.5 pr-3">{r.risk_band}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{formatPercent(r.p_churn, 1)}</td>
                  <td className="py-1.5 pr-3">
                    {r.best_offer}
                    {r.runner_up ? <span className="block text-xs text-gray-500">then {r.runner_up}</span> : null}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">{formatMoney(r.expected_saving)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="All assumptions">
        <ul className="flex flex-col gap-1 text-xs text-gray-600 dark:text-gray-400">
          {(metrics.assumptions ?? []).map((a) => (
            <li key={a.name}>
              <span className="mr-1 font-semibold">ASSUMPTION</span>
              <SourceChip source={a.source} /> {a.name}: {a.value == null ? "not set" : formatStat(a.value, a.value < 1 ? 3 : 2)}{" "}
              {a.unit} — {a.meaning}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
