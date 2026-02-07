from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LametricV2Coordinator
from .entity import LametricV2Entity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: LametricV2Coordinator = hass.data["lametric_v2"][entry.entry_id]["coordinator"]
    async_add_entities(
        [
            LametricNextAppButton(coordinator),
            LametricPrevAppButton(coordinator),
            LametricDismissCurrentButton(coordinator),
            LametricDismissAllButton(coordinator),
        ]
    )


class LametricNextAppButton(LametricV2Entity, ButtonEntity):
    def __init__(self, coordinator: LametricV2Coordinator) -> None:
        super().__init__(coordinator, unique_key="app_next", name="Next app")

    async def async_press(self) -> None:
        await self.coordinator.client.app_next()


class LametricPrevAppButton(LametricV2Entity, ButtonEntity):
    def __init__(self, coordinator: LametricV2Coordinator) -> None:
        super().__init__(coordinator, unique_key="app_prev", name="Previous app")

    async def async_press(self) -> None:
        await self.coordinator.client.app_prev()


class LametricDismissCurrentButton(LametricV2Entity, ButtonEntity):
    def __init__(self, coordinator: LametricV2Coordinator) -> None:
        super().__init__(coordinator, unique_key="dismiss_current", name="Dismiss current notification")

    async def async_press(self) -> None:
        await self.coordinator.client.dismiss_current()


class LametricDismissAllButton(LametricV2Entity, ButtonEntity):
    def __init__(self, coordinator: LametricV2Coordinator) -> None:
        super().__init__(coordinator, unique_key="dismiss_all", name="Dismiss all notifications")

    async def async_press(self) -> None:
        await self.coordinator.client.dismiss_all()

