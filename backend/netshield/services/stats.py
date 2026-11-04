"""Statistics queries shared by the web UI, Android app and Home Assistant.

Short ranges (<= 48 h, within raw retention) are answered from raw request rows with
minute precision; longer ranges from the hourly aggregates. Every number returned here
is computed from stored source data – nothing is extrapolated or invented.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..database.models import (
    CAT_BLOCKED,
    CAT_CHALLENGED,
    CAT_INTERNAL,
    CAT_SUSPICIOUS,
    CAT_VISITOR,
    CATEGORIES,
    CollectorState,
    CrowdsecAlert,
    CrowdsecDecision,
    DailyVisitors,
    DecisionCount,
    Domain,
    HourlyStat,
    MetricSample,
    ProxyRequest,
)
from ..util import local_day, now_ts, start_of_local_day

RANGES = {"live": 15 * 60, "1h": 3600, "24h": 86400, "7d": 7 * 86400, "30d": 30 * 86400}
MAX_CUSTOM_RANGE = 366 * 86400


class RangeError(ValueError):
    pass


@dataclass
class TimeRange:
    start: int
    end: int
    label: str

    @property
    def seconds(self) -> int:
        return self.end - self.start


def resolve_range(name: str | None, start: int | None, end: int | None) -> TimeRange:
    now = now_ts()
    if start is not None or end is not None or name == "custom":
        if start is None:
            raise RangeError("custom range requires 'from'")
        end = end or now
        if end <= start:
            raise RangeError("'to' must be after 'from'")
        if end - start > MAX_CUSTOM_RANGE:
            raise RangeError("range too large (max 366 days)")
        return TimeRange(start, min(end, now), "custom")
    name = name or "24h"
    if name not in RANGES:
        raise RangeError(f"unknown range '{name}'")
    return TimeRange(now - RANGES[name], now, name)


def pick_bucket(seconds: int) -> int:
    if seconds <= 3 * 3600:
        return 60
    if seconds <= 48 * 3600:
        return 900 if seconds > 12 * 3600 else 300
    if seconds <= 8 * 86400:
        return 3600
    return 86400


class Stats:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # --- helpers ---------------------------------------------------------------
    def use_raw(self, tr: TimeRange) -> bool:
        raw_from = now_ts() - self.settings.raw_retention_days * 86400 + 3600
        return tr.start >= raw_from and tr.seconds <= 48 * 3600

    def _tz_offset(self) -> int:
        off = datetime.now(ZoneInfo(self.settings.timezone)).utcoffset()
        return int(off.total_seconds()) if off else 0

    @staticmethod
    def _raw_where(tr: TimeRange, host: str | None):
        cond = [ProxyRequest.ts >= tr.start, ProxyRequest.ts < tr.end]
        if host:
            cond.append(ProxyRequest.host == host)
        return and_(*cond)

    @staticmethod
    def _agg_where(tr: TimeRange, host: str | None):
        cond = [HourlyStat.hour >= tr.start - tr.start % 3600, HourlyStat.hour < tr.end]
        if host:
            cond.append(HourlyStat.host == host)
        return and_(*cond)

    # --- request totals ----------------------------------------------------------
    async def category_totals(self, s: AsyncSession, tr: TimeRange, host: str | None = None) -> dict:
        if self.use_raw(tr):
            q = (
                select(ProxyRequest.category, func.count(),
                       func.sum(case((ProxyRequest.observe_only, 1), else_=0)),
                       func.coalesce(func.sum(ProxyRequest.bytes_down), 0))
                .where(self._raw_where(tr, host))
                .group_by(ProxyRequest.category)
            )
        else:
            q = (
                select(HourlyStat.category, func.sum(HourlyStat.count), func.sum(HourlyStat.observe_hits),
                       func.coalesce(func.sum(HourlyStat.bytes_down), 0))
                .where(self._agg_where(tr, host))
                .group_by(HourlyStat.category)
            )
        out = {c: 0 for c in CATEGORIES}
        would_block = 0
        bytes_down = 0
        for cat, cnt, obs, b in (await s.execute(q)).all():
            out[cat] = int(cnt or 0)
            would_block += int(obs or 0)
            bytes_down += int(b or 0)
        total = sum(out.values())
        return {
            "requests": total,
            "external_requests": total - out[CAT_INTERNAL],
            "by_category": out,
            "blocked": out[CAT_BLOCKED],
            "challenged": out[CAT_CHALLENGED],
            "suspicious": out[CAT_SUSPICIOUS],
            "internal": out[CAT_INTERNAL],
            "would_block_observe": would_block,
            "bytes_down": bytes_down,
        }

    async def visitors(self, s: AsyncSession, tr: TimeRange, host: str | None = None) -> dict:
        """Estimated unique visitors (distinct pseudonymised IPs of non-suspicious external requests).

        Within one local day the count is exact distinct; over several days the daily counts
        are summed ("visitor-days"), because pseudonyms rotate daily for privacy.
        """
        tz = self.settings.timezone
        same_day = local_day(tr.start, tz) == local_day(max(tr.end - 1, tr.start), tz)
        if same_day and self.use_raw(tr):
            q = select(func.count(distinct(ProxyRequest.visitor_hash))).where(
                self._raw_where(tr, host), ProxyRequest.category == CAT_VISITOR
            )
            return {"value": int((await s.execute(q)).scalar() or 0), "method": "distinct_daily_pseudonyms"}
        first = local_day(tr.start, tz)
        last = local_day(max(tr.end - 1, tr.start), tz)
        q = select(func.coalesce(func.sum(DailyVisitors.visitors), 0)).where(
            DailyVisitors.day >= first, DailyVisitors.day <= last, DailyVisitors.host == (host or "*")
        )
        return {"value": int((await s.execute(q)).scalar() or 0), "method": "sum_of_daily_visitors"}

    async def timeseries(self, s: AsyncSession, tr: TimeRange, host: str | None = None,
                         bucket: int | None = None) -> dict:
        bucket = bucket or pick_bucket(tr.seconds)
        off = 0
        if self.use_raw(tr):
            bucket = max(bucket, 60)
            b = (ProxyRequest.ts - (ProxyRequest.ts % bucket)).label("b")
            q = (select(b, ProxyRequest.category, func.count())
                 .where(self._raw_where(tr, host)).group_by(b, ProxyRequest.category))
        else:
            bucket = max(bucket, 3600)
            off = self._tz_offset() if bucket >= 86400 else 0
            b = (HourlyStat.hour - ((HourlyStat.hour + off) % bucket)).label("b")
            q = (select(b, HourlyStat.category, func.sum(HourlyStat.count))
                 .where(self._agg_where(tr, host)).group_by(b, HourlyStat.category))
        rows = (await s.execute(q)).all()
        series: dict[int, dict[str, int]] = {}
        for bts, cat, cnt in rows:
            series.setdefault(int(bts), {c: 0 for c in CATEGORIES})[cat] = int(cnt or 0)
        # fill gaps with zeros so charts don't interpolate missing data as traffic
        start = tr.start - ((tr.start + off) % bucket)
        points = []
        t = start
        while t < tr.end:
            vals = series.get(t, {c: 0 for c in CATEGORIES})
            points.append({"ts": t, **vals, "total": sum(vals.values())})
            t += bucket
            if len(points) > 5000:
                break
        return {"bucket_seconds": bucket, "source": "raw" if self.use_raw(tr) else "hourly", "points": points}

    async def countries(self, s: AsyncSession, tr: TimeRange, host: str | None = None,
                        include_internal: bool = False) -> list[dict]:
        if self.use_raw(tr):
            country = func.coalesce(ProxyRequest.country, "--")
            blocked = func.sum(case((ProxyRequest.category.in_([CAT_BLOCKED, CAT_CHALLENGED]), 1), else_=0))
            q = select(country, func.count(), blocked).where(self._raw_where(tr, host))
            if not include_internal:
                q = q.where(ProxyRequest.category != CAT_INTERNAL)
            q = q.group_by(country)
        else:
            blocked = func.sum(case((HourlyStat.category.in_([CAT_BLOCKED, CAT_CHALLENGED]), HourlyStat.count),
                                    else_=0))
            q = select(HourlyStat.country, func.sum(HourlyStat.count), blocked).where(self._agg_where(tr, host))
            if not include_internal:
                q = q.where(HourlyStat.category != CAT_INTERNAL)
            q = q.group_by(HourlyStat.country)
        out = [
            {"country": c if c != "--" else None, "requests": int(n or 0), "blocked": int(bl or 0),
             "allowed": int(n or 0) - int(bl or 0)}
            for c, n, bl in (await s.execute(q)).all()
        ]
        out.sort(key=lambda x: x["requests"], reverse=True)
        return out

    async def statuses(self, s: AsyncSession, tr: TimeRange, host: str | None = None) -> list[dict]:
        if self.use_raw(tr):
            q = (select(ProxyRequest.status, func.count()).where(self._raw_where(tr, host))
                 .group_by(ProxyRequest.status))
        else:
            q = (select(HourlyStat.status, func.sum(HourlyStat.count)).where(self._agg_where(tr, host))
                 .group_by(HourlyStat.status))
        out = [{"status": int(st), "count": int(n or 0)} for st, n in (await s.execute(q)).all()]
        out.sort(key=lambda x: x["count"], reverse=True)
        return out

    def _clip_raw(self, tr: TimeRange) -> tuple[TimeRange, bool]:
        raw_from = now_ts() - self.settings.raw_retention_days * 86400
        if tr.start < raw_from:
            return TimeRange(raw_from, tr.end, tr.label), True
        return tr, False

    async def top_paths(self, s: AsyncSession, tr: TimeRange, host: str | None = None, limit: int = 20,
                        category: str | None = None) -> dict:
        tr2, clipped = self._clip_raw(tr)
        blocked = func.sum(case((ProxyRequest.category.in_([CAT_BLOCKED, CAT_CHALLENGED]), 1), else_=0))
        errors = func.sum(case((ProxyRequest.status >= 400, 1), else_=0))
        q = select(ProxyRequest.host, ProxyRequest.path, func.count().label("n"), blocked, errors).where(
            self._raw_where(tr2, host))
        if category:
            q = q.where(ProxyRequest.category == category)
        q = q.group_by(ProxyRequest.host, ProxyRequest.path).order_by(func.count().desc()).limit(limit)
        items = [{"host": h, "path": p, "requests": int(n), "blocked": int(b or 0), "errors": int(e or 0)}
                 for h, p, n, b, e in (await s.execute(q)).all()]
        return {"items": items, "clipped_to_raw_retention": clipped}

    async def top_sources(self, s: AsyncSession, tr: TimeRange, host: str | None = None,
                          limit: int = 20) -> dict:
        tr2, clipped = self._clip_raw(tr)
        blocked = func.sum(case((ProxyRequest.category.in_([CAT_BLOCKED, CAT_CHALLENGED]), 1), else_=0))
        susp = func.sum(case((ProxyRequest.category == CAT_SUSPICIOUS, 1), else_=0))
        q = (select(ProxyRequest.ip, func.max(ProxyRequest.country), func.count(), blocked, susp,
                    func.count(distinct(ProxyRequest.host)), func.max(ProxyRequest.ts))
             .where(self._raw_where(tr2, host), ProxyRequest.category != CAT_INTERNAL,
                    ProxyRequest.ip.is_not(None))
             .group_by(ProxyRequest.ip).order_by(func.count().desc()).limit(limit))
        items = [{"ip": ip, "country": c, "requests": int(n), "blocked": int(b or 0), "suspicious": int(sp or 0),
                  "domains": int(d), "last_seen": int(ls)}
                 for ip, c, n, b, sp, d, ls in (await s.execute(q)).all()]
        return {"items": items, "clipped_to_raw_retention": clipped,
                "ip_mode": self.settings.ip_mode,
                "prefix": None if self.settings.ip_mode == "full" else
                {"ipv4": self.settings.ipv4_prefix, "ipv6": self.settings.ipv6_prefix}}

    async def recent_requests(self, s: AsyncSession, *, host: str | None, category: str | None,
                              status: int | None, before_ts: int | None, limit: int) -> list[dict]:
        q = select(ProxyRequest)
        if host:
            q = q.where(ProxyRequest.host == host)
        if category:
            q = q.where(ProxyRequest.category == category)
        if status:
            q = q.where(ProxyRequest.status == status)
        if before_ts:
            q = q.where(ProxyRequest.ts < before_ts)
        q = q.order_by(ProxyRequest.ts.desc(), ProxyRequest.id.desc()).limit(limit)
        return [
            {"id": r.id, "ts": r.ts, "host": r.host, "method": r.method, "path": r.path, "status": r.status,
             "duration_ms": r.duration_ms, "bytes_down": r.bytes_down, "ip": r.ip, "country": r.country,
             "city": r.city, "category": r.category, "verdict": r.verdict, "observe_only": r.observe_only,
             "authenticated": r.authenticated, "protocol": r.protocol}
            for r in (await s.execute(q)).scalars()
        ]

    async def requests_per_minute(self, s: AsyncSession, host: str | None = None, minutes: int = 5) -> float:
        now = now_ts()
        q = select(func.count()).where(self._raw_where(TimeRange(now - minutes * 60, now, "rpm"), host))
        return round(int((await s.execute(q)).scalar() or 0) / minutes, 2)

    # --- domains --------------------------------------------------------------------
    async def domains(self, s: AsyncSession, tr: TimeRange, include_hidden: bool = False) -> list[dict]:
        doms = {d.host: d for d in (await s.execute(select(Domain))).scalars()}
        if self.use_raw(tr):
            q = (select(ProxyRequest.host, ProxyRequest.category, func.count())
                 .where(self._raw_where(tr, None)).group_by(ProxyRequest.host, ProxyRequest.category))
        else:
            q = (select(HourlyStat.host, HourlyStat.category, func.sum(HourlyStat.count))
                 .where(self._agg_where(tr, None)).group_by(HourlyStat.host, HourlyStat.category))
        per: dict[str, dict[str, int]] = {}
        for h, cat, n in (await s.execute(q)).all():
            per.setdefault(h, {c: 0 for c in CATEGORIES})[cat] = int(n or 0)
        now = now_ts()
        rpm_q = (select(ProxyRequest.host, func.count()).where(ProxyRequest.ts >= now - 300)
                 .group_by(ProxyRequest.host))
        rpm = {h: round(n / 5, 2) for h, n in (await s.execute(rpm_q)).all()}
        out = []
        for host in sorted(set(doms) | set(per)):
            d = doms.get(host)
            if d and d.hidden and not include_hidden:
                continue
            cats = per.get(host, {c: 0 for c in CATEGORIES})
            out.append({
                "host": host,
                "display_name": d.display_name if d else None,
                "source": d.source if d else "logs",
                "enabled": d.enabled if d else True,
                "hidden": d.hidden if d else False,
                "removed_upstream": d.removed_upstream if d else False,
                "crowdsec_mode": d.crowdsec_mode if d else None,
                "auth_enabled": d.auth_enabled if d else False,
                "last_seen": d.last_seen if d else None,
                "requests": sum(cats.values()),
                "blocked": cats[CAT_BLOCKED] + cats[CAT_CHALLENGED],
                "suspicious": cats[CAT_SUSPICIOUS],
                "internal": cats[CAT_INTERNAL],
                "requests_per_minute": rpm.get(host, 0.0),
            })
        out.sort(key=lambda x: x["requests"], reverse=True)
        return out

    # --- crowdsec ---------------------------------------------------------------------
    async def alert_summary(self, s: AsyncSession, tr: TimeRange, host: str | None = None) -> dict:
        cond = [CrowdsecAlert.created_ts >= tr.start, CrowdsecAlert.created_ts < tr.end]
        if host:
            cond.append(CrowdsecAlert.target_host == host)
        where = and_(*cond)
        total = int((await s.execute(select(func.count()).where(where))).scalar() or 0)
        sev = dict((await s.execute(select(CrowdsecAlert.severity, func.count()).where(where)
                                    .group_by(CrowdsecAlert.severity))).all())
        scen = (await s.execute(select(CrowdsecAlert.scenario, func.count()).where(where)
                                .group_by(CrowdsecAlert.scenario).order_by(func.count().desc()).limit(15))).all()
        ctry = (await s.execute(select(CrowdsecAlert.country, func.count()).where(where)
                                .group_by(CrowdsecAlert.country).order_by(func.count().desc()).limit(30))).all()
        with_dec = int((await s.execute(select(func.count()).where(where, CrowdsecAlert.decisions_count > 0)))
                       .scalar() or 0)
        bucket = pick_bucket(tr.seconds)
        bucket = max(bucket, 300)
        b = (CrowdsecAlert.created_ts - (CrowdsecAlert.created_ts % bucket)).label("b")
        ts_rows = dict((await s.execute(select(b, func.count()).where(where).group_by(b))).all())
        start = tr.start - tr.start % bucket
        points = []
        t = start
        while t < tr.end and len(points) < 5000:
            points.append({"ts": t, "alerts": int(ts_rows.get(t, 0))})
            t += bucket
        return {
            "alerts": total,
            "alerts_with_decision": with_dec,
            "by_severity": {k: int(sev.get(k, 0)) for k in ("critical", "high", "low")},
            "top_scenarios": [{"scenario": sc, "count": int(n)} for sc, n in scen],
            "countries": [{"country": c, "count": int(n)} for c, n in ctry],
            "timeseries": {"bucket_seconds": bucket, "points": points},
        }

    async def alerts(self, s: AsyncSession, *, tr: TimeRange, host: str | None, scenario: str | None,
                     severity: str | None, before_id: int | None, limit: int) -> list[dict]:
        q = select(CrowdsecAlert).where(CrowdsecAlert.created_ts >= tr.start, CrowdsecAlert.created_ts < tr.end)
        if host:
            q = q.where(CrowdsecAlert.target_host == host)
        if scenario:
            q = q.where(CrowdsecAlert.scenario == scenario)
        if severity:
            q = q.where(CrowdsecAlert.severity == severity)
        if before_id:
            q = q.where(CrowdsecAlert.id < before_id)
        q = q.order_by(CrowdsecAlert.id.desc()).limit(limit)
        return [
            {"id": a.id, "scenario": a.scenario, "message": a.message, "created": a.created_ts,
             "start": a.start_ts, "stop": a.stop_ts, "events": a.events_count, "scope": a.source_scope,
             "source": a.source_value, "range": a.source_range, "country": a.country, "as_name": a.as_name,
             "target_host": a.target_host, "simulated": a.simulated, "decisions": a.decisions_count,
             "decision_type": a.decision_type, "decision_duration": a.decision_duration,
             "severity": a.severity}
            for a in (await s.execute(q)).scalars()
        ]

    async def decisions(self, s: AsyncSession) -> dict:
        latest = (await s.execute(select(func.max(DecisionCount.ts)))).scalar()
        counts = []
        if latest:
            counts = [{"origin": o, "type": t, "count": int(c)} for o, t, c in (await s.execute(
                select(DecisionCount.origin, DecisionCount.type, DecisionCount.count)
                .where(DecisionCount.ts == latest))).all()]
        local = set(self.settings.crowdsec_local_origins)
        now = now_ts()
        active = [
            {"id": d.id, "origin": d.origin, "type": d.type, "scope": d.scope, "value": d.value,
             "scenario": d.scenario, "expires": d.expires_ts,
             "remaining_seconds": max(0, d.expires_ts - now) if d.expires_ts else None}
            for d in (await s.execute(select(CrowdsecDecision).order_by(CrowdsecDecision.expires_ts.desc())))
            .scalars()
        ]
        return {
            "snapshot_ts": latest,
            "local_active": sum(c["count"] for c in counts if c["origin"] in local),
            "community_active": sum(c["count"] for c in counts if c["origin"] not in local),
            "by_origin": counts,
            "local_decisions": active,
        }

    async def decision_history(self, s: AsyncSession, tr: TimeRange) -> list[dict]:
        local = list(self.settings.crowdsec_local_origins)
        is_local = DecisionCount.origin.in_(local)
        q = (select(DecisionCount.ts,
                    func.sum(case((is_local, DecisionCount.count), else_=0)),
                    func.sum(case((is_local, 0), else_=DecisionCount.count)))
             .where(DecisionCount.ts >= tr.start, DecisionCount.ts < tr.end)
             .group_by(DecisionCount.ts).order_by(DecisionCount.ts))
        rows = (await s.execute(q)).all()
        step = max(1, len(rows) // 300)
        return [{"ts": int(t), "local": int(lo or 0), "community": int(co or 0)} for t, lo, co in rows[::step]]

    async def metrics_latest(self, s: AsyncSession) -> dict:
        latest = (await s.execute(select(func.max(MetricSample.ts)))).scalar()
        if not latest:
            return {"ts": None, "values": []}
        rows = (await s.execute(select(MetricSample.name, MetricSample.labels, MetricSample.value)
                                .where(MetricSample.ts == latest))).all()
        return {"ts": latest, "values": [{"name": n, "labels": lab, "value": v} for n, lab, v in rows]}

    async def blocked_by_enforcer(self, s: AsyncSession, tr: TimeRange) -> dict:
        """Enforcement evidence by layer. Only the NetBird proxy reports individual requests."""
        totals = await self.category_totals(s, tr)
        appsec = await self._metric_delta(s, "cs_appsec_block_total", tr)
        return {
            "netbird_proxy": {"blocked": totals["blocked"], "challenged": totals["challenged"],
                              "would_block_observe": totals["would_block_observe"],
                              "evidence": "per-request access log"},
            "crowdsec_appsec": {"blocked": appsec, "evidence": "prometheus counter (delta)"},
            "firewall_bouncer": {"blocked": None,
                                 "evidence": "not available – firewall drops packets before any request"},
        }

    async def _metric_delta(self, s: AsyncSession, name: str, tr: TimeRange) -> int | None:
        q = (select(MetricSample.ts, func.sum(MetricSample.value)).where(
            MetricSample.name == name, MetricSample.ts >= tr.start, MetricSample.ts < tr.end)
            .group_by(MetricSample.ts).order_by(MetricSample.ts))
        rows = (await s.execute(q)).all()
        if len(rows) < 2:
            return None
        delta = 0.0
        prev = rows[0][1]
        for _, v in rows[1:]:
            delta += v - prev if v >= prev else v  # counter reset after restart
            prev = v
        return int(delta)

    # --- sources / status ---------------------------------------------------------------
    async def sources(self, s: AsyncSession) -> list[dict]:
        return [
            {"name": c.name, "status": c.status, "last_success": c.last_success_ts, "last_error": c.last_error,
             "last_error_ts": c.last_error_ts, "items_total": c.items_total}
            for c in (await s.execute(select(CollectorState).order_by(CollectorState.name))).scalars()
        ]

    async def security_status(self, s: AsyncSession) -> dict:
        now = now_ts()
        hour = TimeRange(now - 3600, now, "1h")
        reasons = []
        crit = int((await s.execute(select(func.count()).where(
            CrowdsecAlert.created_ts >= hour.start, CrowdsecAlert.severity == "critical"))).scalar() or 0)
        high = int((await s.execute(select(func.count()).where(
            CrowdsecAlert.created_ts >= hour.start, CrowdsecAlert.severity == "high"))).scalar() or 0)
        errors = [c for c in await self.sources(s) if c["status"] == "error"]
        level = "ok"
        if crit:
            level = "critical"
            reasons.append({"code": "critical_alerts_1h", "value": crit})
        if high:
            level = "warning" if level == "ok" else level
            reasons.append({"code": "alerts_with_decision_1h", "value": high})
        if errors:
            level = "warning" if level == "ok" else level
            reasons.append({"code": "source_errors", "value": [e["name"] for e in errors]})
        return {"level": level, "reasons": reasons}

    async def overview(self, s: AsyncSession, tr: TimeRange, host: str | None = None) -> dict:
        now = now_ts()
        tz = self.settings.timezone
        today = TimeRange(start_of_local_day(now, tz), now, "today")
        last24 = TimeRange(now - 86400, now, "24h")
        totals = await self.category_totals(s, tr, host)
        today_totals = await self.category_totals(s, today, host)
        totals_24 = await self.category_totals(s, last24, host)
        alerts_24 = await self.alert_summary(s, last24, host)
        alerts_range = await self.alert_summary(s, tr, host)
        countries = await self.countries(s, tr, host)
        doms = await self.domains(s, tr)
        decisions = await self.decisions(s)
        return {
            "range": {"start": tr.start, "end": tr.end, "label": tr.label},
            "requests": totals,
            "requests_today": today_totals["requests"],
            "requests_24h": totals_24["requests"],
            "blocked_24h": totals_24["blocked"] + totals_24["challenged"],
            "visitors": await self.visitors(s, tr, host),
            "visitors_today": await self.visitors(s, today, host),
            "active_domains": sum(1 for d in doms if d["requests"] > 0 and (not host or d["host"] == host)),
            "known_domains": len(doms),
            "requests_per_minute": await self.requests_per_minute(s, host),
            "crowdsec": {
                "alerts": alerts_range["alerts"],
                "alerts_24h": alerts_24["alerts"],
                "critical_alerts_24h": alerts_24["by_severity"]["critical"],
                "local_active_decisions": decisions["local_active"],
                "community_active_decisions": decisions["community_active"],
            },
            "top_countries": countries[:10],
            "security_status": await self.security_status(s),
        }

