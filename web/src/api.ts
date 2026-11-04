// Thin API client. Session cookie auth + CSRF header for state-changing requests.
export type RangeKey = "live" | "1h" | "24h" | "7d" | "30d" | "custom";
export interface RangeSel { key: RangeKey; from?: number; to?: number }

let csrf: string | null = null;
export const setCsrf = (t: string | null) => { csrf = t; };

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && csrf) headers["X-CSRF-Token"] = csrf;
  const r = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), credentials: "same-origin" });
  if (!r.ok) {
    let msg = r.statusText;
    try { const j = await r.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* ignore */ }
    if (r.status === 401) window.dispatchEvent(new Event("nsm:unauthorized"));
    throw new ApiError(r.status, msg);
  }
  return r.json() as Promise<T>;
}

export const api = {
  get: <T,>(path: string, params?: Record<string, string | number | undefined | null | boolean>) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params ?? {})) if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
    const q = qs.toString();
    return request<T>("GET", q ? `${path}?${q}` : path);
  },
  post: <T,>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  put: <T,>(path: string, body: unknown) => request<T>("PUT", path, body),
  patch: <T,>(path: string, body: unknown) => request<T>("PATCH", path, body),
  del: <T,>(path: string) => request<T>("DELETE", path),
};

export function rangeParams(r: RangeSel) {
  return r.key === "custom" ? { from: r.from, to: r.to } : { range: r.key };
}

// ---- response types (subset of the OpenAPI schema at /api/docs) ----
export interface CategoryTotals {
  requests: number; external_requests: number; blocked: number; challenged: number; suspicious: number;
  internal: number; would_block_observe: number; bytes_down: number; by_category: Record<string, number>;
}
export interface CountryRow { country: string | null; requests: number; blocked: number; allowed: number }
export interface SecurityStatus { level: "ok" | "warning" | "critical"; reasons: { code: string; value: unknown }[] }
export interface Overview {
  range: { start: number; end: number; label: string };
  requests: CategoryTotals; requests_today: number; requests_24h: number; blocked_24h: number;
  visitors: { value: number; method: string }; visitors_today: { value: number; method: string };
  active_domains: number; known_domains: number; requests_per_minute: number;
  crowdsec: { alerts: number; alerts_24h: number; critical_alerts_24h: number; local_active_decisions: number; community_active_decisions: number };
  top_countries: CountryRow[]; security_status: SecurityStatus;
}
export interface TsPoint { ts: number; total: number; visitor: number; suspicious: number; blocked: number; challenged: number; internal: number }
export interface Timeseries { bucket_seconds: number; source: string; points: TsPoint[] }
export interface DomainRow {
  host: string; display_name: string | null; source: string; enabled: boolean; hidden: boolean; removed_upstream: boolean;
  crowdsec_mode: string | null; auth_enabled: boolean; last_seen: number | null; requests: number; blocked: number;
  suspicious: number; internal: number; requests_per_minute: number;
}
export interface PathRow { host: string; path: string; requests: number; blocked: number; errors: number }
export interface AlertSummary {
  alerts: number; alerts_with_decision: number; by_severity: Record<string, number>;
  top_scenarios: { scenario: string; count: number }[]; countries: { country: string | null; count: number }[];
  timeseries: { bucket_seconds: number; points: { ts: number; alerts: number }[] };
}
export interface DomainDetail {
  host: string; info: null | { source: string; display_name: string | null; enabled: boolean; crowdsec_mode: string | null; auth_enabled: boolean; first_seen: number | null; last_seen: number | null };
  requests: CategoryTotals; requests_per_minute: number; visitors: { value: number; method: string };
  countries: CountryRow[]; statuses: { status: number; count: number }[];
  top_paths: { items: PathRow[]; clipped_to_raw_retention: boolean }; suspicious_paths: { items: PathRow[]; clipped_to_raw_retention: boolean };
  timeseries: Timeseries; crowdsec: AlertSummary;
}
export interface AlertRow {
  id: number; scenario: string; message: string; created: number; events: number; source: string | null; range: string | null;
  country: string | null; as_name: string | null; target_host: string | null; decisions: number; decision_type: string | null;
  decision_duration: string | null; severity: string; simulated: boolean;
}
export interface DecisionsResp {
  snapshot_ts: number | null; local_active: number; community_active: number;
  by_origin: { origin: string; type: string; count: number }[];
  local_decisions?: { id: number; origin: string; type: string; scope: string; value: string; scenario: string | null; expires: number | null; remaining_seconds: number | null }[];
}
export interface CrowdsecSummary {
  alerts: AlertSummary; decisions: DecisionsResp; decision_history: { ts: number; local: number; community: number }[];
  enforcement: Record<string, { blocked: number | null; challenged?: number; would_block_observe?: number; evidence: string }>;
}
export interface RequestRow {
  id: string; ts: number; host: string; method: string; path: string; status: number; duration_ms: number; ip: string | null;
  country: string | null; city: string | null; category: string; verdict: string | null; observe_only: boolean; protocol: string;
}
export interface SourceRow { name: string; configured: boolean; status?: string; last_success?: number | null; last_error?: string | null; items_total?: number }
export interface NotificationRow { id: number; ts: number; kind: string; severity: string; title: string; message: string; host: string | null; delivered_ntfy: boolean }
