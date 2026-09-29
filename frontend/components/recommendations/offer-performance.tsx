"use client";

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { components } from "@/lib/api-types";
import { shortLabel } from "@/lib/drivers";
import { formatCount, formatP, formatPercent } from "@/lib/format";
import { formatOfferValue } from "@/lib/offers";
import { PALETTE } from "@/lib/palette";

import { SignificanceBadge } from "../overview/top-insights";
import { Alert, Card } from "../ui";

type Effectiveness = components["schemas"]["OfferEffectiveness"];
type Offer = components["schemas"]["OfferRow"];

function OfferCard({ offer, auc }: { offer: Offer; auc: number | null | undefined }) {
  return (
    <article className="flex flex-col gap-2 rounded-xl border border-gray-200 p-4 dark:border-gray-800">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-semibold">{offer.offer}</h3>
        {offer.test ? <SignificanceBadge significant={offer.test.significant} /> : null}
      </div>
      <dl className="grid grid-cols-3 gap-2 text-sm">
        <div>
          <dt className="text-xs text-gray-500">Shown</dt>
          <dd className="tabular-nums">{formatCount(offer.shown)}</dd>
          <dd className="text-xs text-gray-500">{formatPercent(offer.acceptance_rate, 1)} accepted</dd>
        </div>
        <div>
          <dt className="text-xs text-gray-500">Churn if accepted</dt>
          <dd className="tabular-nums">{formatPercent(offer.acceptors.churn_rate, 1)}</dd>
          <dd className="text-xs text-gray-500">n = {formatCount(offer.acceptors.n)}</dd>
        </div>
        <div>
          <dt className="text-xs text-gray-500">Churn if declined</dt>
          <dd className="tabular-nums">{formatPercent(offer.decliners.churn_rate, 1)}</dd>
          <dd className="text-xs text-gray-500">n = {formatCount(offer.decliners.n)}</dd>
        </div>
      </dl>
      <p className="text-xs text-gray-500">
        {offer.test ? `${offer.test.test_name}, adjusted p ${formatP(offer.test.p_adjusted)}.` : "Too few customers to test."}
        {auc != null ? ` Acceptance model ROC-AUC ${auc.toFixed(2)}.` : " Acceptance from segment rates (low data)."}
      </p>
    </article>
  );
}

export function OfferPerformance({ effectiveness }: { effectiveness: Effectiveness }) {
  const offers = effectiveness.offers ?? [];
  const nbo = effectiveness.next_best_offer;
  const data = offers.map((o) => ({
    offer: o.offer,
    Accepted: o.acceptors.churn_rate,
    Declined: o.decliners.churn_rate,
  }));
  return (
    <section aria-labelledby="offer-performance" className="flex flex-col gap-3">
      <div>
        <h2 id="offer-performance" className="text-lg font-semibold">
          Offer performance <span className="text-sm font-normal text-gray-500">({offers.length})</span>
        </h2>
        <p className="text-sm text-gray-500">
          How past retention offers did. Never offered: {formatPercent(effectiveness.never_offered.churn_rate, 1)} churn (n ={" "}
          {formatCount(effectiveness.never_offered.n)}); offered: {formatPercent(effectiveness.offered.churn_rate, 1)} (n ={" "}
          {formatCount(effectiveness.offered.n)}).
        </p>
      </div>
      {(effectiveness.warnings ?? []).map((w) => (
        <Alert key={w} tone="warning">
          {w}
        </Alert>
      ))}
      {effectiveness.note ? <p className="text-xs text-gray-500">{effectiveness.note}</p> : null}

      {data.length ? (
        <Card>
          <figure>
            <div className="w-full" style={{ height: 70 + data.length * 44 }}>
              <ResponsiveContainer>
                <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 24, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis
                    type="number"
                    fontSize={12}
                    tickFormatter={(v: number) => formatPercent(v, 0)}
                    label={{ value: "Churn rate", position: "insideBottom", offset: -14, fontSize: 12 }}
                  />
                  <YAxis type="category" dataKey="offer" width={170} fontSize={12} interval={0} tickFormatter={(v: string) => shortLabel(v, 26)} />
                  <Tooltip cursor={{ fill: "rgba(128, 128, 128, 0.15)" }} formatter={(v) => formatPercent(Number(v), 1)} />
                  <Legend verticalAlign="top" wrapperStyle={{ fontSize: 12, paddingBottom: 8 }} />
                  <Bar dataKey="Accepted" fill={PALETTE.blue} />
                  <Bar dataKey="Declined" fill={PALETTE.orange} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <figcaption className="mt-1 text-xs text-gray-500">
              What this shows: churn among customers who accepted each offer vs those who declined it. A gap is an
              association, not proof: acceptors chose to accept.
            </figcaption>
          </figure>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        {offers.map((o) => (
          <OfferCard key={o.offer} offer={o} auc={nbo?.offer_models?.[o.offer]?.roc_auc} />
        ))}
      </div>

      {nbo ? (
        <Card title="Next best offer">
          <p className="mb-2 text-sm text-gray-600 dark:text-gray-400">
            {formatCount(nbo.customers_scored)} Medium and High risk customers scored. Total expected value{" "}
            {formatOfferValue(nbo.total_expected_value, nbo.value_unit)}
            {nbo.value_unit === "revenue" ? "" : " (no revenue column)"}. Open a customer in Risk Predictions to see why.
          </p>
          <ul className="grid gap-1 text-sm sm:grid-cols-2">
            {(nbo.by_offer ?? []).map((b) => (
              <li key={b.offer} className="flex justify-between gap-3 border-b border-gray-100 py-1 dark:border-gray-900">
                <span>{b.offer}</span>
                <span className="tabular-nums text-gray-600 dark:text-gray-400">
                  {formatCount(b.customers)} · {formatOfferValue(b.expected_value, nbo.value_unit)}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
    </section>
  );
}
