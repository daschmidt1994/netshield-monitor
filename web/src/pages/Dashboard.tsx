import { api, rangeParams, type DomainRow, type NotificationRow, type Overview, type RangeSel, type SourceRow, type Timeseries } from "../api";
import { useApi } from "../hooks";
import { useT } from "../i18n";
import { fmtNum, fmtTime } from "../format";
import { Badge, Card, ErrorBox, Loading, Stat } from "../components/ui";
import { TrafficChart } from "../components/TrafficChart";
import { CountryTable } from "../components/tables";

export function SecurityBadge({ level }: { level: string }) {
  const { t } = useT();
  const tone = level === "critical" ? "bad" : level === "warning" ? "warn" : "ok";
  return <Badge tone={tone}>{t(level as "ok")}</Badge>;
}

export function BackfillBanner() {
  const { lang } = useT();
  const src = useApi(() => api.get<{ sources: SourceRow[] }>("/api/v1/sources"), [], { interval: 15000 });
  const nb = src.data?.sources.find((s) => s.name === "netbird_access_logs");
  if (nb?.status !== "backfill") return null;
  return (
    <div className="info-box">
      {lang === "de"
        ? `Historische Access-Logs werden noch importiert (${fmtNum(nb.items_total ?? 0, lang)} bisher, älteste zuerst). Aktuelle Zahlen erscheinen, sobald der Import die Gegenwart erreicht.`
        : `Historical access logs are still being imported (${fmtNum(nb.items_total ?? 0, lang)} so far, oldest first). Current numbers appear once the import catches up.`}
    </div>
  );
}

export function Dashboard({ range }: { range: RangeSel }) {
  const { t, lang } = useT();
  const p = rangeParams(range);
  const ov = useApi(() => api.get<Overview>("/api/v1/overview", p), [JSON.stringify(p)], { interval: range.key === "live" ? 30000 : undefined });
  const ts = useApi(() => api.get<Timeseries>("/api/v1/timeseries", p), [JSON.stringify(p)]);
  const doms = useApi(() => api.get<{ items: DomainRow[] }>("/api/v1/domains", p), [JSON.stringify(p)]);
  const notes = useApi(() => api.get<{ items: NotificationRow[] }>("/api/v1/notifications", { limit: 6 }), []);
  if (ov.error) return <ErrorBox error={ov.error} />;
  if (!ov.data) return <Loading />;
  const o = ov.data;
  const sec = o.security_status;
  return (
    <div className="stack">
      <BackfillBanner />
      <div className="stats-grid">
        <Stat label={t("requestsToday")} value={fmtNum(o.requests_today, lang)} sub={`${fmtNum(o.requests_per_minute, lang)} ${t("rpm")}`} />
        <Stat label={t("requests24h")} value={fmtNum(o.requests_24h, lang)} sub={range.key !== "24h" ? `${t("requestsRange")}: ${fmtNum(o.requests.requests, lang)}` : undefined} />
        <Stat label={t("visitorsEst")} value={fmtNum(o.visitors.value, lang)} hint={t("visitorsHint")} sub={`${t("requestsToday")}: ${fmtNum(o.visitors_today.value, lang)}`} />
        <Stat label={t("activeDomains")} value={`${o.active_domains} / ${o.known_domains}`} />
        <Stat label={t("blocked")} tone="bad" value={fmtNum(o.requests.blocked + o.requests.challenged, lang)} hint={t("blockedHint")}
          sub={`${t("challenged")}: ${fmtNum(o.requests.challenged, lang)}${o.requests.would_block_observe ? ` · ${t("wouldBlock")}: ${fmtNum(o.requests.would_block_observe, lang)}` : ""}`} />
        <Stat label={t("alerts24h")} tone={o.crowdsec.critical_alerts_24h ? "warn" : undefined} value={fmtNum(o.crowdsec.alerts_24h, lang)}
          sub={`${t("criticalAlerts")}: ${fmtNum(o.crowdsec.critical_alerts_24h, lang)}`} />
        <Stat label={t("localDecisions")} value={fmtNum(o.crowdsec.local_active_decisions, lang)} sub={`${t("communityDecisions")}: ${fmtNum(o.crowdsec.community_active_decisions, lang)}`} />
        <Stat label={t("securityStatus")} value={<SecurityBadge level={sec.level} />}
          sub={sec.reasons.map((r) => `${r.code}: ${Array.isArray(r.value) ? r.value.join(", ") : r.value}`).join(" · ") || undefined} />
      </div>
      <Card title={t("traffic")} hint={t("alertsVsDecisions")}>
        {ts.data ? <TrafficChart data={ts.data} /> : <Loading />}
      </Card>
      <div className="grid-2">
        <Card title={t("topCountries")} hint={t("approxGeo")}><CountryTable rows={o.top_countries} /></Card>
        <Card title={t("domains")} actions={<a href="#/domains" className="link">→</a>}>
          {doms.data ? (
            <div className="table-wrap"><table className="table">
              <thead><tr><th>Host</th><th className="num">{t("total")}</th><th className="num">{t("blocked")}</th><th className="num">{t("rpm")}</th></tr></thead>
              <tbody>{doms.data.items.slice(0, 10).map((d) => (
                <tr key={d.host} className="clickable" onClick={() => { window.location.hash = `/domains/${d.host}`; }}>
                  <td className="mono small">{d.host}{d.crowdsec_mode === "observe" && <Badge tone="warn">observe</Badge>}</td>
                  <td className="num">{fmtNum(d.requests, lang)}</td>
                  <td className={`num ${d.blocked ? "bad-text" : "muted"}`}>{d.blocked ? fmtNum(d.blocked, lang) : "–"}</td>
                  <td className="num">{fmtNum(d.requests_per_minute, lang)}</td>
                </tr>))}</tbody>
            </table></div>) : <Loading />}
        </Card>
      </div>
      {notes.data && notes.data.items.length > 0 && (
        <Card title={t("recentNotifications")}>
          <ul className="notes">{notes.data.items.map((n) => (
            <li key={n.id}><Badge tone={n.severity === "critical" ? "bad" : n.severity === "warning" ? "warn" : "muted"}>{n.severity}</Badge>
              <b>{n.title}</b> <span className="muted">{n.message}</span> <span className="muted small">{fmtTime(n.ts, lang)}</span></li>))}</ul>
        </Card>
      )}
    </div>
  );
}
