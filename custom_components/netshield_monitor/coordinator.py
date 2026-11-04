"""Data update coordinator."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NetShieldApi, NetShieldAuthError, NetShieldConnectionError
from .const import DOMAIN, EVENT_NOTIFICATION, EVENT_SECURITY_ALERT

_LOGGER = logging.getLogger(__name__)


class NetShieldCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls /api/v1/ha/summary and fires events for new notifications."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: NetShieldApi, interval: int) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=interval),
                         config_entry=entry)
        self.api = api
        self._last_notification_id: int | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.api.summary()
        except NetShieldAuthError as err:
            raise ConfigEntryAuthFailed("NetShield API token was rejected") from err
        except NetShieldConnectionError as err:
            raise UpdateFailed(str(err)) from err
        self._fire_events(data.get("notifications") or [])
        return data

    def _fire_events(self, notifications: list[dict[str, Any]]) -> None:
        if not notifications:
            if self._last_notification_id is None:
                self._last_notification_id = 0
            return
        newest = max(n["id"] for n in notifications)
        if self._last_notification_id is None:
            # first refresh after start: don't replay history
            self._last_notification_id = newest
            return
        for n in sorted(notifications, key=lambda x: x["id"]):
            if n["id"] <= self._last_notification_id:
                continue
            payload = {k: n.get(k) for k in ("id", "ts", "kind", "severity", "title", "message", "host")}
            self.hass.bus.async_fire(EVENT_NOTIFICATION, payload)
            if n.get("severity") == "critical":
                self.hass.bus.async_fire(EVENT_SECURITY_ALERT, payload)
        self._last_notification_id = newest
