import type { ReactNode } from "react";
import type { RangeKey, RangeSel } from "../api";
import { useT } from "../i18n";
import { useState } from "react";

export function Card({ title, children, actions, className = "", hint }: { title?: ReactNode; children: ReactNode; actions?: ReactNode; className?: string; hint?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          <h2 title={hint}>{title}{hint && <span className="hint-dot" aria-label={hint}>?</span>}</h2>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, sub, tone, hint }: { label: string; value: ReactNode; sub?: ReactNode; tone?: "ok" | "warn" | "bad" | "accent"; hint?: string }) {
  return (
    <div className={`stat ${tone ? `tone-${tone}` : ""}`} title={hint}>
      <div className="stat-label">{label}{hint && <span className="hint-dot">?</span>}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export function Loading() { const { t } = useT(); return <div className="muted pad">{t("loading")}</div>; }
export function ErrorBox({ error }: { error: string }) { const { t } = useT(); return <div className="error-box">{t("error")}: {error}</div>; }
export function Empty() { const { t } = useT(); return <div className="muted pad">{t("noData")}</div>; }

const KEYS: RangeKey[] = ["live", "1h", "24h", "7d", "30d", "custom"];
const toLocalInput = (ts: number) => { const d = new Date(ts * 1000); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); };

export function RangePicker({ value, onChange }: { value: RangeSel; onChange: (r: RangeSel) => void }) {
  const { t } = useT();
  const now = Math.floor(Date.now() / 1000);
  const [from, setFrom] = useState(toLocalInput(value.from ?? now - 86400 * 3));
  const [to, setTo] = useState(toLocalInput(value.to ?? now));
  return (
    <div className="range-picker">
      <div className="seg" role="tablist">
        {KEYS.map((k) => (
          <button key={k} role="tab" aria-selected={value.key === k} className={value.key === k ? "active" : ""}
            onClick={() => k === "custom" ? onChange({ key: "custom", from: Math.floor(new Date(from).getTime() / 1000), to: Math.floor(new Date(to).getTime() / 1000) }) : onChange({ key: k })}>
            {k === "live" ? t("live") : k === "custom" ? t("custom") : k}
          </button>
        ))}
      </div>
      {value.key === "custom" && (
        <div className="custom-range">
          <label>{t("from")} <input type="datetime-local" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
          <label>{t("to")} <input type="datetime-local" value={to} onChange={(e) => setTo(e.target.value)} /></label>
          <button className="btn" onClick={() => onChange({ key: "custom", from: Math.floor(new Date(from).getTime() / 1000), to: Math.floor(new Date(to).getTime() / 1000) })}>{t("apply")}</button>
        </div>
      )}
    </div>
  );
}

export function Badge({ children, tone }: { children: ReactNode; tone?: "ok" | "warn" | "bad" | "muted" | "accent" }) {
  return <span className={`badge ${tone ? `tone-${tone}` : ""}`}>{children}</span>;
}

export function Bar({ value, max, tone }: { value: number; max: number; tone?: string }) {
  const pct = max > 0 ? Math.max(2, (value / max) * 100) : 0;
  return <div className="bar"><div className={`bar-fill ${tone ?? ""}`} style={{ width: `${pct}%` }} /></div>;
}
