"""Shared fixtures. All sample data uses documentation IP ranges and example.com domains."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest

from netshield.config import Settings
from netshield.database import Database


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%S.%f") + "123Z"  # nanosecond-style


def make_event(i: int, ts: float, *, host="app.example.com", path="/", status=200, ip="198.51.100.10",
               country="AT", meta=None, auth=None, protocol="http") -> dict:
    """Shape copied from a real NetBird v0.81 /api/events/proxy entry (values anonymised)."""
    ev = {
        "bytes_download": 1000 + i, "bytes_upload": 0, "city_name": "Vienna" if country else None,
        "country_code": country, "duration_ms": 12, "host": host, "id": f"ev{i:06d}", "method": "GET",
        "path": path, "protocol": protocol, "service_id": "svc1", "source_ip": ip, "status_code": status,
        "subdivision_code": "9", "timestamp": iso(ts),
    }
    if meta:
        ev["metadata"] = meta
    if auth:
        ev["auth_method_used"] = auth
    if status == 403 and auth:
        ev["reason"] = "Authentication failed"
    return ev


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db",
        netbird_url="https://netbird.example.com",
        netbird_token="nbp_test",  # noqa: S106
        crowdsec_lapi_url="http://crowdsec.test:8080",
        crowdsec_bouncer_key="bouncer-test",
        crowdsec_machine_id="netshield-test",
        crowdsec_machine_password="machine-test",
        crowdsec_metrics_url="http://crowdsec.test:6060/metrics",
        cookie_secure=False,
        timezone="Europe/Vienna",
        rate_limit_per_minute=1000,
    )


@pytest.fixture
async def db(settings) -> Database:
    d = Database(settings.database_url)
    await d.init()
    yield d
    await d.dispose()


@pytest.fixture
def now() -> int:
    return int(time.time())
