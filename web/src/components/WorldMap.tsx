import { useEffect, useMemo, useState } from "react";
import type { CountryRow } from "../api";
import { useT } from "../i18n";
import { countryName, fmtNum } from "../format";
import { EChart, loadWorld, seriesColors } from "./charts";

export type MapMetric = "requests" | "blocked" | "allowed";

export function WorldMap({ rows, metric = "requests", height = 420, onSelect }: { rows: CountryRow[]; metric?: MapMetric; height?: number; onSelect?: (cc: string) => void }) {
  const { t, lang } = useT();
  const [ready, setReady] = useState(false);
  useEffect(() => { loadWorld().then(() => setReady(true)); }, []);
  const option = useMemo(() => {
    const c = seriesColors();
    // square-root scale so one dominant country does not wash out all others; tooltips show real values
    const data = rows.filter((r) => r.country && r[metric] > 0).map((r) => ({ name: r.country!, value: Math.sqrt(r[metric]), row: r }));
    const realMax = Math.max(1, ...rows.map((r) => r[metric]));
    const max = Math.sqrt(realMax);
    const tone = metric === "blocked" ? c.blocked : c.accent;
    return {
      tooltip: {
        trigger: "item", backgroundColor: c.surface, borderColor: c.grid, textStyle: { color: c.text },
        formatter: (p: { name: string; data?: { row: CountryRow } }) => {
          const r = p.data?.row;
          return `<b>${countryName(p.name, lang)}</b><br/>${t("total")}: ${fmtNum(r?.requests ?? 0, lang)}<br/>${t("allowed")}: ${fmtNum(r?.allowed ?? 0, lang)}<br/>${t("blocked")}: ${fmtNum(r?.blocked ?? 0, lang)}`;
        },
      },
      visualMap: {
        min: 0, max, left: 8, bottom: 8, calculable: false, text: [fmtNum(realMax, lang), "0"], textStyle: { color: c.muted },
        inRange: { color: [c.grid, tone] }, type: "continuous", itemHeight: 90,
      },
      series: [{
        type: "map", map: "world", roam: true, scaleLimit: { min: 1, max: 8 }, nameProperty: "name",
        itemStyle: { areaColor: c.surface, borderColor: c.grid, borderWidth: 0.5 },
        emphasis: { label: { show: false }, itemStyle: { areaColor: c.challenged } },
        select: { disabled: true }, data,
      }],
    };
  }, [rows, metric, t, lang]);
  if (!ready) return <div style={{ height }} className="muted pad">{t("loading")}</div>;
  return <EChart option={option} height={height} onClick={(p) => p.name && onSelect?.(p.name)} />;
}
