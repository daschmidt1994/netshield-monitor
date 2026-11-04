"""CrowdSec collectors using the documented Local API (LAPI) and Prometheus metrics.

* Decisions: ``GET /v1/decisions`` with a **bouncer API key** (``X-Api-Key``) – read access to
  active decisions only.
* Alerts: ``POST /v1/watchers/login`` + ``GET /v1/alerts`` with **machine credentials**.
  CrowdSec has no read-only machine role; credentials stay server-side and are never exposed
  through the NetShield API.
* Metrics: Prometheus text endpoint (default ``:6060/metrics``).

Important distinction (shown separately in all UIs):
  alert = something was detected, decision = a remediation exists,
  blocked = enforcement actually observed (NetBird proxy access logs, see netbird.py).
"""

from __future__ import annotations

import logging
import re
import time
from collections import Counter

import httpx
from sqlalchemy import delete

from .. import USER_AGENT
from ..config import Settings
from ..database import Database, upsert
from ..database.models import CrowdsecAlert, CrowdsecDecision, DecisionCount, MetricSample
from ..security.privacy import IpPolicy
from ..util import now_ts, parse_go_duration, parse_rfc3339
from .base import Collector, CollectorError

log = logging.getLogger(__name__)

ALERT_WINDOW = 6 * 3600
ALERT_LIMIT = 1000


class LapiClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.crowdsec_lapi_url or "http://invalid",
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=httpx.Timeout(60.0, connect=10.0),
            transport=transport,
        )
        self._jwt: str | None = None
        self._jwt_exp: float = 0

    async def _request(self, method: str, path: str, **kw) -> httpx.Response:
        try:
            return await self._client.request(method, path, **kw)
        except httpx.HTTPError as exc:
            raise CollectorError(f"CrowdSec LAPI not reachable: {type(exc).__name__}") from exc

    async def decisions(self, origins: list[str] | None = None) -> list[dict]:
        key = self.settings.crowdsec_bouncer_key.get_secret_value() if self.settings.crowdsec_bouncer_key else ""
        params = {"origins": ",".join(origins)} if origins else None
        r = await self._request("GET", "/v1/decisions", headers={"X-Api-Key": key}, params=params)
        if r.status_code == 403 or r.status_code == 401:
            raise CollectorError("CrowdSec rejected the bouncer key – check NETSHIELD_CROWDSEC_BOUNCER_KEY")
        if r.status_code >= 400:
            raise CollectorError(f"CrowdSec LAPI error {r.status_code} on /v1/decisions")
        return r.json() or []

    async def _login(self) -> str:
        if self._jwt and time.time() < self._jwt_exp - 60:
            return self._jwt
        pw = self.settings.crowdsec_machine_password
        r = await self._request(
            "POST",
            "/v1/watchers/login",
            json={
                "machine_id": self.settings.crowdsec_machine_id,
                "password": pw.get_secret_value() if pw else "",
                "scenarios": [],
            },
        )
        if r.status_code in (401, 403):
            raise CollectorError("CrowdSec machine login failed – check machine id/password")
        if r.status_code >= 400:
            raise CollectorError(f"CrowdSec login error {r.status_code}")
        body = r.json()
        self._jwt = body["token"]
        exp = parse_rfc3339(body.get("expire"))
        self._jwt_exp = float(exp) if exp else time.time() + 600
        return self._jwt

    async def alerts(self, since_s: int, until_s: int | None) -> list[dict]:
        params = {"since": f"{max(since_s, 1)}s", "limit": ALERT_LIMIT, "include_capi": "false"}
        if until_s:
            params["until"] = f"{until_s}s"
        for attempt in range(2):
            token = await self._login()
            r = await self._request("GET", "/v1/alerts", headers={"Authorization": f"Bearer {token}"},
                                    params=params)
            if r.status_code == 401 and attempt == 0:
                self._jwt = None
                continue
            if r.status_code >= 400:
                raise CollectorError(f"CrowdSec LAPI error {r.status_code} on /v1/alerts")
            return r.json() or []
        raise CollectorError("CrowdSec authentication failed")

    async def metrics(self) -> str:
        url = self.settings.crowdsec_metrics_url
        try:
            r = await self._client.get(url)
        except httpx.HTTPError as exc:
            raise CollectorError(f"CrowdSec metrics not reachable: {type(exc).__name__}") from exc
        if r.status_code >= 400:
            raise CollectorError(f"CrowdSec metrics error {r.status_code}")
        return r.text

    async def aclose(self) -> None:
        await self._client.aclose()


