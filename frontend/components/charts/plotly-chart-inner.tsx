"use client";

import { useEffect, useRef, useState } from "react";

import type { Layout, Trace } from "plotly.js-basic-dist-min";

export type PlotlyChartProps = {
  data: Trace[];
  layout?: Layout;
  /** Accessible description of what the chart shows. */
  label: string;
  height?: number;
};

const LIGHT = { text: "#374151", grid: "#e5e7eb" };
const DARK = { text: "#d1d5db", grid: "#374151" };

function prefersDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches;
}

/** Plotly in the browser only: the bundle is imported on mount, never during SSR. */
export default function PlotlyChartInner({ data, layout, label, height = 320 }: PlotlyChartProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [dark, setDark] = useState(prefersDark);

  useEffect(() => {
    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    const onChange = () => setDark(media.matches);
    media?.addEventListener("change", onChange);
    return () => media?.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    let cancelled = false;
    const colours = dark ? DARK : LIGHT;
    import("plotly.js-basic-dist-min")
      .then((mod) => {
        if (cancelled) return;
        const Plotly = mod.default ?? mod;
        return Plotly.react(
          node,
          data,
          {
            height,
            margin: { t: 16, r: 16, b: 48, l: 56 },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: { size: 12, color: colours.text },
            legend: { orientation: "h", y: -0.25 },
            ...layout,
            xaxis: { gridcolor: colours.grid, zerolinecolor: colours.grid, ...(layout?.xaxis as object) },
            yaxis: { gridcolor: colours.grid, zerolinecolor: colours.grid, ...(layout?.yaxis as object) },
          },
          { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"] },
        );
      })
      .catch(() => {
        if (!cancelled) setError("The chart could not be drawn.");
      });
    return () => {
      cancelled = true;
    };
  }, [data, layout, height, dark]);

  useEffect(() => {
    const node = ref.current;
    return () => {
      if (node) import("plotly.js-basic-dist-min").then((mod) => (mod.default ?? mod).purge(node)).catch(() => {});
    };
  }, []);

  if (error) return <p className="text-sm text-red-700 dark:text-red-300">{error}</p>;
  return <div ref={ref} role="img" aria-label={label} className="w-full" style={{ minHeight: height }} />;
}
