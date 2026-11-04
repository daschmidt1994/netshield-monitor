"""Command line helpers: ``netshield serve | create-admin | create-token | check``."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from .config import get_settings
from .database import Database


def _serve(args) -> None:
    import uvicorn

    uvicorn.run("netshield.main:app", host=args.host, port=args.port, proxy_headers=False,
                log_level=get_settings().log_level.lower(), access_log=False)


async def _create_admin(args) -> None:
    from .security.auth import create_admin

    db = Database(get_settings().database_url)
    await db.init()
    pw = getpass.getpass("New admin password (min. 12 chars): ")
    if pw != getpass.getpass("Repeat password: "):
        sys.exit("passwords do not match")
    await create_admin(db, args.username, pw, replace=True)
    await db.dispose()
    print(f"admin user '{args.username}' saved")


async def _create_token(args) -> None:
    from .database.models import ApiToken
    from .security.auth import new_api_token, sha256
    from .util import now_ts

    db = Database(get_settings().database_url)
    await db.init()
    raw = new_api_token()
    async with db.session() as s:
        s.add(ApiToken(name=args.name, prefix=raw[:12], token_hash=sha256(raw), scope=args.scope,
                       created_ts=now_ts()))
        await s.commit()
    await db.dispose()
    print(raw)


async def _check(_args) -> None:
    """Verify connectivity to all configured sources (no data is stored)."""
    from .collectors.base import CollectorError
    from .collectors.crowdsec import LapiClient
    from .collectors.netbird import NetBirdClient
    from .util import now_ts

    cfg = get_settings()
    ok = True

    async def step(name, coro):
        nonlocal ok
        try:
            result = await coro
            print(f"[ OK ] {name}: {result}")
        except CollectorError as exc:
            ok = False
            print(f"[FAIL] {name}: {exc}")

    if cfg.netbird_enabled:
        nb = NetBirdClient(cfg)

        async def nb_events():
            d = await nb.proxy_events(now_ts() - 3600, 1)
            return f"{d.get('total_records', 0)} access log entries in the last hour"

        async def nb_services():
            return f"{len(await nb.services())} services"

        await step("NetBird access logs", nb_events())
        await step("NetBird services", nb_services())
        await nb.aclose()
    else:
        print("[SKIP] NetBird not configured")
    lapi = LapiClient(cfg)
    if cfg.crowdsec_decisions_enabled:
        async def dec():
            return f"{len(await lapi.decisions(cfg.crowdsec_local_origins))} local decisions"
        await step("CrowdSec decisions (bouncer key)", dec())
    else:
        print("[SKIP] CrowdSec bouncer key not configured")
    if cfg.crowdsec_alerts_enabled:
        async def al():
            return f"{len(await lapi.alerts(3600, None))} alerts in the last hour"
        await step("CrowdSec alerts (machine login)", al())
    else:
        print("[SKIP] CrowdSec machine credentials not configured")
    if cfg.crowdsec_metrics_url:
        async def met():
            return f"{len((await lapi.metrics()).splitlines())} metric lines"
        await step("CrowdSec metrics", met())
    await lapi.aclose()
    sys.exit(0 if ok else 1)


def main() -> None:
    p = argparse.ArgumentParser(prog="netshield")
    sub = p.add_subparsers(dest="cmd", required=True)
    sv = sub.add_parser("serve", help="run the web server and collectors")
    sv.add_argument("--host", default="0.0.0.0")  # noqa: S104 - container default
    sv.add_argument("--port", type=int, default=8080)
    ca = sub.add_parser("create-admin", help="create or reset the web admin user")
    ca.add_argument("--username", default=get_settings().admin_username)
    ct = sub.add_parser("create-token", help="create an API token (prints it once)")
    ct.add_argument("name")
    ct.add_argument("--scope", choices=["read", "admin"], default="read")
    sub.add_parser("check", help="test connectivity to all configured data sources")
    args = p.parse_args()
    if args.cmd == "serve":
        _serve(args)
    elif args.cmd == "create-admin":
        asyncio.run(_create_admin(args))
    elif args.cmd == "create-token":
        asyncio.run(_create_token(args))
    elif args.cmd == "check":
        asyncio.run(_check(args))


if __name__ == "__main__":
    main()
