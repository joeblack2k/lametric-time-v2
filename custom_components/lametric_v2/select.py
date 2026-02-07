from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LametricV2Coordinator
from .entity import LametricV2Entity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: LametricV2Coordinator = hass.data["lametric_v2"][entry.entry_id]["coordinator"]
    async_add_entities([LametricBrightnessModeSelect(coordinator)])


class LametricBrightnessModeSelect(LametricV2Entity, SelectEntity):
    _attr_options = ["auto", "manual"]

    def __init__(self, coordinator: LametricV2Coordinator) -> None:
        super().__init__(coordinator, unique_key="brightness_mode", name="Brightness mode")

    @property
    def current_option(self) -> str | None:
        disp = self._device.get("display")
        mode = disp.get("brightness_mode") if isinstance(disp, dict) else None
        return mode if isinstance(mode, str) else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.client.set_display({"brightness_mode": option})
        await self.coordinator.async_request_refresh()

