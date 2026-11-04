import { useMemo } from "react";
import type { Timeseries } from "../api";
import { useT } from "../i18n";
import { EChart, seriesColors } from "./charts";

const CATS = ["visitor", "suspicious", "challenged", "blocked", "internal"] as const;

export function TrafficChart({ data, height = 280 }: { data: Timeseries; height?: number }) {
  const { t, lang } = useT();
  const option = useMemo(() => {
    const c = seriesColors();
    const dayFmt = data.bucket_seconds >= 86400;
    const locale = lang === "de" ? "de-AT" : "en-US";
    const labels = data.points.map((p) => new Date(p.ts * 1000).toLocaleString(locale,
      dayFmt ? { day: "2-digit", month: "2-digit" } : data.bucket_seconds >= 3600 ? { day: "2-digit", month: "2-digit", hour: "2-digit" } : { hour: "2-digit", minute: "2-digit" }));
    return {
      color: CATS.map((k) => c[k]),
      tooltip: { trigger: "axis", backgroundColor: c.surface, borderColor: c.grid, textStyle: { color: c.text } },
      legend: { bottom: 0, type: "scroll", textStyle: { color: c.muted }, icon: "roundRect" },
      grid: { left: 44, right: 12, top: 16, bottom: 56 },
      xAxis: { type: "category", data: labels, axisLabel: { color: c.muted, hideOverlap: true }, axisLine: { lineStyle: { color: c.grid } } },
      yAxis: { type: "value", axisLabel: { color: c.muted }, splitLine: { lineStyle: { color: c.grid, opacity: 0.5 } } },
      series: CATS.map((k) => ({
        name: t(k), type: "bar", stack: "total", barCategoryGap: "20%", emphasis: { focus: "series" },
        data: data.points.map((p) => p[k]),
      })),
    };
  }, [data, t, lang]);
  return <EChart option={option} height={height} />;
}
