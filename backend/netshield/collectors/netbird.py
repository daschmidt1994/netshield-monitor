"""NetBird collectors.

Uses only documented Management API endpoints (verified against NetBird v0.81 OpenAPI):

* ``GET /api/events/proxy`` – reverse proxy access logs (paginated, max 100/page,
  ``sort_by``/``sort_order``/``start_date`` filters)
* ``GET /api/reverse-proxies/services`` – configured reverse proxy services (domains)

Authentication: ``Authorization: Token <personal access token>`` of a service user.
"""

from __future__ import annotations

import logging
import secrets
from collections import defaultdict

import httpx
from sqlalchemy import select, update

from .. import USER_AGENT
from ..config import Settings
from ..database import Database, upsert
from ..database.models import (
    Domain,
    HourlyStat,
    ProxyRequest,
    VisitorSalt,
)
from ..database.session import existing_ids
from ..security.privacy import IpPolicy, visitor_hash
from ..services.classify import classify
from ..util import local_day, now_ts, parse_rfc3339, to_rfc3339
from .base import Collector, CollectorError

log = logging.getLogger(__name__)

PAGE_SIZE = 100


class NetBirdClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base = settings.netbird_url
        token = settings.netbird_token.get_secret_value() if settings.netbird_token else ""
        self._client = httpx.AsyncClient(
            base_url=self.base or "http://invalid",
            headers={"Authorization": f"Token {token}", "Accept": "application/json",
                     "User-Agent": USER_AGENT},
            timeout=httpx.Timeout(30.0, connect=10.0),
            verify=settings.netbird_verify_tls,
            transport=transport,
        )

    async def get(self, path: str, params: dict | None = None):
        try:
            r = await self._client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise CollectorError(f"NetBird API not reachable: {type(exc).__name__}") from exc
        if r.status_code == 401:
            raise CollectorError("NetBird API rejected the token (401) – check NETSHIELD_NETBIRD_TOKEN")
        if r.status_code == 403:
            raise CollectorError(f"NetBird token lacks permission for {path} (403)")
        if r.status_code >= 400:
            raise CollectorError(f"NetBird API error {r.status_code} on {path}")
        return r.json()

    async def proxy_events(self, start_ts: int, page: int) -> dict:
        return await self.get(
            "/api/events/proxy",
            {
                "page": page,
                "page_size": PAGE_SIZE,
                "sort_by": "timestamp",
                "sort_order": "asc",
                "start_date": to_rfc3339(start_ts),
            },
        )

    async def services(self) -> list[dict]:
        data = await self.get("/api/reverse-proxies/services")
        return data if isinstance(data, list) else []

    async def aclose(self) -> None:
        await self._client.aclose()


