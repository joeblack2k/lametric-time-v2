from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LametricV2Coordinator
from .entity import LametricV2Entity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: LametricV2Coordinator = hass.data["lametric_v2"][entry.entry_id]["coordinator"]
    async_add_entities(
        [
            LametricBrightnessNumber(coordinator),
            LametricVolumeNumber(coordinator),
        ]
    )


class LametricBrightnessNumber(LametricV2Entity, NumberEntity):
    _attr_native_min_value = 2
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator: LametricV2Coordinator) -> None:
        super().__init__(coordinator, unique_key="brightness", name="Brightness")

    @property
    def native_value(self) -> float | None:
        disp = self._device.get("display")
        if isinstance(disp, dict) and isinstance(disp.get("brightness"), (int, float)):
            return float(disp["brightness"])
        return None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.client.set_display({"brightness": int(value)})
        await self.coordinator.async_request_refresh()


class LametricVolumeNumber(LametricV2Entity, NumberEntity):
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator: LametricV2Coordinator) -> None:
        super().__init__(coordinator, unique_key="volume", name="Volume")

    @property
    def native_value(self) -> float | None:
        aud = self._device.get("audio")
        if isinstance(aud, dict) and isinstance(aud.get("volume"), (int, float)):
            return float(aud["volume"])
        return None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.client.set_audio({"volume": int(value)})
        await self.coordinator.async_request_refresh()

