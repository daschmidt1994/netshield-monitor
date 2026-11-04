import { useCallback, useEffect, useRef, useState } from "react";

// Live refresh: one shared EventSource; components re-fetch (throttled) when new data arrives.
type Listener = () => void;
const listeners = new Set<Listener>();
let es: EventSource | null = null;
let lastFire = 0;
let pending: number | null = null;

function fire() {
  const now = Date.now();
  const wait = Math.max(0, 15000 - (now - lastFire)); // at most every 15 s
  if (pending !== null) return;
  pending = window.setTimeout(() => {
    pending = null; lastFire = Date.now();
    listeners.forEach((l) => l());
  }, wait);
}

export function startLive() {
  if (es) return;
  es = new EventSource("/api/v1/stream", { withCredentials: true });
  es.addEventListener("update", fire);
  es.addEventListener("notification", (e) => {
    fire();
    window.dispatchEvent(new CustomEvent("nsm:notification", { detail: JSON.parse((e as MessageEvent).data) }));
  });
}
export function stopLive() { es?.close(); es = null; }

export function useApi<T>(fn: () => Promise<T>, deps: unknown[], opts: { live?: boolean; interval?: number } = {}) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const load = useCallback(async () => {
    try { setData(await fnRef.current()); setError(null); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { setLoading(true); load(); }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (opts.live === false) return;
    listeners.add(load);
    const iv = opts.interval ? window.setInterval(load, opts.interval) : undefined;
    return () => { listeners.delete(load); if (iv) window.clearInterval(iv); };
  }, [load, opts.live, opts.interval]);
  return { data, error, loading, reload: load };
}

export function useHashRoute(): [string, (p: string) => void] {
  const get = () => window.location.hash.replace(/^#/, "") || "/";
  const [route, setRoute] = useState(get);
  useEffect(() => {
    const h = () => setRoute(get());
    window.addEventListener("hashchange", h);
    return () => window.removeEventListener("hashchange", h);
  }, []);
  return [route, (p: string) => { window.location.hash = p; }];
}
