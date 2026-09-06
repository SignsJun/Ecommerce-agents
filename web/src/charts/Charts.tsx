import { useMemo } from "react";
import { t } from "../i18n";
import { axisMoney, moneyCompact, shortDate } from "../fmt";
import { AXIS_LABEL, PALETTE, SPLIT_LINE, TOOLTIP, echarts, useChart } from "./useChart";
import type { ChartOption } from "./useChart";

function areaColor(hex: string, from = 0.22, to = 0.01) {
  return new echarts.graphic.LinearGradient(0, 0, 0, 1, [
    { offset: 0, color: `${hex}${Math.round(from * 255).toString(16).padStart(2, "0")}` },
    { offset: 1, color: `${hex}${Math.round(to * 255).toString(16).padStart(2, "0")}` },
  ]);
}

export function Sparkline({ values, tone = PALETTE[0] }: { values: number[]; tone?: string }) {
  const option = useMemo<ChartOption>(
    () => ({
      animation: false,
      grid: { left: 0, right: 0, top: 2, bottom: 2 },
      xAxis: { type: "category", show: false, data: values.map((_, i) => i) },
      yAxis: { type: "value", show: false, scale: true },
      series: [
        {
          type: "line",
          data: values,
          smooth: true,
          symbol: "none",
          lineStyle: { width: 2, color: tone },
          areaStyle: { color: areaColor(tone, 0.2) },
        },
      ],
    }),
    [values, tone],
  );
  const ref = useChart(option);
  return <div ref={ref} className="h-10 w-full" />;
}

type StorePoint = { date: string; revenue: number; profit: number; ad_spend: number };

export function StoreTrend({ rows }: { rows: StorePoint[] }) {
  const option = useMemo<ChartOption>(() => {
    const dates = rows.map((r) => shortDate(r.date));
    const build = (name: string, key: keyof StorePoint, color: string) => ({
      name,
      type: "line" as const,
      smooth: true,
      symbol: "none",
      data: rows.map((r) => Number(r[key])),
      lineStyle: { width: 2.4, color },
      itemStyle: { color },
      areaStyle: { color: areaColor(color) },
    });
    return {
      color: PALETTE,
      tooltip: {
        ...TOOLTIP,
        trigger: "axis",
        valueFormatter: (v) => moneyCompact(v as number),
      },
      legend: {
        top: 0,
        right: 0,
        icon: "roundRect",
        itemWidth: 10,
        itemHeight: 10,
        textStyle: { color: "#6b7280", fontSize: 12 },
      },
      grid: { left: 8, right: 8, top: 42, bottom: 4, containLabel: true },
      xAxis: {
        type: "category",
        data: dates,
        boundaryGap: false,
        axisLine: { lineStyle: { color: "#e8eaef" } },
        axisTick: { show: false },
        axisLabel: AXIS_LABEL,
      },
      yAxis: {
        type: "value",
        splitLine: SPLIT_LINE,
        axisLabel: { ...AXIS_LABEL, formatter: (v: number) => axisMoney(v) },
      },
      series: [
        build("收入", "revenue", PALETTE[0]),
        build("利润", "profit", PALETTE[1]),
        build("广告花费", "ad_spend", PALETTE[2]),
      ],
    };
  }, [rows]);
  const ref = useChart(option);
  return <div ref={ref} className="h-72 w-full" />;
}

type SkuPoint = StorePoint & { units_sold: number; inventory_eod: number };

