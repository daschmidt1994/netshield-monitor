"""Diagnostics (secrets redacted)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import NetShieldConfigEntry
from .const import CONF_TOKEN, CONF_URL

TO_REDACT = {CONF_TOKEN, CONF_URL, "host", "domains", "message", "top_countries"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: NetShieldConfigEntry) -> dict[str, Any]:
    c = entry.runtime_data
    data = c.data or {}
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "last_update_success": c.last_update_success,
        "domain_count": len(data.get("domains", [])),
        "summary": async_redact_data({k: v for k, v in data.items() if k != "notifications"}, TO_REDACT),
    }