# ---------------------------------------------------------------------------
def _target_host(alert: dict) -> str | None:
    for item in alert.get("meta") or []:
        if item.get("key") == "target_fqdn" and item.get("value"):
            return str(item["value"]).strip('[]"').split('","')[0].lower()
    for ev in alert.get("events") or []:
        for item in ev.get("meta") or []:
            if item.get("key") == "target_fqdn" and item.get("value"):
                return str(item["value"]).lower()
    return None


def severity_for(scenario: str, has_decision: bool, pattern: re.Pattern) -> str:
    """critical = exploit-type scenario that also led to a remediation (attacker was banned/challenged);
    high = exploit-type scenario without decision (e.g. AppSec virtual patch blocked one request) or any
    other scenario with a decision; low = detection without remediation."""
    dangerous = bool(pattern.search(scenario or ""))
    if dangerous and has_decision:
        return "critical"
    return "high" if dangerous or has_decision else "low"


def normalize_alert(a: dict, policy: IpPolicy, pattern: re.Pattern) -> dict | None:
    if a.get("id") is None:
        return None
    src = a.get("source") or {}
    decisions = a.get("decisions") or []
    scope = src.get("scope")
    value = src.get("value") or src.get("ip")
    if scope and scope.lower() == "ip":
        value = policy.display(value)
    elif scope and scope.lower() == "range":
        value = policy.display_range(value)
    d0 = decisions[0] if decisions else {}
    scenario = a.get("scenario") or "unknown"
    return {
        "id": int(a["id"]),
        "uuid": a.get("uuid"),
        "scenario": scenario[:255],
        "message": (a.get("message") or "")[:2000],
        "created_ts": parse_rfc3339(a.get("created_at")) or now_ts(),
        "start_ts": parse_rfc3339(a.get("start_at")),
        "stop_ts": parse_rfc3339(a.get("stop_at")),
        "events_count": int(a.get("events_count") or 0),
        "source_scope": scope,
        "source_value": value,
        "source_range": policy.display_range(src.get("range")),
        "country": (src.get("cn") or None),
        "as_name": (src.get("as_name") or None),
        "as_number": str(src.get("as_number") or "") or None,
        "target_host": _target_host(a),
        "simulated": bool(a.get("simulated")),
        "decisions_count": len(decisions),
        "decision_type": d0.get("type"),
        "decision_duration": d0.get("duration"),
        "machine_id": a.get("machine_id"),
        "severity": severity_for(scenario, bool(decisions), pattern),
    }


class CrowdsecAlertsCollector(Collector):
    name = "crowdsec_alerts"

    def __init__(self, db: Database, settings: Settings, client: LapiClient | None = None) -> None:
        super().__init__(db)
        self.settings = settings
        self.interval = settings.crowdsec_poll_seconds
        self.client = client or LapiClient(settings)
        self.policy = IpPolicy(settings.ip_mode, settings.ipv4_prefix, settings.ipv6_prefix,
                               settings.internal_networks)
        self.pattern = re.compile(settings.critical_scenario_pattern, re.IGNORECASE)
        self.new_alerts: list[dict] = []  # consumed by the notifier

    @property
    def enabled(self) -> bool:
        return self.settings.crowdsec_alerts_enabled

    async def run_once(self) -> int:
        state = await self.get_state()
        cursor = dict(state.cursor or {})
        now = now_ts()
        first_run = "last_ts" not in cursor
        start = int(cursor.get("last_ts") or (now - self.settings.crowdsec_backfill_hours * 3600)) - 120
        total = 0
        window_start = start
        while window_start < now:
            window_end = min(window_start + ALERT_WINDOW, now)
            total += await self._fetch_window(window_start, window_end, notify=not first_run)
            window_start = window_end
        cursor["last_ts"] = now
        await self.save_cursor(cursor)
        return total

    async def _fetch_window(self, start: int, end: int, notify: bool) -> int:
        now = now_ts()
        until = now - end if end < now else None
        alerts = await self.client.alerts(now - start, until)
        if len(alerts) >= ALERT_LIMIT and end - start > 600:
            mid = (start + end) // 2
            return await self._fetch_window(start, mid, notify) + await self._fetch_window(mid, end, notify)
        rows = [r for r in (normalize_alert(a, self.policy, self.pattern) for a in alerts) if r]
        if not rows:
            return 0
        async with self.db.session() as s:
            from ..database.session import existing_ids

            known = await existing_ids(s, CrowdsecAlert.id, [r["id"] for r in rows])
            new = [r for r in rows if r["id"] not in known]
            await upsert(s, CrowdsecAlert, new, ["id"])
            await s.commit()
        if notify:
            self.new_alerts.extend(new)
        return len(new)


