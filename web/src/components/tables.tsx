import type { CountryRow, PathRow } from "../api";
import { useT } from "../i18n";
import { countryName, flag, fmtNum } from "../format";
import { Bar, Empty } from "./ui";

export function CountryTable({ rows, limit = 10 }: { rows: CountryRow[]; limit?: number }) {
  const { t, lang } = useT();
  if (!rows.length) return <Empty />;
  const max = Math.max(...rows.map((r) => r.requests));
  return (
    <table className="table">
      <thead><tr><th>{t("country")}</th><th className="num">{t("total")}</th><th className="num">{t("blocked")}</th><th className="wbar" /></tr></thead>
      <tbody>
        {rows.slice(0, limit).map((r) => (
          <tr key={r.country ?? "--"}>
            <td><span className="flag">{flag(r.country)}</span>{countryName(r.country, lang)}</td>
            <td className="num">{fmtNum(r.requests, lang)}</td>
            <td className={`num ${r.blocked ? "bad-text" : "muted"}`}>{r.blocked ? fmtNum(r.blocked, lang) : "–"}</td>
            <td className="wbar"><Bar value={r.requests} max={max} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function PathTable({ rows, showHost = false }: { rows: PathRow[]; showHost?: boolean }) {
  const { t, lang } = useT();
  if (!rows.length) return <Empty />;
  return (
    <div className="table-wrap">
      <table className="table">
        <thead><tr>{showHost && <th>Host</th>}<th>{t("path")}</th><th className="num">{t("total")}</th><th className="num">{t("blocked")}</th><th className="num">4xx/5xx</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.host + r.path}>
              {showHost && <td className="mono small">{r.host}</td>}
              <td className="mono path" title={r.path}>{r.path}</td>
              <td className="num">{fmtNum(r.requests, lang)}</td>
              <td className={`num ${r.blocked ? "bad-text" : "muted"}`}>{r.blocked ? fmtNum(r.blocked, lang) : "–"}</td>
              <td className="num">{r.errors ? fmtNum(r.errors, lang) : "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
