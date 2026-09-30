"use client";

import type { SegmentColumn, SegmentFilter } from "@/lib/api";

import { Button } from "../ui";

const NUMERIC_OPS: SegmentFilter["op"][] = ["gte", "gt", "lte", "lt", "eq", "ne"];
const CATEGORY_OPS: SegmentFilter["op"][] = ["eq", "ne", "in", "not_in"];
const OP_LABELS: Record<SegmentFilter["op"], string> = {
  eq: "is",
  ne: "is not",
  in: "is one of",
  not_in: "is none of",
  gt: ">",
  gte: "≥",
  lt: "<",
  lte: "≤",
};

const inputClass =
  "min-h-10 rounded-lg border border-gray-300 bg-white px-2 text-sm dark:border-gray-700 dark:bg-gray-900";

function defaultFilter(col: SegmentColumn): SegmentFilter {
  return col.kind === "numeric"
    ? { column: col.column, op: "gte", value: col.min ?? 0 }
    : { column: col.column, op: "eq", value: col.levels?.[0] ?? "" };
}

function FilterRow({
  filter,
  columns,
  onChange,
  onRemove,
  label,
}: {
  filter: SegmentFilter;
  columns: SegmentColumn[];
  onChange: (f: SegmentFilter) => void;
  onRemove: () => void;
  label: string;
}) {
  const col = columns.find((c) => c.column === filter.column);
  const ops = col?.kind === "numeric" ? NUMERIC_OPS : CATEGORY_OPS;
  const multi = filter.op === "in" || filter.op === "not_in";
  const values = Array.isArray(filter.value) ? filter.value.map(String) : [String(filter.value)];

  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label={label}>
      <select
        aria-label="Column"
        className={inputClass}
        value={filter.column}
        onChange={(e) => {
          const next = columns.find((c) => c.column === e.target.value);
          if (next) onChange(defaultFilter(next));
        }}
      >
        {columns.map((c) => (
          <option key={c.column} value={c.column}>
            {c.column}
          </option>
        ))}
      </select>
      <select
        aria-label="Condition"
        className={inputClass}
        value={filter.op}
        onChange={(e) => {
          const op = e.target.value as SegmentFilter["op"];
          const isMulti = op === "in" || op === "not_in";
          onChange({ ...filter, op, value: isMulti ? values.slice(0, 1) : values[0] ?? "" });
        }}
      >
        {ops.map((op) => (
          <option key={op} value={op}>
            {OP_LABELS[op]}
          </option>
        ))}
      </select>
      {col?.kind === "numeric" ? (
        <input
          aria-label="Value"
          type="number"
          className={`${inputClass} w-28`}
          value={String(filter.value)}
          min={col.min ?? undefined}
          max={col.max ?? undefined}
          onChange={(e) => onChange({ ...filter, value: e.target.value === "" ? 0 : Number(e.target.value) })}
        />
      ) : multi ? (
        <select
          aria-label="Values"
          multiple
          className={`${inputClass} min-h-20`}
          value={values}
          onChange={(e) => onChange({ ...filter, value: Array.from(e.target.selectedOptions, (o) => o.value) })}
        >
          {(col?.levels ?? []).map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
      ) : (
        <select aria-label="Value" className={inputClass} value={values[0]} onChange={(e) => onChange({ ...filter, value: e.target.value })}>
          {(col?.levels ?? []).map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
      )}
      <Button variant="secondary" onClick={onRemove} aria-label={`Remove ${label}`}>
        Remove
      </Button>
    </div>
  );
}

/** Flat AND filters over the analysed session's columns (evaluated in Python). */
export function SegmentBuilder({
  columns,
  filters,
  onChange,
  emptyText = "No filters: all analysed customers.",
}: {
  columns: SegmentColumn[];
  filters: SegmentFilter[];
  onChange: (filters: SegmentFilter[]) => void;
  emptyText?: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      {filters.length ? null : <p className="text-sm text-gray-500">{emptyText}</p>}
      {filters.map((f, i) => (
        <FilterRow
          key={i}
          label={`Filter ${i + 1}`}
          filter={f}
          columns={columns}
          onChange={(next) => onChange(filters.map((old, j) => (j === i ? next : old)))}
          onRemove={() => onChange(filters.filter((_, j) => j !== i))}
        />
      ))}
      {columns.length ? (
        <div>
          <Button variant="secondary" onClick={() => onChange([...filters, defaultFilter(columns[0])])}>
            Add filter
          </Button>
        </div>
      ) : null}
    </div>
  );
}