export function SkuTrend({ rows }: { rows: SkuPoint[] }) {
  const option = useMemo<ChartOption>(
    () => ({
      color: PALETTE,
      tooltip: { ...TOOLTIP, trigger: "axis" },
      legend: {
        top: 0,
        right: 0,
        icon: "roundRect",
        itemWidth: 10,
        itemHeight: 10,
        textStyle: { color: "#6b7280", fontSize: 12 },
      },
      grid: { left: 8, right: 8, top: 42, bottom: 4, containLabel: true },
      xAxis: {
        type: "category",
        data: rows.map((r) => shortDate(r.date)),
        boundaryGap: false,
        axisLine: { lineStyle: { color: "#e8eaef" } },
        axisTick: { show: false },
        axisLabel: AXIS_LABEL,
      },
      yAxis: [
        {
          type: "value",
          name: "金额",
          nameTextStyle: { color: "#97a0b0", fontSize: 11 },
          splitLine: SPLIT_LINE,
          axisLabel: { ...AXIS_LABEL, formatter: (v: number) => axisMoney(v) },
        },
        {
          type: "value",
          name: "库存",
          nameTextStyle: { color: "#97a0b0", fontSize: 11 },
          splitLine: { show: false },
          axisLabel: AXIS_LABEL,
        },
      ],
      series: [
        {
          name: "库存",
          type: "bar",
          yAxisIndex: 1,
          data: rows.map((r) => r.inventory_eod),
          itemStyle: { color: "#eef2ff", borderRadius: [3, 3, 0, 0] },
          barMaxWidth: 14,
        },
        {
          name: "收入",
          type: "line",
          smooth: true,
          symbol: "none",
          data: rows.map((r) => r.revenue),
          lineStyle: { width: 2.4, color: PALETTE[0] },
          itemStyle: { color: PALETTE[0] },
        },
        {
          name: "利润",
          type: "line",
          smooth: true,
          symbol: "none",
          data: rows.map((r) => r.profit),
          lineStyle: { width: 2.4, color: PALETTE[1] },
          itemStyle: { color: PALETTE[1] },
          areaStyle: { color: areaColor(PALETTE[1], 0.16) },
        },
        {
          name: "广告花费",
          type: "line",
          smooth: true,
          symbol: "none",
          data: rows.map((r) => r.ad_spend),
          lineStyle: { width: 2, color: PALETTE[2], type: "dashed" },
          itemStyle: { color: PALETTE[2] },
        },
      ],
    }),
    [rows],
  );
  const ref = useChart(option);
  return <div ref={ref} className="h-80 w-full" />;
}

export type StrategyBar = {
  name: string;
  expected: number;
  p10: number;
  recommended: boolean;
};

export function StrategyCompare({ rows }: { rows: StrategyBar[] }) {
  const option = useMemo<ChartOption>(
    () => ({
      tooltip: {
        ...TOOLTIP,
        trigger: "axis",
        axisPointer: { type: "shadow" },
        valueFormatter: (v) => moneyCompact(v as number),
      },
      legend: {
        top: 0,
        right: 0,
        icon: "roundRect",
        itemWidth: 10,
        itemHeight: 10,
        textStyle: { color: "#6b7280", fontSize: 12 },
      },
      grid: { left: 8, right: 24, top: 42, bottom: 4, containLabel: true },
      xAxis: {
        type: "value",
        splitLine: SPLIT_LINE,
        axisLabel: { ...AXIS_LABEL, formatter: (v: number) => axisMoney(v) },
      },
      yAxis: {
        type: "category",
        data: rows.map((r) => r.name),
        axisLine: { lineStyle: { color: "#e8eaef" } },
        axisTick: { show: false },
        axisLabel: { color: "#3c4257", fontSize: 12 },
      },
      series: [
        {
          name: "期望利润",
          type: "bar",
          data: rows.map((r) => ({
            value: r.expected,
            itemStyle: { color: r.recommended ? PALETTE[0] : "#c7cbd6", borderRadius: [0, 4, 4, 0] },
          })),
          barMaxWidth: 16,
        },
        {
          name: "悲观利润 P10",
          type: "bar",
          data: rows.map((r) => ({
            value: r.p10,
            itemStyle: { color: r.recommended ? "#a5b4fc" : "#e3e5ea", borderRadius: [0, 4, 4, 0] },
          })),
          barMaxWidth: 16,
        },
      ],
    }),
    [rows],
  );
  const ref = useChart(option);
  return <div ref={ref} style={{ height: Math.max(200, rows.length * 68) }} className="w-full" />;
}

export type ScenarioMatrix = {
  scenarios: string[];
  series: { name: string; values: (number | null)[]; recommended: boolean }[];
};

