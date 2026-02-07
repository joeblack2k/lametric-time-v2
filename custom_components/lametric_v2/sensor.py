from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import PERCENTAGE
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LametricV2Coordinator
from .entity import LametricV2Entity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: LametricV2Coordinator = hass.data["lametric_v2"][entry.entry_id]["coordinator"]
    async_add_entities([LametricWifiSignalSensor(coordinator)])


class LametricWifiSignalSensor(LametricV2Entity, SensorEntity):
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = "diagnostic"

    def __init__(self, coordinator: LametricV2Coordinator) -> None:
        super().__init__(coordinator, unique_key="wifi_signal", name="Wi-Fi signal")

    @property
    def native_value(self) -> int | None:
        wifi = self._device.get("wifi")
        if not isinstance(wifi, dict):
            return None

        # Firmware variants use "strength" or "signal_strength".
        for k in ("strength", "signal_strength"):
            v = wifi.get(k)
            if isinstance(v, (int, float)):
                return int(v)
        return None

