import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from conftest import make_event
from netshield.app import create_app
from netshield.collectors.netbird import NetBirdAccessLogCollector, NetBirdClient
from netshield.security.auth import create_admin
from netshield.services.maintenance import Maintenance

PASSWORD = "correct-horse-battery"


@pytest.fixture
async def app(settings):
    application = create_app(settings, start_collectors=False)
    async with application.router.lifespan_context(application):
        await create_admin(application.state.db, "admin", PASSWORD)
        yield application


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def login(client) -> str:
    r = await client.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD})
    assert r.status_code == 200
    return r.json()["csrf_token"]


async def seed(app, settings, now):
    events = [make_event(i, now - 600 + i, ip=f"198.51.100.{i % 5}") for i in range(20)]
    events += [make_event(100 + i, now - 300 + i, status=403, auth="crowdsec_ban",
                          meta={"crowdsec_verdict": "crowdsec_ban"}, ip="203.0.113.9", country="SG")
               for i in range(5)]
    events += [make_event(200, now - 100, path="/wp-login.php", ip="203.0.113.77", country="US", status=404)]
    events += [make_event(300, now - 50, ip="172.30.0.1", country=None)]
    col = NetBirdAccessLogCollector(app.state.db, settings, NetBirdClient(settings))
    assert await col.ingest(events) == len(events)
    await Maintenance(app.state.db, settings).update_daily_visitors(1)


async def test_health_is_public_and_minimal(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert set(r.json()) == {"status", "version", "time"}
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]


async def test_auth_required(client):
    for path in ("/api/v1/overview", "/api/v1/domains", "/api/v1/crowdsec/summary", "/api/v1/ha/summary"):
        assert (await client.get(path)).status_code == 401


async def test_login_wrong_password(client):
    r = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong-password!"})
    assert r.status_code == 401
    r = await client.post("/api/v1/auth/login", json={"username": "nobody", "password": "wrong-password!"})
    assert r.status_code == 401


async def test_login_rate_limited(client, app):
    app.state.login_limiter.limit = 3
    for _ in range(3):
        await client.post("/api/v1/auth/login", json={"username": "admin", "password": "x"})
    r = await client.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD})
    assert r.status_code == 429


async def test_session_csrf_and_tokens(client):
    csrf = await login(client)
    assert (await client.get("/api/v1/auth/me")).json()["scope"] == "admin"
    # unsafe method without CSRF header is rejected
    r = await client.post("/api/v1/admin/tokens", json={"name": "android"})
    assert r.status_code == 403
    r = await client.post("/api/v1/admin/tokens", json={"name": "android", "scope": "read"},
                          headers={"X-CSRF-Token": csrf})
    assert r.status_code == 201
    token = r.json()["token"]
    assert token.startswith("nsm_")
    listed = (await client.get("/api/v1/admin/tokens")).json()["items"]
    assert "token" not in listed[0] and "token_hash" not in listed[0]

    async with AsyncClient(transport=client._transport, base_url="http://test") as anon:
        h = {"Authorization": f"Bearer {token}"}
        assert (await anon.get("/api/v1/overview", headers=h)).status_code == 200
        # read tokens cannot use admin endpoints
        assert (await anon.get("/api/v1/admin/tokens", headers=h)).status_code == 403
        assert (await anon.get("/api/v1/overview", headers={"Authorization": "Bearer nsm_wrong"})).status_code \
            == 401
        tid = listed[0]["id"]
        r = await client.delete(f"/api/v1/admin/tokens/{tid}", headers={"X-CSRF-Token": csrf})
        assert r.status_code == 200
        assert (await anon.get("/api/v1/overview", headers=h)).status_code == 401


async def test_overview_numbers_from_real_rows(client, app, settings, now):
    await seed(app, settings, now)
    await login(client)
    ov = (await client.get("/api/v1/overview", params={"range": "1h"})).json()
    req = ov["requests"]
    assert req["requests"] == 27
    assert req["blocked"] == 5
    assert req["suspicious"] == 1
    assert req["internal"] == 1
    assert req["external_requests"] == 26
    assert ov["visitors"]["value"] == 5  # 5 distinct visitor IPs, scanner/blocked/internal excluded
    assert ov["active_domains"] == 1
    countries = {c["country"]: c for c in ov["top_countries"]}
    assert countries["SG"]["blocked"] == 5 and countries["AT"]["requests"] == 20
    assert None not in countries  # internal requests are excluded from GeoIP stats

    ts = (await client.get("/api/v1/timeseries", params={"range": "1h"})).json()
    assert ts["bucket_seconds"] == 60 and sum(p["total"] for p in ts["points"]) == 27

    dom = (await client.get("/api/v1/domains/app.example.com", params={"range": "1h"})).json()
    assert dom["requests"]["requests"] == 27
    assert dom["suspicious_paths"]["items"][0]["path"] == "/wp-login.php"
    assert (await client.get("/api/v1/domains/unknown.example.com")).status_code == 404

    src = (await client.get("/api/v1/top/sources", params={"range": "1h"})).json()
    assert all("/" in item["ip"] for item in src["items"])  # truncated networks only

    ha = (await client.get("/api/v1/ha/summary")).json()
    assert ha["requests_24h"] == 27 and ha["blocked_24h"] == 5 and ha["top_country"] == "AT"
    assert ha["domains"][0]["host"] == "app.example.com"


