import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, LineChart, MapChart, PieChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsCoreOption } from "echarts/core";

echarts.use([LineChart, BarChart, PieChart, MapChart, GridComponent, TooltipComponent, LegendComponent, VisualMapComponent, CanvasRenderer]);

export const cssVar = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

export const seriesColors = () => ({
  visitor: cssVar("--c-visitor"), suspicious: cssVar("--c-suspicious"), blocked: cssVar("--c-blocked"),
  challenged: cssVar("--c-challenged"), internal: cssVar("--c-internal"), accent: cssVar("--accent"),
  text: cssVar("--text"), muted: cssVar("--muted"), grid: cssVar("--border"), surface: cssVar("--surface"),
});

export function EChart({ option, height = 280, onClick }: { option: EChartsCoreOption; height?: number; onClick?: (p: { name?: string }) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    chart.current = echarts.init(ref.current, undefined, { renderer: "canvas" });
    const ro = new ResizeObserver(() => chart.current?.resize());
    ro.observe(ref.current);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    return () => { ro.disconnect(); chart.current?.dispose(); chart.current = null; void mq; };
  }, []);
  useEffect(() => { chart.current?.setOption(option, { notMerge: true }); }, [option]);
  useEffect(() => {
    if (!chart.current || !onClick) return;
    const c = chart.current;
    c.on("click", onClick as never);
    return () => { c.off("click"); };
  }, [onClick]);
  return <div ref={ref} style={{ width: "100%", height }} />;
}

let worldPromise: Promise<void> | null = null;
export function loadWorld() {
  worldPromise ??= fetch("/world.json").then((r) => r.json()).then((geo) => { echarts.registerMap("world", geo); });
  return worldPromise;
}
export { echarts };
