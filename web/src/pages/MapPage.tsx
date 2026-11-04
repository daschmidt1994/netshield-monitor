import { useState } from "react";
import { api, rangeParams, type CountryRow, type DomainRow, type RangeSel } from "../api";
import { useApi } from "../hooks";
import { useT } from "../i18n";
import { Card, ErrorBox, Loading } from "../components/ui";
import { WorldMap, type MapMetric } from "../components/WorldMap";
import { CountryTable } from "../components/tables";

export function MapPage({ range }: { range: RangeSel }) {
  const { t } = useT();
  const p = rangeParams(range);
  const [host, setHost] = useState("");
  const [metric, setMetric] = useState<MapMetric>("requests");
  const doms = useApi(() => api.get<{ items: DomainRow[] }>("/api/v1/domains", p), [JSON.stringify(p)], { live: false });
  const c = useApi(() => api.get<{ items: CountryRow[] }>("/api/v1/countries", { ...p, host: host || undefined }), [JSON.stringify(p), host]);
  return (
    <div className="stack">
      <Card title={t("map")} hint={t("approxGeo")} actions={
        <div className="row gap">
          <select value={host} onChange={(e) => setHost(e.target.value)} aria-label="Domain">
            <option value="">{t("all")} {t("domains")}</option>
            {doms.data?.items.map((d) => <option key={d.host} value={d.host}>{d.host}</option>)}
          </select>
          <div className="seg">
            {(["requests", "allowed", "blocked"] as MapMetric[]).map((m) => (
              <button key={m} className={metric === m ? "active" : ""} onClick={() => setMetric(m)}>{m === "requests" ? t("total") : t(m)}</button>))}
          </div>
        </div>}>
        {c.error ? <ErrorBox error={c.error} /> : c.data ? <WorldMap rows={c.data.items} metric={metric} height={480} /> : <Loading />}
        <p className="muted small">{t("approxGeo")}</p>
      </Card>
      {c.data && <Card title={t("topCountries")}><CountryTable rows={c.data.items} limit={50} /></Card>}
    </div>
  );
}
