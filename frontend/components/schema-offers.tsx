import { OFFER_FIELDS, offerColumnNames, withOfferField, type SchemaDraft } from "@/lib/schema-form";

const selectClass =
  "min-h-9 w-full rounded-lg border border-gray-300 bg-white px-2 text-sm dark:border-gray-700 dark:bg-gray-900";

/** Offer / campaign columns: treatments, analysed separately and kept out of the churn model. */
export function SchemaOffers({
  draft,
  names,
  onChange,
}: {
  draft: SchemaDraft;
  names: string[];
  onChange: (draft: SchemaDraft) => void;
}) {
  const offers = draft.offer_columns;
  const listShape = offers != null && (Array.isArray(offers.shown) || Array.isArray(offers.accepted));
  const other = offers?.other ?? [];
  return (
    <fieldset className="flex flex-col gap-3 rounded-lg border border-gray-200 p-4 dark:border-gray-800">
      <legend className="px-1 text-sm font-medium">Retention offers (optional)</legend>
      <p className="text-xs text-gray-500">
        Columns describing a retention offer or campaign. They are what you did, not who the customer is, so they are
        analysed on their own and left out of the churn model. Leave &ldquo;Offer shown&rdquo; empty to skip this.
      </p>
      {listShape ? (
        <p className="text-sm">
          One column per offer: {offerColumnNames(offers).join(", ")}.
          <button type="button" className="ml-2 text-blue-600 underline" onClick={() => onChange({ ...draft, offer_columns: null })}>
            Skip offer analysis
          </button>
        </p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {OFFER_FIELDS.map((field) => {
            const value = offers?.[field.key];
            return (
              <label key={field.key} className="flex flex-col gap-1 text-sm" title={field.help}>
                <span className="font-medium">{field.label}</span>
                <select
                  className={selectClass}
                  value={typeof value === "string" ? value : ""}
                  disabled={field.key !== "shown" && !offers}
                  onChange={(e) => onChange(withOfferField(draft, field.key, e.target.value))}
                >
                  <option value="">None</option>
                  {names.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
            );
          })}
        </div>
      )}
      {offers && other.length ? (
        <p className="text-xs text-gray-500">Also treated as campaign columns: {other.join(", ")}.</p>
      ) : null}
    </fieldset>
  );
}
