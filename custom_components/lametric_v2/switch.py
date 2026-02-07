from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LametricV2Coordinator
from .entity import LametricV2Entity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: LametricV2Coordinator = hass.data["lametric_v2"][entry.entry_id]["coordinator"]
    async_add_entities([LametricBluetoothSwitch(coordinator)])


class LametricBluetoothSwitch(LametricV2Entity, SwitchEntity):
    def __init__(self, coordinator: LametricV2Coordinator) -> None:
        super().__init__(coordinator, unique_key="bluetooth", name="Bluetooth")

    @property
    def is_on(self) -> bool | None:
        bt = self._device.get("bluetooth")
        active = bt.get("active") if isinstance(bt, dict) else None
        return bool(active) if isinstance(active, bool) else None

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.client.set_bluetooth({"active": True})
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.client.set_bluetooth({"active": False})
        await self.coordinator.async_request_refresh()

