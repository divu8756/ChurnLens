"use client";

import { ALPHAS } from "@/lib/hypothesis";

export function AlphaControl({ alpha, onChange }: { alpha: number; onChange: (alpha: number) => void }) {
  const index = Math.max(0, ALPHAS.findIndex((a) => a === alpha));
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium">
        Significance level α = <span className="tabular-nums">{alpha}</span>
      </span>
      <input
        type="range"
        min={0}
        max={ALPHAS.length - 1}
        step={1}
        value={index}
        onChange={(e) => onChange(ALPHAS[Number(e.target.value)])}
        className="w-full max-w-xs accent-blue-600"
        aria-valuetext={`alpha ${alpha}`}
      />
      <span className="flex max-w-xs justify-between text-xs text-gray-500" aria-hidden>
        {ALPHAS.map((a) => (
          <span key={a}>{a}</span>
        ))}
      </span>
    </label>
  );
}
