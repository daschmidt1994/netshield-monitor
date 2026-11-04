import { useState } from "react";
import { api, rangeParams, type DomainDetail, type DomainRow, type RangeSel } from "../api";
import { useApi } from "../hooks";
import { useT } from "../i18n";
import { fmtNum, fmtTime } from "../format";
import { Badge, Card, ErrorBox, Loading, Stat } from "../components/ui";
import { TrafficChart } from "../components/TrafficChart";
import { CountryTable, PathTable } from "../components/tables";
import { EChart, seriesColors } from "../components/charts";

export function Domains({ range }: { range: RangeSel }) {
  const { t, lang } = useT();
  const p = rangeParams(range);
  const [showHidden, setShowHidden] = useState(false);
  const doms = useApi(() => api.get<{ items: DomainRow[] }>("/api/v1/domains", { ...p, include_hidden: showHidden }), [JSON.stringify(p), showHidden]);
  if (doms.error) return <ErrorBox error={doms.error} />;
  if (!doms.data) return <Loading />;
  const max = Math.max(1, ...doms.data.items.map((d) => d.requests));
  return (
    <Card title={`${t("domains")} (${doms.data.items.length})`} actions={
      <label className="small"><input type="checkbox" checked={showHidden} onChange={(e) => setShowHidden(e.target.checked)} /> {t("hidden")}</label>}>
      <div className="domain-grid">
        {doms.data.items.map((d) => (
          <a key={d.host} href={`#/domains/${d.host}`} className={`domain-card ${d.hidden ? "dim" : ""}`}>
            <div className="domain-head">
              <span className="mono">{d.host}</span>
              <span>
                {d.crowdsec_mode && <Badge tone={d.crowdsec_mode === "enforce" ? "ok" : "warn"}>{d.crowdsec_mode}</Badge>}
                {d.removed_upstream && <Badge tone="muted">removed</Badge>}
                {!d.enabled && <Badge tone="muted">disabled</Badge>}
              </span>
            </div>
            <div className="domain-nums">
              <div><b>{fmtNum(d.requests, lang)}</b><span>{t("total")}</span></div>
              <div><b className="bad-text">{fmtNum(d.blocked, lang)}</b><span>{t("blocked")}</span></div>
              <div><b>{fmtNum(d.suspicious, lang)}</b><span>{t("suspicious")}</span></div>
              <div><b>{fmtNum(d.requests_per_minute, lang)}</b><span>{t("rpm")}</span></div>
            </div>
            <div className="bar"><div className="bar-fill" style={{ width: `${(d.requests / max) * 100}%` }} /></div>
            <div className="muted small">{t("lastSeen")}: {fmtTime(d.last_seen, lang)}</div>
          </a>
        ))}
      </div>
    </Card>
  );
}

export function DomainPage({ host, range }: { host: string; range: RangeSel }) {
  const { t, lang } = useT();
  const p = rangeParams(range);
  const d = useApi(() => api.get<DomainDetail>(`/api/v1/domains/${encodeURIComponent(host)}`, p), [host, JSON.stringify(p)]);
  if (d.error) return <ErrorBox error={d.error} />;
  if (!d.data) return <Loading />;
  const x = d.data;
  const c = seriesColors();
  const statusOption = {
    tooltip: { trigger: "item" },
    series: [{
      type: "pie", radius: ["45%", "75%"], itemStyle: { borderColor: c.surface, borderWidth: 2 }, label: { color: c.muted },
      data: x.statuses.slice(0, 10).map((s) => ({
        name: String(s.status), value: s.count,
        itemStyle: { color: s.status >= 500 ? c.blocked : s.status >= 400 ? c.suspicious : s.status >= 300 ? c.internal : c.visitor },
      })),
    }],
  };
  return (
    <div className="stack">
      <div className="page-title">
        <a href="#/domains" className="link">← {t("domains")}</a>
        <h1 className="mono">{host}</h1>
        {x.info?.crowdsec_mode && <Badge tone={x.info.crowdsec_mode === "enforce" ? "ok" : "warn"}>{t("mode")}: {x.info.crowdsec_mode}</Badge>}
        {x.info?.crowdsec_mode === "observe" && <span className="muted small">{t("observeHint")}</span>}
      </div>
      <div className="stats-grid">
        <Stat label={t("requestsRange")} value={fmtNum(x.requests.requests, lang)} />
        <Stat label={t("rpm")} value={fmtNum(x.requests_per_minute, lang)} />
        <Stat label={t("visitorsEst")} value={fmtNum(x.visitors.value, lang)} hint={t("visitorsHint")} />
        <Stat label={t("blocked")} tone="bad" value={fmtNum(x.requests.blocked + x.requests.challenged, lang)} hint={t("blockedHint")}
          sub={x.requests.would_block_observe ? `${t("wouldBlock")}: ${fmtNum(x.requests.would_block_observe, lang)}` : undefined} />
        <Stat label={t("suspicious")} tone="warn" value={fmtNum(x.requests.suspicious, lang)} />
        <Stat label={t("alerts")} value={fmtNum(x.crowdsec.alerts, lang)} />
      </div>
      <Card title={t("traffic")}><TrafficChart data={x.timeseries} /></Card>
      <div className="grid-2">
        <Card title={t("topCountries")} hint={t("approxGeo")}><CountryTable rows={x.countries} limit={12} /></Card>
        <Card title={t("statusCodes")}><EChart option={statusOption} height={260} /></Card>
      </div>
      <div className="grid-2">
        <Card title={t("topPaths")}><PathTable rows={x.top_paths.items} /></Card>
        <Card title={t("suspiciousPaths")}><PathTable rows={x.suspicious_paths.items} /></Card>
      </div>
      {x.crowdsec.top_scenarios.length > 0 && (
        <Card title={`${t("crowdsec")} – ${t("scenarios")}`}>
          <table className="table"><tbody>{x.crowdsec.top_scenarios.map((s) => (
            <tr key={s.scenario}><td className="mono small">{s.scenario}</td><td className="num">{fmtNum(s.count, lang)}</td></tr>))}</tbody></table>
        </Card>
      )}
    </div>
  );
}
