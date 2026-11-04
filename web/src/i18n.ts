import { createContext, useContext } from "react";

const de = {
  appName: "NetShield Monitor", dashboard: "Dashboard", domains: "Domains", map: "Weltkarte", crowdsec: "CrowdSec",
  requests: "Requests", settings: "Einstellungen", logout: "Abmelden", login: "Anmelden", username: "Benutzername",
  password: "Passwort", loginFailed: "Anmeldung fehlgeschlagen", live: "Live", custom: "Benutzerdefiniert",
  from: "Von", to: "Bis", apply: "Anwenden", requestsToday: "Requests heute", requests24h: "Requests 24 h",
  requestsRange: "Requests im Zeitraum", visitorsEst: "Geschätzte Besucher", visitorsHint: "Eindeutige (pseudonymisierte) IP-Adressen pro Tag ohne Bots, Blockierte und interne Zugriffe. Über mehrere Tage: Summe der Tageswerte.",
  activeDomains: "Aktive Domains", blocked: "Blockiert", blockedHint: "Vom NetBird-Proxy per CrowdSec abgewiesen (Ban oder Captcha) – tatsächlich durchgesetzt.",
  challenged: "Captcha", suspicious: "Verdächtig", visitor: "Besucher", internal: "Intern", alerts: "CrowdSec-Alerts",
  alerts24h: "Alerts 24 h", criticalAlerts: "Kritische Alerts", localDecisions: "Eigene Entscheidungen", communityDecisions: "Community-Sperrlisten",
  securityStatus: "Sicherheitsstatus", ok: "Alles ruhig", warning: "Warnung", critical: "Kritisch", traffic: "Traffic-Verlauf",
  topCountries: "Häufigste Herkunftsländer", country: "Land", allowed: "Erlaubt", total: "Gesamt", rpm: "Req./Min.",
  statusCodes: "HTTP-Statuscodes", topPaths: "Top-URLs", suspiciousPaths: "Auffällige Requests", noData: "Keine Daten im Zeitraum",
  loading: "Lade …", error: "Fehler", approxGeo: "GeoIP-Standorte sind ungefähre Angaben und nicht zwingend der Standort einer Person.",
  mode: "CrowdSec-Modus", enforce: "Enforce", observe: "Observe", wouldBlock: "Wäre blockiert (Observe)",
  observeHint: "Observe: CrowdSec bewertet die Anfrage, sie wird aber trotzdem durchgelassen.",
  scenarios: "Szenarien", decisions: "Entscheidungen", source: "Quelle", target: "Ziel", time: "Zeit", severity: "Schwere",
  duration: "Dauer", remaining: "Restdauer", events: "Ereignisse", alertsVsDecisions: "Alert = erkannt · Entscheidung = Sperre beschlossen · Blockiert = tatsächlich abgewiesen",
  enforcement: "Durchsetzung", netbirdProxy: "NetBird-Proxy", appsec: "CrowdSec AppSec", firewall: "Firewall-Bouncer",
  notAvailable: "nicht messbar", sources: "Datenquellen", status: "Status", lastSuccess: "Letzter Erfolg", tokens: "API-Tokens",
  newToken: "Neuer Token", name: "Name", scope: "Berechtigung", create: "Erstellen", revoke: "Widerrufen", tokenOnce: "Token jetzt kopieren – er wird nur einmal angezeigt:",
  notifications: "Benachrichtigungen", save: "Speichern", saved: "Gespeichert", testNtfy: "ntfy testen", privacy: "Datenschutz",
  ipMode: "IP-Speicherung", truncated: "gekürzt", full: "vollständig", retention: "Aufbewahrung", days: "Tage",
  addDomain: "Domain hinzufügen", hide: "Ausblenden", show: "Einblenden", hidden: "ausgeblendet", lastSeen: "Zuletzt gesehen",
  method: "Methode", path: "Pfad", ip: "IP/Netz", category: "Kategorie", all: "Alle", more: "Mehr laden",
  heatmap: "Heatmap", mapMode: "Anzeige", recent: "Letzte Requests", originCountries: "Herkunft der Angreifer",
  never: "nie", theme: "Design", language: "Sprache", dark: "Dunkel", light: "Hell", system: "System",
  historyDecisions: "Aktive Entscheidungen im Verlauf", local: "Eigene", community: "Community", alertsTimeline: "Alerts im Verlauf",
  notConfigured: "nicht konfiguriert", recentNotifications: "Letzte Benachrichtigungen",
};
type Dict = typeof de;
const en: Dict = {
  appName: "NetShield Monitor", dashboard: "Dashboard", domains: "Domains", map: "World map", crowdsec: "CrowdSec",
  requests: "Requests", settings: "Settings", logout: "Log out", login: "Log in", username: "Username",
  password: "Password", loginFailed: "Login failed", live: "Live", custom: "Custom",
  from: "From", to: "To", apply: "Apply", requestsToday: "Requests today", requests24h: "Requests 24 h",
  requestsRange: "Requests in range", visitorsEst: "Estimated visitors", visitorsHint: "Distinct (pseudonymised) IP addresses per day excluding bots, blocked and internal traffic. Over several days: sum of daily values.",
  activeDomains: "Active domains", blocked: "Blocked", blockedHint: "Rejected by the NetBird proxy via CrowdSec (ban or captcha) – actually enforced.",
  challenged: "Captcha", suspicious: "Suspicious", visitor: "Visitors", internal: "Internal", alerts: "CrowdSec alerts",
  alerts24h: "Alerts 24 h", criticalAlerts: "Critical alerts", localDecisions: "Local decisions", communityDecisions: "Community blocklists",
  securityStatus: "Security status", ok: "All quiet", warning: "Warning", critical: "Critical", traffic: "Traffic",
  topCountries: "Top countries", country: "Country", allowed: "Allowed", total: "Total", rpm: "Req/min",
  statusCodes: "HTTP status codes", topPaths: "Top URLs", suspiciousPaths: "Suspicious requests", noData: "No data in range",
  loading: "Loading …", error: "Error", approxGeo: "GeoIP locations are approximate and not necessarily where a person is.",
  mode: "CrowdSec mode", enforce: "Enforce", observe: "Observe", wouldBlock: "Would be blocked (observe)",
  observeHint: "Observe: CrowdSec evaluates the request but lets it through anyway.",
  scenarios: "Scenarios", decisions: "Decisions", source: "Source", target: "Target", time: "Time", severity: "Severity",
  duration: "Duration", remaining: "Remaining", events: "Events", alertsVsDecisions: "Alert = detected · Decision = remediation exists · Blocked = actually rejected",
  enforcement: "Enforcement", netbirdProxy: "NetBird proxy", appsec: "CrowdSec AppSec", firewall: "Firewall bouncer",
  notAvailable: "not measurable", sources: "Data sources", status: "Status", lastSuccess: "Last success", tokens: "API tokens",
  newToken: "New token", name: "Name", scope: "Scope", create: "Create", revoke: "Revoke", tokenOnce: "Copy the token now – it is shown only once:",
  notifications: "Notifications", save: "Save", saved: "Saved", testNtfy: "Test ntfy", privacy: "Privacy",
  ipMode: "IP storage", truncated: "truncated", full: "full", retention: "Retention", days: "days",
  addDomain: "Add domain", hide: "Hide", show: "Show", hidden: "hidden", lastSeen: "Last seen",
  method: "Method", path: "Path", ip: "IP/network", category: "Category", all: "All", more: "Load more",
  heatmap: "Heatmap", mapMode: "Show", recent: "Recent requests", originCountries: "Attacker origin",
  never: "never", theme: "Theme", language: "Language", dark: "Dark", light: "Light", system: "System",
  historyDecisions: "Active decisions over time", local: "Local", community: "Community", alertsTimeline: "Alerts over time",
  notConfigured: "not configured", recentNotifications: "Recent notifications",
};
export const dictionaries = { de, en };
export type Lang = keyof typeof dictionaries;
export type TKey = keyof Dict;
export const I18nContext = createContext<{ lang: Lang; t: (k: TKey) => string; setLang: (l: Lang) => void }>({
  lang: "de", t: (k) => de[k], setLang: () => {},
});
export const useT = () => useContext(I18nContext);
export function detectLang(): Lang {
  try { const s = localStorage.getItem("nsm.lang"); if (s === "de" || s === "en") return s; } catch { /* ignore */ }
  return navigator.language?.toLowerCase().startsWith("de") ? "de" : "en";
}
