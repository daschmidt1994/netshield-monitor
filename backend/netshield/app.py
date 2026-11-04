"""FastAPI application factory and lifecycle."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import admin, routes
from .collectors.crowdsec import (
    CrowdsecAlertsCollector,
    CrowdsecDecisionsCollector,
    CrowdsecMetricsCollector,
    LapiClient,
)
from .collectors.netbird import NetBirdAccessLogCollector, NetBirdClient, NetBirdServicesCollector
from .config import Settings, get_settings
from .database import Database
from .security.auth import admin_exists, create_admin
from .security.http import (
    ClientIpResolver,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    SlidingWindowLimiter,
)
from .services.events import EventBus
from .services.maintenance import Maintenance
from .services.notifier import Notifier
from .services.runtime_settings import RuntimeSettingsStore
from .services.stats import Stats

log = logging.getLogger("netshield")
STATIC_DIR = Path(__file__).parent / "static"


def build_collectors(app: FastAPI) -> list:
    st = app.state
    cfg: Settings = st.settings
    nb = NetBirdClient(cfg)
    lapi = LapiClient(cfg)
    st.clients = [nb, lapi]
    access = NetBirdAccessLogCollector(st.db, cfg, nb)
    alerts = CrowdsecAlertsCollector(st.db, cfg, lapi)
    st.notifier = Notifier(st.db, cfg, st.runtime, st.bus, alerts_collector=alerts)
    collectors = [
        access,
        NetBirdServicesCollector(st.db, cfg, nb),
        alerts,
        CrowdsecDecisionsCollector(st.db, cfg, lapi),
        CrowdsecMetricsCollector(st.db, cfg, lapi),
        Maintenance(st.db, cfg, access.salts),
        st.notifier,
    ]

    async def on_update(name: str, n: int) -> None:
        await st.bus.publish("update", {"source": name, "new_items": n})

    for c in collectors:
        c.listeners.append(on_update)
    return collectors


def create_app(settings: Settings | None = None, *, start_collectors: bool = True) -> FastAPI:
    cfg = settings or get_settings()
    logging.basicConfig(level=cfg.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # request URLs are noisy

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await app.state.db.init()
        if cfg.admin_password and not await admin_exists(app.state.db):
            await create_admin(app.state.db, cfg.admin_username, cfg.admin_password.get_secret_value())
            log.info("created admin user '%s' from environment", cfg.admin_username)
        if not await admin_exists(app.state.db):
            log.warning("no admin user yet – run: docker compose exec netshield netshield create-admin")
        app.state.collectors = build_collectors(app)
        if start_collectors:
            for c in app.state.collectors:
                c.start()
        log.info("NetShield Monitor %s started (netbird=%s, crowdsec alerts=%s, decisions=%s, ntfy=%s)",
                 __version__, cfg.netbird_enabled, cfg.crowdsec_alerts_enabled, cfg.crowdsec_decisions_enabled,
                 cfg.ntfy_enabled)
        yield
        for c in app.state.collectors:
            await c.stop()
        for client in getattr(app.state, "clients", []):
            await client.aclose()
        await app.state.db.dispose()

    app = FastAPI(
        title="NetShield Monitor API",
        version=__version__,
        description="Traffic & security statistics from NetBird reverse proxy and CrowdSec.",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = cfg
    app.state.db = Database(cfg.database_url)
    app.state.stats = Stats(cfg)
    app.state.bus = EventBus()
    app.state.runtime = RuntimeSettingsStore(app.state.db)
    app.state.ip_resolver = ClientIpResolver(cfg.trusted_proxies)
    app.state.login_limiter = SlidingWindowLimiter(cfg.login_attempts_per_15min, 900)

    app.add_middleware(RateLimitMiddleware, limiter=SlidingWindowLimiter(cfg.rate_limit_per_minute, 60),
                       resolver=app.state.ip_resolver)
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(routes.router)
    app.include_router(admin.router)

    @app.exception_handler(Exception)
    async def unhandled(_request, exc):  # never leak internals
        log.exception("unhandled error")
        return JSONResponse({"detail": "internal error"}, status_code=500)

    if (STATIC_DIR / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse({"detail": "not found"}, status_code=404)
            candidate = (STATIC_DIR / path).resolve()
            if path and candidate.is_file() and STATIC_DIR.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(STATIC_DIR / "index.html")

    return app
