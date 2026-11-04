import { useEffect, useMemo, useState } from "react";
import { api, setCsrf, type RangeSel } from "./api";
import { dictionaries, I18nContext, detectLang, type Lang, type TKey } from "./i18n";
import { startLive, stopLive, useHashRoute } from "./hooks";
import { RangePicker } from "./components/ui";
import { Dashboard } from "./pages/Dashboard";
import { DomainPage, Domains } from "./pages/Domains";
import { MapPage } from "./pages/MapPage";
import { CrowdSec } from "./pages/CrowdSec";
import { Requests } from "./pages/Requests";
import { Settings } from "./pages/Settings";
import { Login } from "./pages/Login";

type Theme = "system" | "light" | "dark";
const store = {
  get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* ignore */ } },
};

const NAV: { path: string; key: TKey; icon: string }[] = [
  { path: "/", key: "dashboard", icon: "▦" },
  { path: "/domains", key: "domains", icon: "◎" },
  { path: "/map", key: "map", icon: "◍" },
  { path: "/crowdsec", key: "crowdsec", icon: "⛨" },
  { path: "/requests", key: "requests", icon: "≡" },
  { path: "/settings", key: "settings", icon: "⚙" },
];

export default function App() {
  const [lang, setLangState] = useState<Lang>(detectLang());
  const [theme, setTheme] = useState<Theme>((store.get("nsm.theme") as Theme) || "system");
  const [user, setUser] = useState<string | null | undefined>(undefined);
  const [route] = useHashRoute();
  const [range, setRange] = useState<RangeSel>(() => {
    const k = store.get("nsm.range");
    return { key: (k === "live" || k === "1h" || k === "24h" || k === "7d" || k === "30d") ? k : "24h" };
  });
  const i18n = useMemo(() => ({
    lang, t: (k: TKey) => dictionaries[lang][k],
    setLang: (l: Lang) => { setLangState(l); store.set("nsm.lang", l); },
  }), [lang]);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  useEffect(() => {
    if (theme === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", theme);
    store.set("nsm.theme", theme);
  }, [theme]);
  useEffect(() => {
    api.get<{ name: string; csrf_token: string | null }>("/api/v1/auth/me")
      .then((me) => { setCsrf(me.csrf_token); setUser(me.name); })
      .catch(() => setUser(null));
    const onUnauth = () => setUser(null);
    window.addEventListener("nsm:unauthorized", onUnauth);
    return () => window.removeEventListener("nsm:unauthorized", onUnauth);
  }, []);
  useEffect(() => { if (user) startLive(); else stopLive(); }, [user]);

  const changeRange = (r: RangeSel) => { setRange(r); if (r.key !== "custom") store.set("nsm.range", r.key); };

  if (user === undefined) return null;
  if (user === null) return <I18nContext.Provider value={i18n}><Login onLogin={setUser} /></I18nContext.Provider>;

  const domainMatch = route.match(/^\/domains\/(.+)$/);
  let page;
  if (domainMatch) page = <DomainPage host={decodeURIComponent(domainMatch[1])} range={range} />;
  else if (route === "/domains") page = <Domains range={range} />;
  else if (route === "/map") page = <MapPage range={range} />;
  else if (route === "/crowdsec") page = <CrowdSec range={range} />;
  else if (route === "/requests") page = <Requests />;
  else if (route === "/settings") page = <Settings />;
  else page = <Dashboard range={range} />;
  const showRange = !["/requests", "/settings"].includes(route);
  const active = (p: string) => (p === "/" ? route === "/" : route.startsWith(p));

  return (
    <I18nContext.Provider value={i18n}>
      <div className="shell">
        <aside className="sidebar">
          <div className="brand"><img src="/favicon.svg" alt="" width={26} height={26} /><span>NetShield</span></div>
          <nav>{NAV.map((n) => (
            <a key={n.path} href={`#${n.path}`} className={active(n.path) ? "active" : ""}><span className="ico" aria-hidden>{n.icon}</span><span className="lbl">{i18n.t(n.key)}</span></a>
          ))}</nav>
          <div className="side-foot">
            <select value={lang} onChange={(e) => i18n.setLang(e.target.value as Lang)} aria-label={i18n.t("language")}><option value="de">Deutsch</option><option value="en">English</option></select>
            <select value={theme} onChange={(e) => setTheme(e.target.value as Theme)} aria-label={i18n.t("theme")}>
              <option value="system">{i18n.t("system")}</option><option value="light">{i18n.t("light")}</option><option value="dark">{i18n.t("dark")}</option>
            </select>
            <button className="btn ghost" onClick={async () => { await api.post("/api/v1/auth/logout").catch(() => {}); setUser(null); }}>{i18n.t("logout")}</button>
          </div>
        </aside>
        <main className="content">
          {showRange && <div className="toolbar"><RangePicker value={range} onChange={changeRange} /></div>}
          {page}
        </main>
      </div>
    </I18nContext.Provider>
  );
}