class CrowdsecDecisionsCollector(Collector):
    name = "crowdsec_decisions"

    def __init__(self, db: Database, settings: Settings, client: LapiClient | None = None) -> None:
        super().__init__(db)
        self.settings = settings
        self.interval = max(settings.crowdsec_poll_seconds, 120)
        self.client = client or LapiClient(settings)
        self.policy = IpPolicy(settings.ip_mode, settings.ipv4_prefix, settings.ipv6_prefix,
                               settings.internal_networks)

    @property
    def enabled(self) -> bool:
        return self.settings.crowdsec_decisions_enabled

    async def run_once(self) -> int:
        now = now_ts()
        local_origins = set(self.settings.crowdsec_local_origins)
        counts: Counter = Counter()
        if self.settings.crowdsec_metrics_url:
            # community lists can hold tens of thousands of decisions: only fetch local ones and
            # take the totals from the cs_active_decisions metric
            decisions = await self.client.decisions(sorted(local_origins))
            try:
                metrics = parse_prometheus(await self.client.metrics())
                for (name, labels), value in metrics.items():
                    if name == "cs_active_decisions":
                        lab = dict(p.split("=", 1) for p in labels.split(","))
                        counts[(lab.get("origin") or "unknown", lab.get("action") or "unknown")] += int(value)
            except CollectorError:
                log.info("metrics unavailable, counting decisions from the full list")
                decisions = await self.client.decisions()
                counts.clear()
        else:
            decisions = await self.client.decisions()
        count_from_list = not counts
        local_rows = []
        for d in decisions:
            origin = d.get("origin") or "unknown"
            dtype = d.get("type") or "unknown"
            if count_from_list:
                counts[(origin, dtype)] += 1
            if origin in local_origins and d.get("id") is not None:
                scope = (d.get("scope") or "").lower()
                value = d.get("value") or ""
                if scope == "ip":
                    value = self.policy.display(value) or value
                elif scope == "range":
                    value = self.policy.display_range(value) or value
                dur = parse_go_duration(d.get("duration"))
                local_rows.append({
                    "id": int(d["id"]), "origin": origin, "type": dtype, "scope": d.get("scope") or "",
                    "value": value[:128], "scenario": (d.get("scenario") or "")[:255],
                    "expires_ts": int(now + dur) if dur is not None else None, "seen_ts": now,
                })
        async with self.db.session() as s:
            await s.execute(delete(CrowdsecDecision))
            await upsert(s, CrowdsecDecision, local_rows, ["id"])
            await upsert(
                s, DecisionCount,
                [{"ts": now, "origin": o, "type": t, "count": c} for (o, t), c in counts.items()],
                ["ts", "origin", "type"], replace=["count"],
            )
            await s.commit()
        return len(local_rows)


# ---------------------------------------------------------------------------
_METRIC_LINE = re.compile(r'^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{[^}]*\})?\s+([-+0-9.eE]+|NaN|\+Inf|-Inf)')
_LABEL = re.compile(r'(\w+)="((?:[^"\\]|\\.)*)"')

# metric name -> labels to keep (series are summed over the others)
TRACKED_METRICS: dict[str, tuple[str, ...]] = {
    "cs_active_decisions": ("origin", "action"),
    "cs_alerts": ("reason",),
    "cs_appsec_block_total": (),
    "cs_appsec_reqs_total": (),
    "cs_lapi_bouncer_requests_total": ("bouncer",),
    "cs_parser_hits_ok_total": (),
    "cs_parser_hits_ko_total": (),
    "cs_bucket_overflowed_total": (),
}


def parse_prometheus(text: str) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        m = _METRIC_LINE.match(line)
        if not m or m.group(1) not in TRACKED_METRICS:
            continue
        name = m.group(1)
        labels = dict(_LABEL.findall(m.group(2) or ""))
        keep = TRACKED_METRICS[name]
        key = ",".join(f"{k}={labels.get(k, '')}" for k in keep)
        try:
            val = float(m.group(3))
        except ValueError:
            continue
        out[(name, key)] = out.get((name, key), 0.0) + val
    return out


class CrowdsecMetricsCollector(Collector):
    name = "crowdsec_metrics"

    def __init__(self, db: Database, settings: Settings, client: LapiClient | None = None) -> None:
        super().__init__(db)
        self.settings = settings
        self.interval = 300
        self.client = client or LapiClient(settings)

    @property
    def enabled(self) -> bool:
        return bool(self.settings.crowdsec_metrics_url)

    async def run_once(self) -> int:
        text = await self.client.metrics()
        values = parse_prometheus(text)
        now = now_ts()
        rows = [{"ts": now, "name": n, "labels": lab, "value": v} for (n, lab), v in values.items()]
        async with self.db.session() as s:
            await upsert(s, MetricSample, rows, ["ts", "name", "labels"], replace=["value"])
            await s.commit()
        return 0  # samples are not "new items" for listeners
