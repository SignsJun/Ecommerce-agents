import { BarChart, GraphChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";
import type { BarSeriesOption, GraphSeriesOption, LineSeriesOption } from "echarts/charts";
import type { GridComponentOption, LegendComponentOption, TooltipComponentOption } from "echarts/components";
import type { ComposeOption } from "echarts/core";

echarts.use([BarChart, GraphChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

export type ChartOption = ComposeOption<
  | BarSeriesOption
  | GraphSeriesOption
  | LineSeriesOption
  | GridComponentOption
  | LegendComponentOption
  | TooltipComponentOption
>;

export { echarts };

type Handlers = Record<string, (params: unknown) => void>;

export function useChart(option: ChartOption, handlers?: Handlers) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const handlersRef = useRef<Handlers | undefined>(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const chart = echarts.init(host, undefined, { renderer: "canvas" });
    chartRef.current = chart;
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(host);
    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    chart.setOption(option, true);
    Object.keys(handlersRef.current ?? {}).forEach((name) => {
      chart.off(name);
      chart.on(name, (params) => handlersRef.current?.[name]?.(params));
    });
  }, [option]);

  return hostRef;
}

export const AXIS_LABEL = { color: "#97a0b0", fontSize: 11 };
export const SPLIT_LINE = { lineStyle: { color: "#eef0f4" } };

export const TOOLTIP = {
  backgroundColor: "#ffffff",
  borderColor: "#e8eaef",
  borderWidth: 1,
  padding: [10, 12] as [number, number],
  textStyle: { color: "#131722", fontSize: 12 },
  extraCssText: "box-shadow: 0 12px 32px -16px rgba(19,23,34,.35); border-radius: 12px;",
};

export const PALETTE = ["#4f46e5", "#16a34a", "#d97706", "#0ea5e9", "#db2777", "#64748b"];
