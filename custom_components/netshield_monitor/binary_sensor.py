"""Binary sensors for NetShield Monitor."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NetShieldConfigEntry
from .coordinator import NetShieldCoordinator
from .entity import NetShieldEntity


async def async_setup_entry(hass: HomeAssistant, entry: NetShieldConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    c = entry.runtime_data
    async_add_entities([BackendOnline(c), SecurityAlert(c), SourceProblem(c)])


class BackendOnline(NetShieldEntity, BinarySensorEntity):
    _attr_translation_key = "backend_online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: NetShieldCoordinator) -> None:
        super().__init__(coordinator, "backend_online")
        self.entity_id = "binary_sensor.netshield_backend_online"

    @property
    def available(self) -> bool:  # must stay available to report "offline"
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success


class SecurityAlert(NetShieldEntity, BinarySensorEntity):
    _attr_translation_key = "security_alert"
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, coordinator: NetShieldCoordinator) -> None:
        super().__init__(coordinator, "security_alert")
        self.entity_id = "binary_sensor.netshield_security_alert"

    @property
    def is_on(self) -> bool:
        return (self.coordinator.data or {}).get("security_status", {}).get("level") == "critical"

    @property
    def extra_state_attributes(self):
        st = (self.coordinator.data or {}).get("security_status", {})
        return {"level": st.get("level"), "reasons": [r.get("code") for r in st.get("reasons", [])]}


class SourceProblem(NetShieldEntity, BinarySensorEntity):
    _attr_translation_key = "source_problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: NetShieldCoordinator) -> None:
        super().__init__(coordinator, "source_problem")
        self.entity_id = "binary_sensor.netshield_source_problem"

    @property
    def is_on(self) -> bool:
        return any(s.get("status") == "error" for s in (self.coordinator.data or {}).get("sources", []))

    @property
    def extra_state_attributes(self):
        return {"sources": {s["name"]: s.get("status") for s in (self.coordinator.data or {}).get("sources", [])}}
