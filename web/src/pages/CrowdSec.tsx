import { useMemo, useState } from "react";
import { api, rangeParams, type AlertRow, type CrowdsecSummary, type DecisionsResp, type RangeSel } from "../api";
import { useApi } from "../hooks";
import { useT } from "../i18n";
import { countryName, flag, fmtDuration, fmtNum, fmtTime } from "../format";
import { Badge, Bar, Card, Empty, ErrorBox, Loading, Stat } from "../components/ui";
import { EChart, seriesColors } from "../components/charts";
import { WorldMap } from "../components/WorldMap";

export function CrowdSec({ range }: { range: RangeSel }) {
  const { t, lang } = useT();
  const p = rangeParams(range);
  const [severity, setSeverity] = useState("");
  const sum = useApi(() => api.get<CrowdsecSummary>("/api/v1/crowdsec/summary", p), [JSON.stringify(p)]);
  const alerts = useApi(() => api.get<{ items: AlertRow[] }>("/api/v1/crowdsec/alerts", { ...p, limit: 100, severity: severity || undefined }), [JSON.stringify(p), severity]);
  const dec = useApi(() => api.get<DecisionsResp>("/api/v1/crowdsec/decisions"), []);
  const c = seriesColors();
  const timeline = useMemo(() => {
    if (!sum.data) return null;
    const pts = sum.data.alerts.timeseries.points;
    const locale = lang === "de" ? "de-AT" : "en-US";
    return {
      tooltip: { trigger: "axis" }, grid: { left: 40, right: 10, top: 10, bottom: 30 },
      xAxis: { type: "category", data: pts.map((x) => new Date(x.ts * 1000).toLocaleString(locale, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })), axisLabel: { color: c.muted } },
      yAxis: { type: "value", axisLabel: { color: c.muted }, splitLine: { lineStyle: { color: c.grid, opacity: 0.5 } } },
      series: [{ type: "bar", name: t("alerts"), data: pts.map((x) => x.alerts), itemStyle: { color: c.suspicious } }],
    };
  }, [sum.data, lang, t, c.muted, c.grid, c.suspicious]);
  const history = useMemo(() => {
    if (!sum.data || sum.data.decision_history.length < 2) return null;
    const h = sum.data.decision_history;
    const locale = lang === "de" ? "de-AT" : "en-US";
    return {
      tooltip: { trigger: "axis" }, legend: { bottom: 0, textStyle: { color: c.muted } }, grid: { left: 56, right: 56, top: 10, bottom: 40 },
      xAxis: { type: "category", data: h.map((x) => new Date(x.ts * 1000).toLocaleString(locale, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })), axisLabel: { color: c.muted } },
      yAxis: [{ type: "value", axisLabel: { color: c.muted }, splitLine: { show: false } }, { type: "value", axisLabel: { color: c.muted }, splitLine: { show: false } }],
      series: [
        { type: "line", name: t("local"), data: h.map((x) => x.local), showSymbol: false, itemStyle: { color: c.blocked } },
        { type: "line", name: t("community"), yAxisIndex: 1, data: h.map((x) => x.community), showSymbol: false, itemStyle: { color: c.internal } },
      ],
    };
  }, [sum.data, lang, t, c.muted, c.blocked, c.internal]);
  if (sum.error) return <ErrorBox error={sum.error} />;
  if (!sum.data) return <Loading />;
  const s = sum.data;
  const enf = s.enforcement;
  const maxScen = Math.max(1, ...s.alerts.top_scenarios.map((x) => x.count));
  return (
    <div className="stack">
      <p className="muted small">{t("alertsVsDecisions")}</p>
      <div className="stats-grid">
        <Stat label={t("alerts")} value={fmtNum(s.alerts.alerts, lang)} sub={`${t("decisions")}: ${fmtNum(s.alerts.alerts_with_decision, lang)}`} />
        <Stat label={t("criticalAlerts")} tone={s.alerts.by_severity.critical ? "warn" : undefined} value={fmtNum(s.alerts.by_severity.critical, lang)} />
        <Stat label={t("localDecisions")} value={fmtNum(s.decisions.local_active, lang)} />
        <Stat label={t("communityDecisions")} value={fmtNum(s.decisions.community_active, lang)} />
      </div>
      <Card title={t("enforcement")}>
        <div className="stats-grid">
          <Stat label={t("netbirdProxy")} tone="bad" value={fmtNum((enf.netbird_proxy?.blocked ?? 0) + (enf.netbird_proxy?.challenged ?? 0), lang)}
            sub={`Ban ${fmtNum(enf.netbird_proxy?.blocked ?? 0, lang)} · Captcha ${fmtNum(enf.netbird_proxy?.challenged ?? 0, lang)} · ${t("wouldBlock")} ${fmtNum(enf.netbird_proxy?.would_block_observe ?? 0, lang)}`} />
          <Stat label={t("appsec")} value={enf.crowdsec_appsec?.blocked == null ? "–" : fmtNum(enf.crowdsec_appsec.blocked, lang)} sub={enf.crowdsec_appsec?.evidence} />
          <Stat label={t("firewall")} value="–" sub={t("notAvailable")} />
        </div>
      </Card>
      <div className="grid-2">
        <Card title={t("alertsTimeline")}>{timeline && <EChart option={timeline} height={220} />}</Card>
        <Card title={t("historyDecisions")}>{history ? <EChart option={history} height={220} /> : <Empty />}</Card>
      </div>
      <div className="grid-2">
        <Card title={t("scenarios")}>
          {s.alerts.top_scenarios.length ? <table className="table"><tbody>{s.alerts.top_scenarios.map((x) => (
            <tr key={x.scenario}><td className="mono small">{x.scenario}</td><td className="num">{fmtNum(x.count, lang)}</td><td className="wbar"><Bar value={x.count} max={maxScen} tone="warn" /></td></tr>))}</tbody></table> : <Empty />}
        </Card>
        <Card title={t("originCountries")} hint={t("approxGeo")}>
          <WorldMap rows={s.alerts.countries.map((x) => ({ country: x.country, requests: x.count, blocked: x.count, allowed: 0 }))} metric="blocked" height={260} />
        </Card>
      </div>
      <Card title={`${t("decisions")} (${t("local")})`}>
        {dec.data?.local_decisions?.length ? (
          <div className="table-wrap"><table className="table">
            <thead><tr><th>{t("source")}</th><th>Typ</th><th>{t("scenarios")}</th><th>Origin</th><th className="num">{t("remaining")}</th></tr></thead>
            <tbody>{dec.data.local_decisions.map((d) => (
              <tr key={d.id}><td className="mono small">{d.value}</td><td><Badge tone={d.type === "ban" ? "bad" : "warn"}>{d.type}</Badge></td>
                <td className="mono small">{d.scenario}</td><td>{d.origin}</td><td className="num">{fmtDuration(d.remaining_seconds)}</td></tr>))}</tbody>
          </table></div>) : <Empty />}
      </Card>
      <Card title={t("alerts")} actions={
        <select value={severity} onChange={(e) => setSeverity(e.target.value)} aria-label={t("severity")}>
          <option value="">{t("all")}</option><option value="critical">critical</option><option value="high">high</option><option value="low">low</option>
        </select>}>
        {alerts.error ? <ErrorBox error={alerts.error} /> : !alerts.data ? <Loading /> : !alerts.data.items.length ? <Empty /> : (
          <div className="table-wrap"><table className="table">
            <thead><tr><th>{t("time")}</th><th>{t("severity")}</th><th>{t("scenarios")}</th><th>{t("source")}</th><th>{t("target")}</th><th className="num">{t("events")}</th><th>{t("decisions")}</th></tr></thead>
            <tbody>{alerts.data.items.map((a) => (
              <tr key={a.id}>
                <td className="small nowrap">{fmtTime(a.created, lang)}</td>
                <td><Badge tone={a.severity === "critical" ? "bad" : a.severity === "high" ? "warn" : "muted"}>{a.severity}</Badge></td>
                <td className="mono small">{a.scenario}</td>
                <td className="small"><span className="flag">{flag(a.country)}</span><span className="mono">{a.source}</span><div className="muted">{a.as_name ?? countryName(a.country, lang)}</div></td>
                <td className="mono small">{a.target_host ?? "–"}</td>
                <td className="num">{fmtNum(a.events, lang)}</td>
                <td className="small">{a.decisions ? `${a.decision_type} · ${a.decision_duration ?? ""}` : "–"}</td>
              </tr>))}</tbody>
          </table></div>)}
      </Card>
    </div>
  );
}
