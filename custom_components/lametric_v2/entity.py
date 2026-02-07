from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LametricV2Coordinator


class LametricV2Entity(CoordinatorEntity[LametricV2Coordinator]):
    def __init__(self, coordinator: LametricV2Coordinator, *, unique_key: str, name: str) -> None:
        super().__init__(coordinator)
        self._unique_key = unique_key
        self._attr_name = name

        serial = self._serial_number
        if serial:
            self._attr_unique_id = f"{serial}-{unique_key}"
        else:
            self._attr_unique_id = f"{coordinator.client.host}-{unique_key}"

    @property
    def _device(self) -> dict[str, Any]:
        return self.coordinator.data or {}

    @property
    def _serial_number(self) -> str | None:
        sn = self._device.get("serial_number")
        return sn if isinstance(sn, str) else None

    @property
    def device_info(self) -> DeviceInfo:
        dev = self._device
        serial = self._serial_number or self.coordinator.client.host
        return DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=dev.get("name") if isinstance(dev.get("name"), str) else "LaMetric",
            manufacturer="LaMetric",
            model=dev.get("model") if isinstance(dev.get("model"), str) else None,
            sw_version=dev.get("os_version") if isinstance(dev.get("os_version"), str) else None,
            configuration_url=f"https://{self.coordinator.client.host}:4343/",
        )