class SaltCache:
    """Per-day random salts for visitor pseudonyms (deleted by maintenance after the day ends)."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._cache: dict[str, str] = {}

    async def get(self, session, day: str) -> str:
        if day in self._cache:
            return self._cache[day]
        row = await session.get(VisitorSalt, day)
        if row is None:
            row = VisitorSalt(day=day, salt=secrets.token_hex(32))
            session.add(row)
            await session.flush()
        self._cache[day] = row.salt
        if len(self._cache) > 64:
            self._cache.pop(next(iter(self._cache)))
        return row.salt

    def forget(self, day: str) -> None:
        self._cache.pop(day, None)


def normalize_event(ev: dict, policy: IpPolicy) -> dict | None:
    ts = parse_rfc3339(ev.get("timestamp"))
    if ts is None or not ev.get("id"):
        return None
    meta = ev.get("metadata") or {}
    auth = ev.get("auth_method_used") or ""
    verdict = meta.get("crowdsec_verdict") or (auth if auth.startswith("crowdsec_") else None)
    observe_only = meta.get("crowdsec_mode") == "observe"
    raw_ip = ev.get("source_ip") or ""
    internal = policy.is_internal(raw_ip)
    path = (ev.get("path") or "/")[:512]
    method = (ev.get("method") or ev.get("protocol") or "").upper()[:16]
    return {
        "id": str(ev["id"])[:64],
        "ts": ts,
        "service_id": ev.get("service_id"),
        "host": (ev.get("host") or "unknown").lower()[:255],
        "method": method,
        "path": path,
        "protocol": (ev.get("protocol") or "http")[:8],
        "status": int(ev.get("status_code") or 0),
        "duration_ms": int(ev.get("duration_ms") or 0),
        "bytes_up": int(ev.get("bytes_upload") or 0),
        "bytes_down": int(ev.get("bytes_download") or 0),
        "ip": policy.display(raw_ip),
        "country": (ev.get("country_code") or None),
        "city": (ev.get("city_name") or None),
        "authenticated": bool(ev.get("user_id")) or auth in ("oidc", "password", "pin", "header"),
        "verdict": verdict[:32] if verdict else None,
        "observe_only": bool(verdict) and observe_only,
        "category": classify(path=path, method=method, verdict=verdict, observe_only=observe_only,
                             internal=internal),
        "reason": (ev.get("reason") or None),
        "_raw_ip": raw_ip,
    }


class NetBirdAccessLogCollector(Collector):
    name = "netbird_access_logs"

    def __init__(self, db: Database, settings: Settings, client: NetBirdClient | None = None) -> None:
        super().__init__(db)
        self.settings = settings
        self.interval = settings.netbird_poll_seconds
        self.client = client or NetBirdClient(settings)
        self.policy = IpPolicy(settings.ip_mode, settings.ipv4_prefix, settings.ipv6_prefix,
                               settings.internal_networks)
        self.salts = SaltCache(db)

    @property
    def enabled(self) -> bool:
        return self.settings.netbird_enabled

    async def run_once(self) -> int:
        state = await self.get_state()
        cursor = dict(state.cursor or {})
        start_ts = int(cursor.get("last_ts") or (now_ts() - self.settings.netbird_backfill_hours * 3600))
        inserted = 0
        max_ts = start_ts
        page = 1
        backlog = False
        while True:
            data = await self.client.proxy_events(start_ts, page)
            events = data.get("data") or []
            inserted += await self.ingest(events)
            for ev in events:
                ts = parse_rfc3339(ev.get("timestamp"))
                if ts and ts > max_ts:
                    max_ts = ts
            total_pages = int(data.get("total_pages") or 0)
            if page >= total_pages or not events:
                break
            if page >= self.settings.netbird_max_pages_per_cycle:
                backlog = True
                break
            page += 1
        cursor["last_ts"] = max_ts
        await self.save_cursor(cursor)
        self._status_override = "backfill" if backlog else None
        if backlog:
            self.interval = 2  # catch up quickly, but politely
        else:
            self.interval = self.settings.netbird_poll_seconds
        return inserted

    async def ingest(self, events: list[dict]) -> int:
        rows = [r for r in (normalize_event(e, self.policy) for e in events) if r]
        if not rows:
            return 0
        tz = self.settings.timezone
        async with self.db.session() as s:
            known = await existing_ids(s, ProxyRequest.id, [r["id"] for r in rows])
            new = [r for r in rows if r["id"] not in known]
            # de-duplicate within the batch as well
            seen: set[str] = set()
            new = [r for r in new if not (r["id"] in seen or seen.add(r["id"]))]
            if not new:
                return 0
            for r in new:
                raw_ip = r.pop("_raw_ip")
                if raw_ip and r["category"] != "internal":
                    salt = await self.salts.get(s, local_day(r["ts"], tz))
                    r["visitor_hash"] = visitor_hash(salt, raw_ip)
                else:
                    r["visitor_hash"] = None
            await upsert(s, ProxyRequest, new, ["id"])

            agg: dict[tuple, list[int]] = defaultdict(lambda: [0, 0, 0])
            hosts: dict[str, tuple[int, int, str | None]] = {}
            for r in new:
                key = (r["ts"] - r["ts"] % 3600, r["host"], r["country"] or "--", r["status"], r["category"])
                a = agg[key]
                a[0] += 1
                a[1] += r["bytes_down"]
                a[2] += 1 if r["observe_only"] else 0
                lo, hi, sid = hosts.get(r["host"], (r["ts"], r["ts"], r["service_id"]))
                hosts[r["host"]] = (min(lo, r["ts"]), max(hi, r["ts"]), sid or r["service_id"])
            await upsert(
                s,
                HourlyStat,
                [
                    {"hour": k[0], "host": k[1], "country": k[2], "status": k[3], "category": k[4],
                     "count": v[0], "bytes_down": v[1], "observe_hits": v[2]}
                    for k, v in agg.items()
                ],
                ["hour", "host", "country", "status", "category"],
                add=["count", "bytes_down", "observe_hits"],
            )
            # domain auto-discovery from observed hosts
            existing = {
                d.host: d
                for d in (await s.execute(select(Domain).where(Domain.host.in_(list(hosts))))).scalars()
            }
            for host, (lo, hi, sid) in hosts.items():
                d = existing.get(host)
                if d is None:
                    s.add(Domain(host=host, source="logs", service_id=sid, first_seen=lo, last_seen=hi))
                else:
                    d.first_seen = min(d.first_seen or lo, lo)
                    d.last_seen = max(d.last_seen or hi, hi)
            await s.commit()
        return len(new)


class NetBirdServicesCollector(Collector):
    name = "netbird_services"

    def __init__(self, db: Database, settings: Settings, client: NetBirdClient | None = None) -> None:
        super().__init__(db)
        self.settings = settings
        self.interval = settings.netbird_services_poll_seconds
        self.client = client or NetBirdClient(settings)

    @property
    def enabled(self) -> bool:
        return self.settings.netbird_enabled

    async def run_once(self) -> int:
        services = await self.client.services()
        seen: set[str] = set()
        changed = 0
        async with self.db.session() as s:
            for svc in services:
                host = (svc.get("domain") or "").lower().strip()
                if not host:
                    continue
                seen.add(host)
                restrictions = svc.get("access_restrictions") or {}
                auth = svc.get("auth") or {}
                auth_enabled = any(
                    (v.get("enabled") if isinstance(v, dict) else bool(v)) for v in auth.values()
                ) if isinstance(auth, dict) else False
                d = await s.get(Domain, host)
                if d is None:
                    d = Domain(host=host, first_seen=None)
                    s.add(d)
                    changed += 1
                d.source = "netbird"
                d.service_id = svc.get("id")
                d.display_name = d.display_name or svc.get("name")
                d.enabled = bool(svc.get("enabled", True))
                d.crowdsec_mode = restrictions.get("crowdsec_mode") or None
                d.auth_enabled = auth_enabled
                d.removed_upstream = False
            await s.execute(
                update(Domain)
                .where(Domain.source == "netbird", Domain.host.not_in(seen or {""}))
                .values(removed_upstream=True)
            )
            await s.commit()
        return changed