async def test_long_range_uses_hourly_aggregates(client, app, settings, now):
    await seed(app, settings, now)
    await login(client)
    ov = (await client.get("/api/v1/overview", params={"range": "7d"})).json()
    assert ov["requests"]["requests"] == 27 and ov["requests"]["blocked"] == 5
    ts = (await client.get("/api/v1/timeseries", params={"range": "30d"})).json()
    assert ts["source"] == "hourly" and sum(p["total"] for p in ts["points"]) == 27


async def test_input_validation(client):
    await login(client)
    assert (await client.get("/api/v1/overview", params={"range": "1y"})).status_code == 422
    assert (await client.get("/api/v1/overview", params={"host": "bad host/../"})).status_code == 422
    assert (await client.get("/api/v1/overview", params={"from": 100, "to": 50})).status_code == 422
    assert (await client.get("/api/v1/requests", params={"limit": 100000})).status_code == 422


async def test_manual_domain_management(client):
    csrf = await login(client)
    h = {"X-CSRF-Token": csrf}
    assert (await client.post("/api/v1/domains", json={"host": "new.example.com"}, headers=h)).status_code == 201
    assert (await client.post("/api/v1/domains", json={"host": "new.example.com"}, headers=h)).status_code == 409
    assert (await client.patch("/api/v1/domains/new.example.com", json={"hidden": True}, headers=h)).status_code \
        == 200
    items = (await client.get("/api/v1/domains")).json()["items"]
    assert all(d["host"] != "new.example.com" for d in items)
    assert (await client.delete("/api/v1/domains/new.example.com", headers=h)).status_code == 200


async def test_sources_never_expose_secrets(client):
    await login(client)
    body = (await client.get("/api/v1/sources")).text
    for secret in ("nbp_test", "bouncer-test", "machine-test"):
        assert secret not in body


async def test_settings_roundtrip(client):
    csrf = await login(client)
    cur = (await client.get("/api/v1/admin/settings")).json()
    cur["notifications"]["cooldown_minutes"] = 5
    r = await client.put("/api/v1/admin/settings", json=cur, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200 and r.json()["notifications"]["cooldown_minutes"] == 5
    cur["notifications"]["cooldown_minutes"] = 0
    r = await client.put("/api/v1/admin/settings", json=cur, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 422


async def test_rate_limit(settings):
    settings.rate_limit_per_minute = 10
    application = create_app(settings, start_collectors=False)
    async with application.router.lifespan_context(application):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as c:
            codes = [(await c.get("/api/v1/overview")).status_code for _ in range(12)]
    assert codes[-1] == 429 and 401 in codes


def test_forwarded_for_only_from_trusted_proxy():
    from starlette.requests import Request

    from netshield.security.http import ClientIpResolver

    def req(peer, xff):
        return Request({"type": "http", "client": (peer, 1), "headers": [(b"x-forwarded-for", xff.encode())]})

    r = ClientIpResolver(["172.30.0.10/32"])
    assert r.resolve(req("198.51.100.1", "203.0.113.5")) == "198.51.100.1"  # untrusted peer: header ignored
    assert r.resolve(req("172.30.0.10", "203.0.113.5")) == "203.0.113.5"
    assert r.resolve(req("172.30.0.10", "203.0.113.5, 172.30.0.10")) == "203.0.113.5"
    assert ClientIpResolver([]).resolve(req("172.30.0.10", "203.0.113.5")) == "172.30.0.10"


@respx.mock
async def test_notifier_dedup_and_ntfy(app, settings, now):
    settings.ntfy_url = "https://ntfy.example.com"
    settings.ntfy_topic = "netshield-test"
    route = respx.post("https://ntfy.example.com/netshield-test").mock(return_value=httpx.Response(200))
    notifier = app.state.notifier
    notifier.ntfy.settings = settings
    cfg = (await app.state.runtime.get()).notifications
    assert await notifier.emit("test", "critical", "Titel", "Nachricht", "k1", cfg) == 1
    assert await notifier.emit("test", "critical", "Titel", "Nachricht", "k1", cfg) == 0  # cooldown
    assert route.call_count == 1
    assert route.calls[0].request.headers["Priority"] == "urgent"


async def test_attack_spike_notification(app, settings, now):
    cfg = (await app.state.runtime.get()).notifications
    cfg.attack_spike_min_per_5min = 5
    events = [make_event(i, now - 60 + i, status=403, auth="crowdsec_ban", meta={"crowdsec_verdict": "crowdsec_ban"})
              for i in range(6)]
    await NetBirdAccessLogCollector(app.state.db, settings, NetBirdClient(settings)).ingest(events)
    assert await app.state.notifier.run_once() >= 1
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await login(c)
        items = (await c.get("/api/v1/notifications")).json()["items"]
    assert any(n["kind"] == "attack_spike" for n in items)
