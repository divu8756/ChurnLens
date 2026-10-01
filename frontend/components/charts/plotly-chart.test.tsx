import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const react = vi.fn(async () => undefined);
const purge = vi.fn();
vi.mock("plotly.js-basic-dist-min", () => ({ default: { react, purge }, react, purge }));

import PlotlyChartInner from "./plotly-chart-inner";

afterEach(cleanup);

describe("PlotlyChart", () => {
  it("draws with Plotly only after mounting in the browser, and cleans up", async () => {
    const { unmount } = render(<PlotlyChartInner label="Test chart" data={[{ type: "bar", x: ["a"], y: [1] }]} />);
    await waitFor(() => expect(react).toHaveBeenCalledTimes(1));
    const [, data, layout, config] = react.mock.calls[0] as unknown as [HTMLElement, unknown, Record<string, unknown>, Record<string, unknown>];
    expect(data).toEqual([{ type: "bar", x: ["a"], y: [1] }]);
    expect(layout.paper_bgcolor).toBe("rgba(0,0,0,0)");
    expect(config.responsive).toBe(true);
    unmount();
    await waitFor(() => expect(purge).toHaveBeenCalled());
  });
});
