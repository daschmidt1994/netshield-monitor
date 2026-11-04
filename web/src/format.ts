import type { Lang } from "./i18n";

export const fmtNum = (n: number | null | undefined, lang: Lang) =>
  n === null || n === undefined ? "–" : new Intl.NumberFormat(lang === "de" ? "de-AT" : "en-US").format(n);

export const fmtCompact = (n: number, lang: Lang) =>
  new Intl.NumberFormat(lang === "de" ? "de-AT" : "en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);

export const fmtTime = (ts: number | null | undefined, lang: Lang, withDate = true) =>
  !ts ? "–" : new Date(ts * 1000).toLocaleString(lang === "de" ? "de-AT" : "en-US",
    withDate ? { dateStyle: "short", timeStyle: "medium" } : { timeStyle: "short" });

export const fmtBytes = (b: number) => {
  const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0; let v = b;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${u[i]}`;
};

export const fmtDuration = (s: number | null | undefined) => {
  if (s === null || s === undefined) return "–";
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`;
};

const regionNames: Record<string, Intl.DisplayNames> = {};
export const countryName = (code: string | null | undefined, lang: Lang) => {
  if (!code) return lang === "de" ? "Unbekannt" : "Unknown";
  try {
    regionNames[lang] ??= new Intl.DisplayNames([lang], { type: "region" });
    return regionNames[lang].of(code.toUpperCase()) ?? code;
  } catch { return code; }
};

export const flag = (code: string | null | undefined) =>
  !code || code.length !== 2 ? "🏳️" : String.fromCodePoint(...[...code.toUpperCase()].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65));