export function ScenarioCompare({ data }: { data: ScenarioMatrix }) {
  const option = useMemo<ChartOption>(
    () => ({
      color: PALETTE,
      tooltip: { ...TOOLTIP, trigger: "axis", valueFormatter: (v) => moneyCompact(v as number) },
      legend: {
        top: 0,
        right: 0,
        icon: "roundRect",
        itemWidth: 10,
        itemHeight: 10,
        textStyle: { color: "#6b7280", fontSize: 12 },
      },
      grid: { left: 8, right: 8, top: 46, bottom: 4, containLabel: true },
      xAxis: {
        type: "category",
        data: data.scenarios.map((s) => t.scenario(s)),
        axisLine: { lineStyle: { color: "#e8eaef" } },
        axisTick: { show: false },
        axisLabel: AXIS_LABEL,
      },
      yAxis: {
        type: "value",
        splitLine: SPLIT_LINE,
        axisLabel: { ...AXIS_LABEL, formatter: (v: number) => axisMoney(v) },
      },
      series: data.series.map((s, i) => ({
        name: s.name,
        type: "bar" as const,
        data: s.values,
        barMaxWidth: 22,
        itemStyle: {
          color: s.recommended ? PALETTE[i % PALETTE.length] : "#d7dae2",
          borderRadius: [4, 4, 0, 0],
        },
      })),
    }),
    [data],
  );
  const ref = useChart(option);
  return <div ref={ref} className="h-72 w-full" />;
}

const STAGE_ORDER = [
  "snapshot",
  "issue",
  "evidence",
  "diagnosis",
  "strategy",
  "validation",
  "simulation",
  "recommendation",
  "decision",
];

const STAGE_COLOR: Record<string, string> = {
  snapshot: "#64748b",
  issue: "#d97706",
  evidence: "#0ea5e9",
  diagnosis: "#4f46e5",
  strategy: "#6366f1",
  validation: "#94a3b8",
  simulation: "#16a34a",
  recommendation: "#db2777",
  decision: "#131722",
};

export type GraphNode = { node_id: string; node_type: string; label: string };
export type GraphEdge = { source_id: string; target_id: string; relation: string };

export function ProvenanceGraph({
  nodes,
  edges,
  onSelect,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onSelect?: (nodeId: string) => void;
}) {
  const option = useMemo<ChartOption>(() => {
    const columns = new Map<string, GraphNode[]>();
    nodes.forEach((n) => {
      const bucket = columns.get(n.node_type) ?? [];
      bucket.push(n);
      columns.set(n.node_type, bucket);
    });
    const usedStages = STAGE_ORDER.filter((s) => columns.has(s));
    const width = Math.max(1, usedStages.length - 1);

    const tallest = Math.max(...usedStages.map((s) => columns.get(s)?.length ?? 0), 1);
    const rowGap = tallest > 7 ? 52 : 68;

    const points = usedStages.flatMap((stage, col) => {
      const bucket = columns.get(stage) ?? [];
      return bucket.map((n, row) => ({
        id: n.node_id,
        name: n.label || n.node_id,
        x: (col / width) * 1280,
        y: (row - (bucket.length - 1) / 2) * rowGap,
        symbolSize: stage === "decision" ? 24 : 16,
        itemStyle: { color: STAGE_COLOR[stage] ?? "#94a3b8", borderColor: "#ffffff", borderWidth: 2 },
        label: {
          show: true,
          position: (stage === "decision" ? "bottom" : stage === "recommendation" ? "top" : "right") as
            | "bottom"
            | "top"
            | "right",
          distance: 8,
          formatter: () => {
            const text = n.label || n.node_id;
            return text.length > 12 ? `${text.slice(0, 12)}…` : text;
          },
          color: "#3c4257",
          fontSize: 11,
        },
        tooltip: { formatter: () => `${t.nodeType(stage)} · ${n.label || n.node_id}` },
      }));
    });

    const ids = new Set(points.map((p) => p.id));
    return {
      tooltip: { ...TOOLTIP },
      animationDuration: 400,
      series: [
        {
          type: "graph",
          layout: "none",
          roam: true,
          zoom: 0.95,
          left: 50,
          right: 70,
          edgeSymbol: ["none", "arrow"],
          edgeSymbolSize: 7,
          labelLayout: { hideOverlap: true },
          data: points,
          links: edges
            .filter((e) => ids.has(e.source_id) && ids.has(e.target_id))
            .map((e) => ({
              source: e.source_id,
              target: e.target_id,
              lineStyle: { color: "#d7dae2", width: 1.1, curveness: 0.14, opacity: 0.9 },
            })),
          emphasis: { focus: "adjacency", lineStyle: { width: 2, color: "#4f46e5" } },
        },
      ],
    };
  }, [nodes, edges]);

  const ref = useChart(
    option,
    onSelect
      ? {
          click: (params) => {
            const data = params as { dataType?: string; data?: { id?: string } };
            if (data.dataType === "node" && data.data?.id) onSelect(data.data.id);
          },
        }
      : undefined,
  );
  return <div ref={ref} className="h-[460px] w-full" />;
}
