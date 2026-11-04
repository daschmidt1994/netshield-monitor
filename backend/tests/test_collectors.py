import httpx
import respx
from sqlalchemy import func, select

from conftest import make_event
from netshield.collectors.crowdsec import (
    CrowdsecAlertsCollector,
    CrowdsecDecisionsCollector,
    LapiClient,
    parse_prometheus,
)
from netshield.collectors.netbird import NetBirdAccessLogCollector, NetBirdClient, NetBirdServicesCollector
from netshield.database.models import (
    CollectorState,
    CrowdsecAlert,
    CrowdsecDecision,
    DecisionCount,
    Domain,
    HourlyStat,
    ProxyRequest,
)

NB = "https://netbird.example.com"
CS = "http://crowdsec.test:8080"


def page(events, page_no, total_pages):
    return {"data": events, "page": page_no, "page_size": 100, "total_records": len(events) * total_pages,
            "total_pages": total_pages}


@respx.mock
async def test_netbird_access_logs_pagination_dedupe_and_classification(db, settings, now):
    events = [
        make_event(1, now - 100),
        make_event(2, now - 90, path="/.env", ip="203.0.113.5", country="US"),
        make_event(3, now - 80, status=403, auth="crowdsec_ban", meta={"crowdsec_verdict": "crowdsec_ban"},
                   ip="203.0.113.9", country="SG"),
        make_event(4, now - 70, status=403, auth="crowdsec_captcha",
                   meta={"crowdsec_verdict": "crowdsec_captcha"}, ip="203.0.113.10", country="DE"),
        make_event(5, now - 60, ip="172.30.0.1", country=None, path="/healthz"),
        make_event(6, now - 50, host="obs.example.com", meta={"crowdsec_mode": "observe",
                                                              "crowdsec_verdict": "crowdsec_ban"}),
    ]
    route = respx.get(f"{NB}/api/events/proxy")
    route.side_effect = [
        httpx.Response(200, json=page(events[:3], 1, 2)),
        httpx.Response(200, json=page(events[3:], 2, 2)),
        httpx.Response(200, json=page(events[4:], 1, 1)),  # second run: overlap must be ignored
    ]
    col = NetBirdAccessLogCollector(db, settings, NetBirdClient(settings))
    assert await col.run_safe() == 6
    assert route.calls[0].request.headers["Authorization"] == "Token nbp_test"
    params = route.calls[0].request.url.params
    assert params["sort_order"] == "asc" and params["page_size"] == "100" and params["start_date"].endswith("Z")
    assert await col.run_safe() == 0

    async with db.session() as s:
        rows = {r.id: r for r in (await s.execute(select(ProxyRequest))).scalars()}
        assert rows["ev000001"].category == "visitor"
        assert rows["ev000001"].ip == "198.51.100.0/24"  # truncated by default
        assert rows["ev000001"].visitor_hash
        assert rows["ev000002"].category == "suspicious"
        assert rows["ev000003"].category == "blocked" and rows["ev000003"].verdict == "crowdsec_ban"
        assert rows["ev000004"].category == "challenged"
        assert rows["ev000005"].category == "internal" and rows["ev000005"].visitor_hash is None
        assert rows["ev000006"].category == "suspicious" and rows["ev000006"].observe_only
        total = (await s.execute(select(func.sum(HourlyStat.count)))).scalar()
        assert total == 6
        obs = (await s.execute(select(func.sum(HourlyStat.observe_hits)))).scalar()
        assert obs == 1
        hosts = set((await s.execute(select(Domain.host))).scalars())
        assert hosts == {"app.example.com", "obs.example.com"}
        st = await s.get(CollectorState, "netbird_access_logs")
        assert st.status == "ok" and st.cursor["last_ts"] == now - 50


@respx.mock
async def test_netbird_errors_are_reported(db, settings):
    respx.get(f"{NB}/api/events/proxy").mock(return_value=httpx.Response(401, json={"message": "x"}))
    col = NetBirdAccessLogCollector(db, settings, NetBirdClient(settings))
    assert await col.run_safe() == 0
    async with db.session() as s:
        st = await s.get(CollectorState, "netbird_access_logs")
        assert st.status == "error" and "401" in st.last_error and "nbp_test" not in st.last_error


@respx.mock
async def test_netbird_services_sync(db, settings):
    respx.get(f"{NB}/api/reverse-proxies/services").mock(return_value=httpx.Response(200, json=[
        {"id": "s1", "name": "app", "domain": "App.example.com", "enabled": True, "mode": "http",
         "access_restrictions": {"crowdsec_mode": "enforce"}, "auth": {"bearer_auth": {"enabled": True}}},
        {"id": "s2", "name": "obs", "domain": "obs.example.com", "enabled": False,
         "access_restrictions": {"crowdsec_mode": "observe"}, "auth": {}},
    ]))
    col = NetBirdServicesCollector(db, settings, NetBirdClient(settings))
    assert await col.run_safe() == 2
    async with db.session() as s:
        app = await s.get(Domain, "app.example.com")
        assert app.source == "netbird" and app.crowdsec_mode == "enforce" and app.auth_enabled
        obs = await s.get(Domain, "obs.example.com")
        assert obs.crowdsec_mode == "observe" and not obs.enabled


