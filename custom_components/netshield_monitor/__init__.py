"""NetShield Monitor integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NetShieldApi
from .const import CONF_SCAN_INTERVAL, CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL, DEFAULT_SCAN_INTERVAL
from .coordinator import NetShieldCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

type NetShieldConfigEntry = ConfigEntry[NetShieldCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: NetShieldConfigEntry) -> bool:
    verify = entry.data.get(CONF_VERIFY_SSL, True)
    session = async_get_clientsession(hass, verify_ssl=verify)
    api = NetShieldApi(session, entry.data[CONF_URL], entry.data[CONF_TOKEN], verify)
    interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = NetShieldCoordinator(hass, entry, api, interval)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: NetShieldConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NetShieldConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
