// Minimal types for the parts of plotly.js-basic-dist-min this app uses (it ships none).
declare module "plotly.js-basic-dist-min" {
  export type Datum = string | number | null;
  export interface Trace {
    type?: "scatter" | "bar";
    mode?: string;
    name?: string;
    x?: Datum[];
    y?: Datum[];
    text?: string[];
    hovertemplate?: string;
    orientation?: "h" | "v";
    line?: Record<string, unknown>;
    marker?: Record<string, unknown>;
    yaxis?: string;
    showlegend?: boolean;
    [key: string]: unknown;
  }
  export type Layout = Record<string, unknown>;
  export type Config = Record<string, unknown>;
  export function react(root: HTMLElement, data: Trace[], layout?: Layout, config?: Config): Promise<unknown>;
  export function purge(root: HTMLElement): void;
  const Plotly: { react: typeof react; purge: typeof purge };
  export default Plotly;
}