def alert(i, created, scenario="crowdsecurity/http-probing", decisions=True, ip="203.0.113.50"):
    """Shape copied from a real CrowdSec v1.8 /v1/alerts entry (values anonymised)."""
    return {
        "id": i, "uuid": f"u{i}", "scenario": scenario, "message": f"Ip {ip} performed '{scenario}'",
        "created_at": created, "start_at": created, "stop_at": created, "events_count": 11, "simulated": False,
        "machine_id": "localhost", "capacity": 10, "leakspeed": "10s", "kind": "", "labels": None,
        "source": {"scope": "Ip", "value": ip, "ip": ip, "cn": "CA", "as_name": "EXAMPLE-AS", "as_number": "64500",
                   "range": "203.0.113.0/24", "latitude": 1.0, "longitude": 2.0},
        "decisions": [{"type": "ban", "duration": "3h59m", "origin": "crowdsec"}] if decisions else [],
        "events": [{"meta": [{"key": "target_fqdn", "value": "app.example.com"}]}],
        "meta": [{"key": "target_uri", "value": "[\"/x\"]"}],
    }


@respx.mock
async def test_crowdsec_alerts(db, settings):
    respx.post(f"{CS}/v1/watchers/login").mock(return_value=httpx.Response(
        200, json={"code": 200, "expire": "2099-01-01T00:00:00Z", "token": "jwt"}))
    alerts_route = respx.get(f"{CS}/v1/alerts").mock(return_value=httpx.Response(200, json=[
        alert(1, "2026-11-04T09:00:00Z"),
        alert(2, "2026-11-04T09:01:00Z", scenario="crowdsecurity/vpatch-git-config"),
        alert(3, "2026-11-04T09:02:00Z", decisions=False),
    ]))
    col = CrowdsecAlertsCollector(db, settings, LapiClient(settings))
    n = await col.run_safe()
    assert n == 3
    req = alerts_route.calls[0].request
    assert req.headers["Authorization"] == "Bearer jwt"
    assert req.url.params["include_capi"] == "false"
    assert col.new_alerts == []  # no notifications for the initial backfill
    async with db.session() as s:
        rows = {a.id: a for a in (await s.execute(select(CrowdsecAlert))).scalars()}
        assert rows[1].severity == "high" and rows[1].target_host == "app.example.com"
        assert rows[1].source_value == "203.0.113.0/24"
        assert rows[2].severity == "critical"
        assert rows[3].severity == "low"
    # next run: new alerts are queued for notification
    alerts_route.mock(return_value=httpx.Response(200, json=[alert(4, "2026-11-04T10:00:00Z",
                                                                   scenario="crowdsecurity/appsec-vpatch")]))
    assert await col.run_safe() == 1
    assert [a["id"] for a in col.new_alerts] == [4]


METRICS = """# HELP cs_active_decisions Number of active decisions.
# TYPE cs_active_decisions gauge
cs_active_decisions{action="ban",origin="CAPI",reason="http:scan"} 9857
cs_active_decisions{action="ban",origin="CAPI",reason="ssh:bruteforce"} 5209
cs_active_decisions{action="captcha",origin="lists",reason="firehol_botscout_7d"} 543
cs_active_decisions{action="ban",origin="crowdsec",reason="crowdsecurity/jira_cve-2021-26086"} 6
cs_appsec_block_total{appsec_engine="myAppSecComponent",source="1.2.3.4"} 3
"""


@respx.mock
async def test_crowdsec_decisions_with_metrics(db, settings):
    dec = respx.get(f"{CS}/v1/decisions").mock(return_value=httpx.Response(200, json=[
        {"id": 10, "origin": "crowdsec", "type": "ban", "scope": "Ip", "value": "203.0.113.7",
         "scenario": "crowdsecurity/jira_cve-2021-26086", "duration": "3h0m0s"},
    ]))
    respx.get("http://crowdsec.test:6060/metrics").mock(return_value=httpx.Response(200, text=METRICS))
    col = CrowdsecDecisionsCollector(db, settings, LapiClient(settings))
    assert await col.run_safe() == 1
    assert dec.calls[0].request.headers["X-Api-Key"] == "bouncer-test"
    assert "crowdsec" in dec.calls[0].request.url.params["origins"]
    async with db.session() as s:
        d = (await s.execute(select(CrowdsecDecision))).scalar_one()
        assert d.value == "203.0.113.0/24" and d.expires_ts
        counts = {(c.origin, c.type): c.count for c in (await s.execute(select(DecisionCount))).scalars()}
        assert counts[("CAPI", "ban")] == 15066
        assert counts[("lists", "captcha")] == 543
        assert counts[("crowdsec", "ban")] == 6


def test_prometheus_parser():
    vals = parse_prometheus(METRICS)
    assert vals[("cs_active_decisions", "origin=CAPI,action=ban")] == 15066
    assert vals[("cs_appsec_block_total", "")] == 3
