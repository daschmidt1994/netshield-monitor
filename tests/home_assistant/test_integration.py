import copy
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events

from custom_components.netshield_monitor.api import NetShieldAuthError, NetShieldConnectionError
from custom_components.netshield_monitor.const import DOMAIN, EVENT_NOTIFICATION, EVENT_SECURITY_ALERT
from custom_components.netshield_monitor.diagnostics import async_get_config_entry_diagnostics

from .conftest import SUMMARY

PATCH = "custom_components.netshield_monitor.api.NetShieldApi.summary"
DATA = {"url": "https://netshield.example.com", "token": "nsm_secret", "verify_ssl": True}


async def test_config_flow_success(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    with patch(PATCH, return_value=SUMMARY), patch("custom_components.netshield_monitor.async_setup_entry",
                                                   return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {**DATA, "url": DATA["url"] + "/"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["url"] == "https://netshield.example.com"


async def test_config_flow_errors(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    with patch(PATCH, side_effect=NetShieldAuthError):
        r = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    assert r["errors"] == {"base": "invalid_auth"}
    with patch(PATCH, side_effect=NetShieldConnectionError("x")):
        r = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    assert r["errors"] == {"base": "cannot_connect"}
    r = await hass.config_entries.flow.async_configure(result["flow_id"], {**DATA, "url": "ftp://x"})
    assert r["errors"] == {"url": "invalid_url"}


async def _setup(hass, summary=SUMMARY):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id=DATA["url"])
    entry.add_to_hass(hass)
    with patch(PATCH, return_value=summary):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_entities(hass: HomeAssistant):
    await _setup(hass)
    assert hass.states.get("sensor.netshield_requests_today").state == "1200"
    assert hass.states.get("sensor.netshield_requests_24h").state == "34000"
    assert hass.states.get("sensor.netshield_blocked_requests").state == "3100"
    dec = hass.states.get("sensor.netshield_crowdsec_active_decisions")
    assert dec.state == "12" and dec.attributes["community_blocklist_decisions"] == 31771
    assert hass.states.get("sensor.netshield_crowdsec_alerts_24h").state == "517"
    assert hass.states.get("sensor.netshield_top_country").state == "AT"
    assert hass.states.get("sensor.netshield_active_domains").state == "2"
    assert hass.states.get("binary_sensor.netshield_backend_online").state == "on"
    assert hass.states.get("binary_sensor.netshield_security_alert").state == "off"
    dom = hass.states.get("sensor.netshield_domain_app_example_com")
    assert dom.state == "30000" and dom.attributes["blocked_24h"] == 3000


async def test_events_and_offline(hass: HomeAssistant):
    entry = await _setup(hass)
    coordinator = entry.runtime_data
    events = async_capture_events(hass, EVENT_NOTIFICATION)
    critical = async_capture_events(hass, EVENT_SECURITY_ALERT)
    newer = copy.deepcopy(SUMMARY)
    newer["security_status"] = {"level": "critical", "reasons": [{"code": "critical_alerts_1h", "value": 1}]}
    newer["notifications"].insert(0, {"id": 6, "ts": 1793785100, "kind": "attack_spike", "severity": "critical",
                                      "title": "Angriffsspitze erkannt", "message": "y", "host": None})
    newer["domains"].append({"host": "new.example.com", "requests_24h": 5, "blocked_24h": 0,
                             "requests_per_minute": 0, "crowdsec_mode": None})
    with patch(PATCH, return_value=newer):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    assert [e.data["id"] for e in events] == [6]  # history (id 5) is not replayed
    assert len(critical) == 1
    assert hass.states.get("binary_sensor.netshield_security_alert").state == "on"
    assert hass.states.get("sensor.netshield_domain_new_example_com").state == "5"  # dynamically added

    with patch(PATCH, side_effect=NetShieldConnectionError("down")):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.netshield_backend_online").state == "off"
    assert hass.states.get("sensor.netshield_requests_today").state == "unavailable"


async def test_auth_failure_starts_reauth(hass: HomeAssistant):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id=DATA["url"])
    entry.add_to_hass(hass)
    with patch(PATCH, side_effect=NetShieldAuthError):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == "reauth" for f in flows)


async def test_diagnostics_redacts_secrets(hass: HomeAssistant):
    entry = await _setup(hass)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    text = str(diag)
    assert "nsm_secret" not in text and "netshield.example.com" not in text and "app.example.com" not in text


async def test_options_flow(hass: HomeAssistant):
    entry = await _setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with patch(PATCH, return_value=SUMMARY):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"scan_interval": 120, "domain_sensors": False})
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["scan_interval"] == 120
