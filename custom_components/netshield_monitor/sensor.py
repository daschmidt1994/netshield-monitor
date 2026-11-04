"""Sensors for NetShield Monitor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import NetShieldConfigEntry
from .const import CONF_DOMAIN_SENSORS
from .coordinator import NetShieldCoordinator
from .entity import NetShieldEntity


@dataclass(frozen=True, kw_only=True)
class NetShieldSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _security_attrs(d: dict[str, Any]) -> dict[str, Any]:
    return {"reasons": [r.get("code") for r in d.get("security_status", {}).get("reasons", [])]}


SENSORS: tuple[NetShieldSensorDescription, ...] = (
    NetShieldSensorDescription(key="requests_today", translation_key="requests_today", icon="mdi:web",
                               state_class=SensorStateClass.TOTAL, native_unit_of_measurement="requests",
                               value_fn=lambda d: d.get("requests_today")),
    NetShieldSensorDescription(key="requests_24h", translation_key="requests_24h", icon="mdi:web-clock",
                               state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement="requests",
                               value_fn=lambda d: d.get("requests_24h")),
    NetShieldSensorDescription(key="requests_per_minute", translation_key="requests_per_minute", icon="mdi:speedometer",
                               state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement="req/min",
                               value_fn=lambda d: d.get("requests_per_minute")),
    NetShieldSensorDescription(key="visitors_today", translation_key="visitors_today", icon="mdi:account-group",
                               state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement="visitors",
                               value_fn=lambda d: d.get("visitors_today")),
    NetShieldSensorDescription(key="blocked_requests", translation_key="blocked_requests", icon="mdi:shield-off",
                               state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement="requests",
                               value_fn=lambda d: d.get("blocked_24h")),
    NetShieldSensorDescription(key="crowdsec_active_decisions", translation_key="crowdsec_active_decisions",
                               icon="mdi:gavel", state_class=SensorStateClass.MEASUREMENT,
                               native_unit_of_measurement="decisions",
                               value_fn=lambda d: d.get("crowdsec_local_decisions"),
                               attrs_fn=lambda d: {"community_blocklist_decisions": d.get("crowdsec_community_decisions")}),
    NetShieldSensorDescription(key="crowdsec_alerts_24h", translation_key="crowdsec_alerts_24h", icon="mdi:alert",
                               state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement="alerts",
                               value_fn=lambda d: d.get("crowdsec_alerts_24h"),
                               attrs_fn=lambda d: {"critical": d.get("crowdsec_critical_alerts_24h")}),
    NetShieldSensorDescription(key="top_country", translation_key="top_country", icon="mdi:earth",
                               value_fn=lambda d: d.get("top_country"),
                               attrs_fn=lambda d: {"requests": d.get("top_country_requests"),
                                                   "top_countries": d.get("top_countries"),
                                                   "note": "GeoIP locations are approximate"}),
    NetShieldSensorDescription(key="active_domains", translation_key="active_domains", icon="mdi:domain",
                               state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement="domains",
                               value_fn=lambda d: d.get("active_domains")),
    NetShieldSensorDescription(key="security_status", translation_key="security_status", icon="mdi:shield-check",
                               device_class=None, options=["ok", "warning", "critical"],
                               value_fn=lambda d: d.get("security_status", {}).get("level"),
                               attrs_fn=_security_attrs),
    NetShieldSensorDescription(key="last_notification", translation_key="last_notification", icon="mdi:bell",
                               entity_category=EntityCategory.DIAGNOSTIC,
                               value_fn=lambda d: (d.get("notifications") or [{}])[0].get("title"),
                               attrs_fn=lambda d: {k: (d.get("notifications") or [{}])[0].get(k)
                                                   for k in ("severity", "message", "host", "ts", "kind")}),
)


async def async_setup_entry(hass: HomeAssistant, entry: NetShieldConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(NetShieldSensor(coordinator, desc) for desc in SENSORS)
    if not entry.options.get(CONF_DOMAIN_SENSORS, True):
        return
    known: set[str] = set()

    @callback
    def _add_domains() -> None:
        new = [d["host"] for d in (coordinator.data or {}).get("domains", []) if d["host"] not in known]
        if new:
            known.update(new)
            async_add_entities(NetShieldDomainSensor(coordinator, host) for host in new)

    _add_domains()
    entry.async_on_unload(coordinator.async_add_listener(_add_domains))


class NetShieldSensor(NetShieldEntity, SensorEntity):
    entity_description: NetShieldSensorDescription

    def __init__(self, coordinator: NetShieldCoordinator, description: NetShieldSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        # stable, language-independent entity ids (e.g. sensor.netshield_requests_today)
        self.entity_id = f"sensor.netshield_{description.key}"
        if description.options:
            self._attr_device_class = "enum"  # type: ignore[assignment]

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attrs_fn
        return fn(self.coordinator.data or {}) if fn else None


class NetShieldDomainSensor(NetShieldEntity, SensorEntity):
    """Requests in the last 24 h for one domain (one entity per domain, not per IP/request)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "requests"
    _attr_icon = "mdi:web"
    _attr_translation_key = "domain_requests"

    def __init__(self, coordinator: NetShieldCoordinator, host: str) -> None:
        super().__init__(coordinator, f"domain_{host}")
        self.host = host
        self._attr_translation_placeholders = {"domain": host}
        self.entity_id = f"sensor.netshield_domain_{slugify(host)}"

    def _row(self) -> dict[str, Any] | None:
        for d in (self.coordinator.data or {}).get("domains", []):
            if d["host"] == self.host:
                return d
        return None

    @property
    def available(self) -> bool:
        return super().available and self._row() is not None

    @property
    def native_value(self) -> int | None:
        row = self._row()
        return row["requests_24h"] if row else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        row = self._row()
        if not row:
            return None
        return {"domain": self.host, "blocked_24h": row.get("blocked_24h"),
                "requests_per_minute": row.get("requests_per_minute"), "crowdsec_mode": row.get("crowdsec_mode")}
