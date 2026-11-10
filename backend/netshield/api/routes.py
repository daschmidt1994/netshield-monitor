"""Read-only API used by the web UI, the Android app and Home Assistant."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select

from .. import __version__
from ..database.models import CATEGORIES, Domain, Notification
from ..security.auth import Principal, require_read
from ..services.stats import TimeRange
from ..util import now_ts
from .deps import HOST_PATTERN, app_state, get_range, host_param

router = APIRouter(prefix="/api/v1")
CategoryQ = Query(None, pattern="^(" + "|".join(CATEGORIES) + ")$")


@router.get("/health", tags=["system"])
async def health(request: Request):
    """Unauthenticated liveness check (no internal details)."""
    try:
        async with request.app.state.db.session() as s:
            await s.execute(select(1))
        db_ok = True
    except Exception:
        db_ok = False
    # A started collector whose loop task has ended no longer collects anything. Answer 503 so
    # the container healthcheck turns unhealthy instead of hiding a dead collector for days.
    collectors_ok = all(
        c.alive for c in getattr(request.app.state, "collectors", []) if getattr(c, "_task", None) is not None
    )
    body = {"status": "ok" if db_ok and collectors_ok else "degraded", "version": __version__, "time": now_ts()}
    if not collectors_ok:
        return JSONResponse(body, status_code=503)
    return body


@router.get("/sources", tags=["system"])
async def sources(st=Depends(app_state), _: Principal = Depends(require_read)):
    """Collector status per data source. Errors are user-facing messages without secrets."""
    cfg = st.settings
    async with st.db.session() as s:
        states = {x["name"]: x for x in await st.stats.sources(s)}
    configured = {
        "netbird_access_logs": cfg.netbird_enabled,
        "netbird_services": cfg.netbird_enabled,
        "crowdsec_alerts": cfg.crowdsec_alerts_enabled,
        "crowdsec_decisions": cfg.crowdsec_decisions_enabled,
        "crowdsec_metrics": bool(cfg.crowdsec_metrics_url),
        "ntfy": cfg.ntfy_enabled,
    }
    return {
        "sources": [{"name": n, "configured": c, **{k: v for k, v in states.get(n, {}).items() if k != "name"}}
                    for n, c in configured.items()],
        "privacy": {"ip_mode": cfg.ip_mode, "ipv4_prefix": cfg.ipv4_prefix, "ipv6_prefix": cfg.ipv6_prefix,
                    "raw_retention_days": cfg.raw_retention_days,
                    "aggregate_retention_days": cfg.aggregate_retention_days},
        "timezone": cfg.timezone,
        "version": __version__,
    }


@router.get("/overview", tags=["stats"])
async def overview(tr: TimeRange = Depends(get_range), host: str | None = Depends(host_param),
                   st=Depends(app_state), _: Principal = Depends(require_read)):
    async with st.db.session() as s:
        return await st.stats.overview(s, tr, host)


@router.get("/timeseries", tags=["stats"])
async def timeseries(tr: TimeRange = Depends(get_range), host: str | None = Depends(host_param),
                     bucket: int | None = Query(None, ge=60, le=86400),
                     st=Depends(app_state), _: Principal = Depends(require_read)):
    async with st.db.session() as s:
        return await st.stats.timeseries(s, tr, host, bucket)


@router.get("/countries", tags=["stats"])
async def countries(tr: TimeRange = Depends(get_range), host: str | None = Depends(host_param),
                    st=Depends(app_state), _: Principal = Depends(require_read)):
    async with st.db.session() as s:
        items = await st.stats.countries(s, tr, host)
    return {"items": items, "note": "GeoIP locations are approximate and not necessarily a person's location"}


@router.get("/statuses", tags=["stats"])
async def statuses(tr: TimeRange = Depends(get_range), host: str | None = Depends(host_param),
                   st=Depends(app_state), _: Principal = Depends(require_read)):
    async with st.db.session() as s:
        return {"items": await st.stats.statuses(s, tr, host)}


@router.get("/top/paths", tags=["stats"])
async def top_paths(tr: TimeRange = Depends(get_range), host: str | None = Depends(host_param),
                    category: str | None = CategoryQ, limit: int = Query(20, ge=1, le=200),
                    st=Depends(app_state), _: Principal = Depends(require_read)):
    async with st.db.session() as s:
        return await st.stats.top_paths(s, tr, host, limit, category)


@router.get("/top/sources", tags=["stats"])
async def top_sources(tr: TimeRange = Depends(get_range), host: str | None = Depends(host_param),
                      limit: int = Query(20, ge=1, le=200),
                      st=Depends(app_state), _: Principal = Depends(require_read)):
    async with st.db.session() as s:
        return await st.stats.top_sources(s, tr, host, limit)


@router.get("/requests", tags=["stats"])
async def recent_requests(host: str | None = Depends(host_param), category: str | None = CategoryQ,
                          status: int | None = Query(None, ge=100, le=599),
                          before: int | None = Query(None, ge=0, description="Return entries older than ts"),
                          limit: int = Query(50, ge=1, le=500),
                          st=Depends(app_state), _: Principal = Depends(require_read)):
    async with st.db.session() as s:
        items = await st.stats.recent_requests(s, host=host, category=category, status=status,
                                               before_ts=before, limit=limit)
    return {"items": items}


@router.get("/domains", tags=["domains"])
async def domains(tr: TimeRange = Depends(get_range), include_hidden: bool = False,
                  st=Depends(app_state), _: Principal = Depends(require_read)):
    async with st.db.session() as s:
        return {"items": await st.stats.domains(s, tr, include_hidden)}


@router.get("/domains/{host}", tags=["domains"])
async def domain_detail(host: str, tr: TimeRange = Depends(get_range),
                        st=Depends(app_state), _: Principal = Depends(require_read)):
    import re

    host = host.lower()
    if not re.match(HOST_PATTERN, host):
        raise HTTPException(422, "invalid host")
    async with st.db.session() as s:
        d = await s.get(Domain, host)
        stats = st.stats
        totals = await stats.category_totals(s, tr, host)
        if d is None and totals["requests"] == 0:
            raise HTTPException(404, "unknown domain")
        return {
            "host": host,
            "info": None if d is None else {
                "source": d.source, "display_name": d.display_name, "enabled": d.enabled,
                "crowdsec_mode": d.crowdsec_mode, "auth_enabled": d.auth_enabled, "hidden": d.hidden,
                "first_seen": d.first_seen, "last_seen": d.last_seen, "removed_upstream": d.removed_upstream},
            "range": {"start": tr.start, "end": tr.end, "label": tr.label},
            "requests": totals,
            "requests_per_minute": await stats.requests_per_minute(s, host),
            "visitors": await stats.visitors(s, tr, host),
            "countries": (await stats.countries(s, tr, host))[:30],
            "statuses": await stats.statuses(s, tr, host),
            "top_paths": await stats.top_paths(s, tr, host, 15),
            "suspicious_paths": await stats.top_paths(s, tr, host, 15, "suspicious"),
            "timeseries": await stats.timeseries(s, tr, host),
            "crowdsec": await stats.alert_summary(s, tr, host),
        }


@router.get("/crowdsec/summary", tags=["crowdsec"])
async def crowdsec_summary(tr: TimeRange = Depends(get_range), host: str | None = Depends(host_param),
                           st=Depends(app_state), _: Principal = Depends(require_read)):
    async with st.db.session() as s:
        return {
            "alerts": await st.stats.alert_summary(s, tr, host),
            "decisions": {k: v for k, v in (await st.stats.decisions(s)).items() if k != "local_decisions"},
            "decision_history": await st.stats.decision_history(s, tr),
            "enforcement": await st.stats.blocked_by_enforcer(s, tr),
        }


@router.get("/crowdsec/alerts", tags=["crowdsec"])
async def crowdsec_alerts(tr: TimeRange = Depends(get_range), host: str | None = Depends(host_param),
                          scenario: str | None = Query(None, max_length=255),
                          severity: str | None = Query(None, pattern="^(critical|high|low)$"),
                          before_id: int | None = Query(None, ge=1), limit: int = Query(50, ge=1, le=500),
                          st=Depends(app_state), _: Principal = Depends(require_read)):
    async with st.db.session() as s:
        return {"items": await st.stats.alerts(s, tr=tr, host=host, scenario=scenario, severity=severity,
                                               before_id=before_id, limit=limit)}


@router.get("/crowdsec/decisions", tags=["crowdsec"])
async def crowdsec_decisions(st=Depends(app_state), _: Principal = Depends(require_read)):
    async with st.db.session() as s:
        return await st.stats.decisions(s)


@router.get("/crowdsec/metrics", tags=["crowdsec"])
async def crowdsec_metrics(st=Depends(app_state), _: Principal = Depends(require_read)):
    async with st.db.session() as s:
        return await st.stats.metrics_latest(s)


@router.get("/notifications", tags=["notifications"])
async def notifications(after_id: int | None = Query(None, ge=0), limit: int = Query(50, ge=1, le=200),
                        st=Depends(app_state), _: Principal = Depends(require_read)):
    async with st.db.session() as s:
        q = select(Notification)
        if after_id is not None:
            q = q.where(Notification.id > after_id).order_by(Notification.id.asc())
        else:
            q = q.order_by(Notification.id.desc())
        rows = (await s.execute(q.limit(limit))).scalars().all()
    return {"items": [{"id": n.id, "ts": n.ts, "kind": n.kind, "severity": n.severity, "title": n.title,
                       "message": n.message, "host": n.host, "delivered_ntfy": n.delivered_ntfy} for n in rows]}


@router.get("/ha/summary", tags=["home-assistant"])
async def ha_summary(st=Depends(app_state), _: Principal = Depends(require_read)):
    """Compact snapshot for Home Assistant (one request per update interval)."""
    now = now_ts()
    tr24 = TimeRange(now - 86400, now, "24h")
    async with st.db.session() as s:
        ov = await st.stats.overview(s, tr24)
        doms = await st.stats.domains(s, tr24)
        sources = await st.stats.sources(s)
        last_n = (await s.execute(select(Notification).order_by(Notification.id.desc()).limit(10))).scalars().all()
    top = next((c for c in ov["top_countries"] if c["country"]), None)
    return {
        "time": now,
        "requests_today": ov["requests_today"],
        "requests_24h": ov["requests_24h"],
        "blocked_24h": ov["blocked_24h"],
        "visitors_today": ov["visitors_today"]["value"],
        "requests_per_minute": ov["requests_per_minute"],
        "active_domains": ov["active_domains"],
        "crowdsec_alerts_24h": ov["crowdsec"]["alerts_24h"],
        "crowdsec_critical_alerts_24h": ov["crowdsec"]["critical_alerts_24h"],
        "crowdsec_local_decisions": ov["crowdsec"]["local_active_decisions"],
        "crowdsec_community_decisions": ov["crowdsec"]["community_active_decisions"],
        "top_country": top["country"] if top else None,
        "top_country_requests": top["requests"] if top else 0,
        "top_countries": ov["top_countries"][:5],
        "security_status": ov["security_status"],
        "sources": [{"name": x["name"], "status": x["status"], "last_success": x["last_success"]} for x in sources],
        "domains": [{"host": d["host"], "requests_24h": d["requests"], "blocked_24h": d["blocked"],
                     "requests_per_minute": d["requests_per_minute"], "crowdsec_mode": d["crowdsec_mode"]}
                    for d in doms],
        "notifications": [{"id": n.id, "ts": n.ts, "kind": n.kind, "severity": n.severity, "title": n.title,
                           "message": n.message, "host": n.host} for n in last_n],
    }


@router.get("/stream", tags=["live"])
async def stream(request: Request, st=Depends(app_state), _: Principal = Depends(require_read)):
    """Server-Sent Events: ``update`` (new data ingested) and ``notification`` events."""
    q = st.bus.subscribe()

    async def gen():
        try:
            yield "retry: 5000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=20)
                    yield msg
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            st.bus.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
