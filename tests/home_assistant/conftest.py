import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


SUMMARY = {
    "time": 1793785000, "requests_today": 1200, "requests_24h": 34000, "blocked_24h": 3100, "visitors_today": 87,
    "requests_per_minute": 21.4, "active_domains": 2, "crowdsec_alerts_24h": 517, "crowdsec_critical_alerts_24h": 19,
    "crowdsec_local_decisions": 12, "crowdsec_community_decisions": 31771, "top_country": "AT",
    "top_country_requests": 20000, "top_countries": [{"country": "AT", "requests": 20000, "blocked": 0, "allowed": 20000}],
    "security_status": {"level": "ok", "reasons": []},
    "sources": [{"name": "netbird_access_logs", "status": "ok", "last_success": 1793785000}],
    "domains": [
        {"host": "app.example.com", "requests_24h": 30000, "blocked_24h": 3000, "requests_per_minute": 20.0,
         "crowdsec_mode": "enforce"},
        {"host": "cloud.example.com", "requests_24h": 4000, "blocked_24h": 100, "requests_per_minute": 1.4,
         "crowdsec_mode": "observe"},
    ],
    "notifications": [{"id": 5, "ts": 1793784000, "kind": "crowdsec_alert", "severity": "warning",
                       "title": "CrowdSec: crowdsecurity/http-probing", "message": "x", "host": None}],
}
