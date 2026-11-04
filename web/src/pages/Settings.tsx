import { useEffect, useState } from "react";
import { api, type DomainRow, type SourceRow } from "../api";
import { useApi } from "../hooks";
import { useT } from "../i18n";
import { fmtTime } from "../format";
import { Badge, Card, ErrorBox, Loading } from "../components/ui";

interface TokenRow { id: number; name: string; prefix: string; scope: string; created: number; last_used: number | null; revoked: boolean }
type NotifSettings = Record<string, number | boolean | string>;

const NOTIF_FIELDS: { key: string; type: "bool" | "num" | "sev"; label: { de: string; en: string } }[] = [
  { key: "enabled", type: "bool", label: { de: "Benachrichtigungen aktiv", en: "Notifications enabled" } },
  { key: "critical_alerts", type: "bool", label: { de: "Neue CrowdSec-Alerts", en: "New CrowdSec alerts" } },
  { key: "min_alert_severity", type: "sev", label: { de: "Mindest-Schwere für Alerts", en: "Minimum alert severity" } },
  { key: "request_spike", type: "bool", label: { de: "Ungewöhnlich viele Requests", en: "Unusual request volume" } },
  { key: "request_spike_factor", type: "num", label: { de: "Faktor über 24-h-Durchschnitt", en: "Factor above 24 h average" } },
  { key: "request_spike_min_per_5min", type: "num", label: { de: "Mindestens Requests / 5 min", en: "Minimum requests / 5 min" } },
  { key: "attack_spike", type: "bool", label: { de: "Angriffsspitzen", en: "Attack spikes" } },
  { key: "attack_spike_min_per_5min", type: "num", label: { de: "Blockierte Requests / 5 min", en: "Blocked requests / 5 min" } },
  { key: "domain_outage", type: "bool", label: { de: "Domain-Ausfälle (502/503/504)", en: "Domain outages (502/503/504)" } },
  { key: "domain_outage_error_ratio", type: "num", label: { de: "Fehleranteil (0–1)", en: "Error ratio (0–1)" } },
  { key: "domain_outage_min_requests", type: "num", label: { de: "Mindest-Requests / 5 min", en: "Minimum requests / 5 min" } },
  { key: "scanner_pattern", type: "bool", label: { de: "Auffällige Zugriffsmuster (404-Serien)", en: "Suspicious patterns (404 bursts)" } },
  { key: "scanner_404_per_source_5min", type: "num", label: { de: "404 pro Quelle / 5 min", en: "404s per source / 5 min" } },
  { key: "source_errors", type: "bool", label: { de: "Datenquellen-Ausfälle", en: "Data source failures" } },
  { key: "source_error_minutes", type: "num", label: { de: "Nach Minuten", en: "After minutes" } },
  { key: "cooldown_minutes", type: "num", label: { de: "Wiederholungssperre (Minuten)", en: "Repeat cooldown (minutes)" } },
];

