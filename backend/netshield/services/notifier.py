"""Notification engine: evaluates thresholds and delivers via ntfy (plus SSE/HA/app polling).

Every notification is stored, so the Android app and Home Assistant can show the same
events. Repeats are suppressed per dedup key for a configurable cooldown.
"""

from __future__ import annotations

import logging

import httpx
from sqlalchemy import case, func, select

from ..collectors.base import Collector
from ..config import Settings
from ..database import Database
from ..database.models import (
    CAT_BLOCKED,
    CAT_CHALLENGED,
    CAT_INTERNAL,
    CollectorState,
    Notification,
    ProxyRequest,
)
from ..util import now_ts
from .events import EventBus
from .runtime_settings import RuntimeSettingsStore

log = logging.getLogger(__name__)

SEVERITY_RANK = {"low": 0, "high": 1, "critical": 2}
NTFY_PRIORITY = {"info": "default", "warning": "high", "critical": "urgent"}
NTFY_TAGS = {"info": "information_source", "warning": "warning", "critical": "rotating_light"}


class NtfyClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._client = httpx.AsyncClient(timeout=15.0, transport=transport)

    async def send(self, title: str, message: str, severity: str, click: str | None = None) -> bool:
        st = self.settings
        if not st.ntfy_enabled:
            return False
        headers = {
            "Title": title.encode("utf-8").decode("latin-1", "ignore"),
            "Priority": NTFY_PRIORITY.get(severity, "default"),
            "Tags": f"{NTFY_TAGS.get(severity, 'bell')},netshield",
        }
        if click:
            headers["Click"] = click
        if st.ntfy_token:
            headers["Authorization"] = f"Bearer {st.ntfy_token.get_secret_value()}"
        try:
            r = await self._client.post(f"{st.ntfy_url}/{st.ntfy_topic}", content=message.encode(), headers=headers)
            if r.status_code >= 400:
                log.warning("ntfy delivery failed: HTTP %s", r.status_code)
                return False
            return True
        except httpx.HTTPError as exc:
            log.warning("ntfy delivery failed: %s", type(exc).__name__)
            return False


