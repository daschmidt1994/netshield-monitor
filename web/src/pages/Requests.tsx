import { useEffect, useState } from "react";
import { api, type DomainRow, type RequestRow } from "../api";
import { useT } from "../i18n";
import { flag, fmtNum, fmtTime } from "../format";
import { Badge, Card, Empty, ErrorBox } from "../components/ui";

const CATS = ["", "visitor", "suspicious", "blocked", "challenged", "internal"];

export function Requests() {
  const { t, lang } = useT();
  const [host, setHost] = useState("");
  const [cat, setCat] = useState("");
  const [rows, setRows] = useState<RequestRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [domains, setDomains] = useState<DomainRow[]>([]);
  const load = async (before?: number) => {
    try {
      const r = await api.get<{ items: RequestRow[] }>("/api/v1/requests", { host: host || undefined, category: cat || undefined, before, limit: 100 });
      setRows((prev) => (before ? [...prev, ...r.items] : r.items)); setError(null);
    } catch (e) { setError(String(e)); }
  };
  useEffect(() => { load(); }, [host, cat]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { api.get<{ items: DomainRow[] }>("/api/v1/domains", { range: "7d" }).then((r) => setDomains(r.items)).catch(() => {}); }, []);
  const tone = (c: string) => (c === "blocked" ? "bad" : c === "challenged" || c === "suspicious" ? "warn" : c === "internal" ? "muted" : "ok");
  return (
    <Card title={t("recent")} actions={
      <div className="row gap">
        <select value={host} onChange={(e) => setHost(e.target.value)} aria-label="Domain">
          <option value="">{t("all")}</option>{domains.map((d) => <option key={d.host}>{d.host}</option>)}
        </select>
        <select value={cat} onChange={(e) => setCat(e.target.value)} aria-label={t("category")}>
          {CATS.map((c) => <option key={c} value={c}>{c ? t(c as "visitor") : t("all")}</option>)}
        </select>
        <button className="btn ghost" onClick={() => load()}>↻</button>
      </div>}>
      {error && <ErrorBox error={error} />}
      {!rows.length ? <Empty /> : (
        <div className="table-wrap"><table className="table">
          <thead><tr><th>{t("time")}</th><th>Host</th><th>{t("method")}</th><th>{t("path")}</th><th className="num">Status</th><th>{t("ip")}</th><th>{t("category")}</th><th className="num">ms</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.id}>
              <td className="small nowrap">{fmtTime(r.ts, lang)}</td>
              <td className="mono small">{r.host}</td>
              <td className="small">{r.method}</td>
              <td className="mono path small" title={r.path}>{r.path}</td>
              <td className={`num ${r.status >= 500 ? "bad-text" : r.status >= 400 ? "warn-text" : ""}`}>{r.status}</td>
              <td className="small nowrap"><span className="flag">{flag(r.country)}</span><span className="mono">{r.ip ?? "–"}</span></td>
              <td><Badge tone={tone(r.category)}>{t(r.category as "visitor")}</Badge>{r.observe_only && <Badge tone="warn">observe</Badge>}</td>
              <td className="num small">{fmtNum(r.duration_ms, lang)}</td>
            </tr>))}</tbody>
        </table></div>)}
      {rows.length > 0 && <div className="pad center"><button className="btn ghost" onClick={() => load(rows[rows.length - 1].ts)}>{t("more")}</button></div>}
    </Card>
  );
}
