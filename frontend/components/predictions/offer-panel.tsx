"use client";

import { useEffect, useState } from "react";

import { ApiError, generateOfferMessage, getNextBestOffer, type NextBestOffer, type OfferMessage } from "@/lib/api";
import { formatPercent, formatStat } from "@/lib/format";
import { GENERAL_FORMULA, LIFT_FORMULA, formatOfferValue, substitutedFormula } from "@/lib/offers";

import { Tex } from "../hypothesis/tex";
import { Alert, Button, Spinner } from "../ui";

type Loaded = { customerId: string; offer?: NextBestOffer; error?: string };

function Input({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-lg bg-gray-50 p-2 dark:bg-gray-900">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="tabular-nums">{value}</p>
      {note ? <p className="text-xs text-amber-700 dark:text-amber-300">{note}</p> : null}
    </div>
  );
}

function MessageBox({ sessionId, customerId }: { sessionId: string; customerId: string }) {
  const [message, setMessage] = useState<OfferMessage | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generate = async () => {
    setBusy(true);
    setError(null);
    try {
      setMessage(await generateOfferMessage(sessionId, customerId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not write the message.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-3">
        <Button variant="secondary" onClick={() => void generate()} disabled={busy}>
          {message ? "Show message again" : "Generate message"}
        </Button>
        {busy ? <Spinner label="Writing the message..." /> : null}
      </div>
      {error ? <Alert tone="error" title={error} /> : null}
      {message ? (
        <div className="flex flex-col gap-2 rounded-lg border border-gray-200 p-3 text-sm dark:border-gray-800">
          <p>{message.message}</p>
          <p className="font-mono text-xs">
            SMS ({message.sms.length}/160): {message.sms}
          </p>
          <p className="text-xs text-gray-500">
            {message.source === "ai"
              ? "Written by AI; every number was checked against the offer."
              : "Standard wording (the AI version was unavailable or did not pass the checks)."}
            {message.cached ? " Reused from earlier, no new AI call." : ""}
          </p>
        </div>
      ) : null}
    </div>
  );
}

/** "Why this offer": the expected-value formula with this customer's inputs. */
export function OfferPanel({ sessionId, customerId }: { sessionId: string; customerId: string }) {
  const [loaded, setLoaded] = useState<Loaded>({ customerId: "" });

  useEffect(() => {
    const controller = new AbortController();
    getNextBestOffer(sessionId, customerId, controller.signal)
      .then((offer) => setLoaded({ customerId, offer }))
      .catch((e: unknown) => {
        if (!controller.signal.aborted) {
          setLoaded({ customerId, error: e instanceof ApiError ? e.message : "Could not load the offer." });
        }
      });
    return () => controller.abort();
  }, [sessionId, customerId]);

  if (loaded.customerId !== customerId) return <Spinner label="Loading the offer..." />;
  if (loaded.error || !loaded.offer) return <Alert tone="error" title={loaded.error ?? "Not available."} />;
  const o = loaded.offer;
  const unit = o.value_unit;

  return (
    <div className="flex flex-col gap-4 text-sm">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <p>
          <span className="text-gray-500">Next best offer: </span>
          <span className="font-semibold">{o.best_offer}</span>
        </p>
        <p>
          <span className="text-gray-500">Expected value: </span>
          <span className="font-semibold tabular-nums">{formatOfferValue(o.expected_value, unit)}</span>
        </p>
        {o.runner_up ? (
          <p className="text-gray-500">
            Runner-up: {o.runner_up} ({formatOfferValue(o.runner_up_value, unit)})
          </p>
        ) : null}
      </div>
      {o.no_offer_reason ? <Alert tone="info" title={`No offer: ${o.no_offer_reason}.`} /> : null}

      <div>
        <p className="mb-1 font-medium">Why this offer</p>
        <Tex latex={GENERAL_FORMULA} block />
        <Tex latex={LIFT_FORMULA} block />
        <Tex latex={substitutedFormula(o)} block />
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Input label="P(churn)" value={formatPercent(o.p_churn, 1)} />
        <Input label="P(accept)" value={formatPercent(o.p_accept, 1)} note={o.low_data ? "low data: segment rate" : undefined} />
        <Input label="Stay if accepted" value={formatPercent(o.p_stay_if_accepted, 1)} />
        <Input label="Stay if declined" value={formatPercent(o.p_stay_if_declined, 1)} />
        <Input label="Retention lift" value={formatStat(o.retention_lift, 3)} />
        <Input label="Customer value" value={unit === "revenue" ? formatOfferValue(o.customer_value, unit) : "1 customer"} />
        <Input label="Cost if accepted" value={formatOfferValue(o.offer_cost ?? 0, "revenue")} />
        <Input label="Offers considered" value={String(o.eligible_offers)} />
      </div>

      <div>
        <p className="mb-1 font-medium">Assumptions</p>
        <ul className="flex flex-col gap-1 text-xs text-gray-600 dark:text-gray-400">
          {o.assumptions.map((a) => (
            <li key={a.name}>
              <span className="mr-1 rounded bg-gray-100 px-1.5 py-0.5 font-medium dark:bg-gray-800">{a.source}</span>
              {a.text}
            </li>
          ))}
        </ul>
      </div>

      {o.best_offer !== "No offer" ? <MessageBox sessionId={sessionId} customerId={customerId} /> : null}
    </div>
  );
}