class Notifier(Collector):
    name = "notifier"
    interval = 60

    def __init__(self, db: Database, settings: Settings, runtime: RuntimeSettingsStore, bus: EventBus,
                 alerts_collector=None, ntfy: NtfyClient | None = None) -> None:
        super().__init__(db)
        self.settings = settings
        self.runtime = runtime
        self.bus = bus
        self.alerts_collector = alerts_collector
        self.ntfy = ntfy or NtfyClient(settings)

    async def run_once(self) -> int:
        cfg = (await self.runtime.get()).notifications
        if not cfg.enabled:
            if self.alerts_collector:
                self.alerts_collector.new_alerts.clear()
            return 0
        sent = 0
        sent += await self._check_alerts(cfg)
        now = now_ts()
        async with self.db.session() as s:
            last5 = ProxyRequest.ts >= now - 300
            if cfg.request_spike:
                cur = int((await s.execute(select(func.count()).where(
                    last5, ProxyRequest.category != CAT_INTERNAL))).scalar() or 0)
                base_total = int((await s.execute(select(func.count()).where(
                    ProxyRequest.ts >= now - 3600 * 24, ProxyRequest.ts < now - 300,
                    ProxyRequest.category != CAT_INTERNAL))).scalar() or 0)
                baseline = base_total / ((86400 - 300) / 300)
                if cur >= cfg.request_spike_min_per_5min and cur > baseline * cfg.request_spike_factor:
                    sent += await self.emit("request_spike", "warning", "Ungewöhnlich viele Requests",
                                            f"{cur} Requests in 5 Minuten (Ø {baseline:.0f})", "request_spike", cfg)
            if cfg.attack_spike:
                blocked = int((await s.execute(select(func.count()).where(
                    last5, ProxyRequest.category.in_([CAT_BLOCKED, CAT_CHALLENGED])))).scalar() or 0)
                if blocked >= cfg.attack_spike_min_per_5min:
                    sent += await self.emit("attack_spike", "critical", "Angriffsspitze erkannt",
                                            f"{blocked} Requests in 5 Minuten durch CrowdSec abgewiesen",
                                            "attack_spike", cfg)
            if cfg.domain_outage:
                rows = (await s.execute(
                    select(ProxyRequest.host, func.count(),
                           func.sum(case((ProxyRequest.status.in_([502, 503, 504]), 1), else_=0)))
                    .where(last5, ProxyRequest.category.not_in([CAT_BLOCKED, CAT_CHALLENGED]))
                    .group_by(ProxyRequest.host))).all()
                for host, n, bad in rows:
                    bad = int(bad or 0)
                    if n >= cfg.domain_outage_min_requests and bad / n >= cfg.domain_outage_error_ratio:
                        sent += await self.emit("domain_outage", "critical", f"Domain gestört: {host}",
                                                f"{bad} von {n} Requests mit 502/503/504 in 5 Minuten",
                                                f"domain_outage:{host}", cfg, host=host)
            if cfg.scanner_pattern:
                rows = (await s.execute(
                    select(ProxyRequest.ip, func.count()).where(
                        last5, ProxyRequest.status == 404, ProxyRequest.category != CAT_INTERNAL,
                        ProxyRequest.ip.is_not(None))
                    .group_by(ProxyRequest.ip).having(func.count() >= cfg.scanner_404_per_source_5min))).all()
                for ip, n in rows:
                    sent += await self.emit("scanner", "warning", "Auffälliges Zugriffsmuster",
                                            f"{ip}: {n}× 404 in 5 Minuten (vermutlich Scanner)",
                                            f"scanner:{ip}", cfg)
            if cfg.source_errors:
                for c in (await s.execute(select(CollectorState).where(CollectorState.status == "error"))).scalars():
                    if c.name in ("notifier",):
                        continue
                    since = now - (c.last_success_ts or 0)
                    if since >= cfg.source_error_minutes * 60:
                        sent += await self.emit("source_error", "warning", f"Datenquelle gestört: {c.name}",
                                                (c.last_error or "")[:300], f"source:{c.name}", cfg)
        return sent

    async def _check_alerts(self, cfg) -> int:
        if not self.alerts_collector or not cfg.critical_alerts:
            if self.alerts_collector:
                self.alerts_collector.new_alerts.clear()
            return 0
        pending, self.alerts_collector.new_alerts = self.alerts_collector.new_alerts, []
        min_rank = SEVERITY_RANK[cfg.min_alert_severity]
        grouped: dict[str, list[dict]] = {}
        for a in pending:
            if a.get("simulated") or SEVERITY_RANK.get(a["severity"], 0) < min_rank:
                continue
            grouped.setdefault(a["scenario"], []).append(a)
        sent = 0
        for scenario, items in grouped.items():
            first = items[0]
            where = f" auf {first['target_host']}" if first.get("target_host") else ""
            src = first.get("source_value") or "?"
            more = f" (+{len(items) - 1} weitere)" if len(items) > 1 else ""
            sev = "critical" if first["severity"] == "critical" else "warning"
            sent += await self.emit("crowdsec_alert", sev, f"CrowdSec: {scenario}",
                                    f"Quelle {src} ({first.get('country') or '??'}){where}{more}",
                                    f"alert:{scenario}", cfg, host=first.get("target_host"))
        return sent

    async def emit(self, kind: str, severity: str, title: str, message: str, dedup_key: str, cfg,
                   host: str | None = None) -> int:
        now = now_ts()
        async with self.db.session() as s:
            recent = (await s.execute(select(func.count()).where(
                Notification.dedup_key == dedup_key, Notification.ts >= now - cfg.cooldown_minutes * 60))).scalar()
            if recent:
                return 0
            n = Notification(ts=now, kind=kind, severity=severity, title=title, message=message, host=host,
                             dedup_key=dedup_key)
            s.add(n)
            await s.commit()
            await s.refresh(n)
            delivered = await self.ntfy.send(title, message, severity)
            if delivered:
                n.delivered_ntfy = True
                await s.commit()
        await self.bus.publish("notification", {"id": n.id, "ts": n.ts, "kind": kind, "severity": severity,
                                                "title": title, "message": message, "host": host})
        return 1
