"use client";

import dynamic from "next/dynamic";

import { Spinner } from "../ui";
import type { PlotlyChartProps } from "./plotly-chart-inner";

/** The one Plotly entry point: client-only (ssr: false) with a loading state. */
export const PlotlyChart = dynamic<PlotlyChartProps>(() => import("./plotly-chart-inner"), {
  ssr: false,
  loading: () => <Spinner label="Loading chart..." />,
});

export type { PlotlyChartProps };