export function Settings() {
  const { t, lang } = useT();
  const src = useApi(() => api.get<{ sources: SourceRow[]; privacy: Record<string, number | string>; version: string; timezone: string }>("/api/v1/sources"), []);
  const tokens = useApi(() => api.get<{ items: TokenRow[] }>("/api/v1/admin/tokens"), [], { live: false });
  const doms = useApi(() => api.get<{ items: DomainRow[] }>("/api/v1/domains", { range: "30d", include_hidden: true }), [], { live: false });
  const [notif, setNotif] = useState<NotifSettings | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [newTok, setNewTok] = useState<{ name: string; scope: string }>({ name: "", scope: "read" });
  const [created, setCreated] = useState<string | null>(null);
  const [newHost, setNewHost] = useState("");
  useEffect(() => { api.get<{ notifications: NotifSettings }>("/api/v1/admin/settings").then((s) => setNotif(s.notifications)).catch((e) => setMsg(String(e))); }, []);
  const flash = (m: string) => { setMsg(m); window.setTimeout(() => setMsg(null), 4000); };
  const saveNotif = async () => {
    try { const r = await api.put<{ notifications: NotifSettings }>("/api/v1/admin/settings", { notifications: notif }); setNotif(r.notifications); flash(t("saved")); }
    catch (e) { flash(String(e)); }
  };
  return (
    <div className="stack">
      {msg && <div className="toast">{msg}</div>}
      <Card title={t("sources")}>
        {src.error ? <ErrorBox error={src.error} /> : !src.data ? <Loading /> : (
          <div className="table-wrap"><table className="table">
            <thead><tr><th>{t("source")}</th><th>{t("status")}</th><th>{t("lastSuccess")}</th><th>{t("error")}</th></tr></thead>
            <tbody>{src.data.sources.map((s) => (
              <tr key={s.name}>
                <td className="mono small">{s.name}</td>
                <td>{!s.configured ? <Badge tone="muted">{t("notConfigured")}</Badge> : <Badge tone={s.status === "ok" ? "ok" : s.status === "backfill" ? "accent" : s.status === "error" ? "bad" : "muted"}>{s.status ?? "–"}</Badge>}</td>
                <td className="small">{fmtTime(s.last_success, lang)}</td>
                <td className="small bad-text">{s.status === "error" ? s.last_error : ""}</td>
              </tr>))}</tbody>
          </table></div>)}
        {src.data && <p className="muted small">v{src.data.version} · {src.data.timezone} · {t("ipMode")}: {src.data.privacy.ip_mode === "full" ? t("full") : `${t("truncated")} (/${src.data.privacy.ipv4_prefix}, /${src.data.privacy.ipv6_prefix})`} · {t("retention")}: {src.data.privacy.raw_retention_days} / {src.data.privacy.aggregate_retention_days} {t("days")}</p>}
      </Card>

      <Card title={t("notifications")} actions={<div className="row gap"><button className="btn ghost" onClick={async () => { try { await api.post("/api/v1/admin/notifications/test"); flash("ntfy ✓"); } catch (e) { flash(String(e)); } }}>{t("testNtfy")}</button><button className="btn" onClick={saveNotif}>{t("save")}</button></div>}>
        {!notif ? <Loading /> : (
          <div className="form-grid">
            {NOTIF_FIELDS.map((f) => (
              <label key={f.key} className="form-row">
                <span>{f.label[lang]}</span>
                {f.type === "bool" ? <input type="checkbox" checked={Boolean(notif[f.key])} onChange={(e) => setNotif({ ...notif, [f.key]: e.target.checked })} />
                  : f.type === "sev" ? <select value={String(notif[f.key])} onChange={(e) => setNotif({ ...notif, [f.key]: e.target.value })}><option>critical</option><option>high</option><option>low</option></select>
                  : <input type="number" step="any" value={Number(notif[f.key])} onChange={(e) => setNotif({ ...notif, [f.key]: Number(e.target.value) })} />}
              </label>))}
          </div>)}
      </Card>

      <Card title={t("tokens")}>
        {created && <div className="token-box"><p>{t("tokenOnce")}</p><code>{created}</code></div>}
        <div className="row gap wrap">
          <input placeholder={t("name")} value={newTok.name} maxLength={64} onChange={(e) => setNewTok({ ...newTok, name: e.target.value })} />
          <select value={newTok.scope} onChange={(e) => setNewTok({ ...newTok, scope: e.target.value })}><option value="read">read</option><option value="admin">admin</option></select>
          <button className="btn" disabled={!newTok.name} onClick={async () => {
            try { const r = await api.post<{ token: string }>("/api/v1/admin/tokens", newTok); setCreated(r.token); setNewTok({ name: "", scope: "read" }); tokens.reload(); }
            catch (e) { flash(String(e)); } }}>{t("create")}</button>
        </div>
        {tokens.data && <table className="table">
          <thead><tr><th>{t("name")}</th><th>Prefix</th><th>{t("scope")}</th><th>{t("lastSeen")}</th><th /></tr></thead>
          <tbody>{tokens.data.items.map((x) => (
            <tr key={x.id} className={x.revoked ? "dim" : ""}>
              <td>{x.name}</td><td className="mono small">{x.prefix}…</td><td><Badge tone={x.scope === "admin" ? "warn" : "muted"}>{x.scope}</Badge></td>
              <td className="small">{x.last_used ? fmtTime(x.last_used, lang) : t("never")}</td>
              <td>{!x.revoked && <button className="btn ghost danger" onClick={async () => { await api.del(`/api/v1/admin/tokens/${x.id}`); tokens.reload(); }}>{t("revoke")}</button>}</td>
            </tr>))}</tbody></table>}
      </Card>

      <Card title={t("domains")}>
        <div className="row gap wrap">
          <input placeholder="app.example.com" value={newHost} onChange={(e) => setNewHost(e.target.value.trim().toLowerCase())} />
          <button className="btn" disabled={!newHost} onClick={async () => { try { await api.post("/api/v1/domains", { host: newHost }); setNewHost(""); doms.reload(); } catch (e) { flash(String(e)); } }}>{t("addDomain")}</button>
        </div>
        {doms.data && <table className="table"><tbody>{doms.data.items.map((d) => (
          <tr key={d.host} className={d.hidden ? "dim" : ""}>
            <td className="mono small">{d.host}</td><td><Badge tone="muted">{d.source}</Badge></td>
            <td><button className="btn ghost" onClick={async () => { await api.patch(`/api/v1/domains/${d.host}`, { hidden: !d.hidden }); doms.reload(); }}>{d.hidden ? t("show") : t("hide")}</button></td>
          </tr>))}</tbody></table>}
      </Card>
    </div>
  );
}
