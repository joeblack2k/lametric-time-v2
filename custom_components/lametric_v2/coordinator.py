from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import LametricV2Client
from .const import DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN


_LOGGER = logging.getLogger(__name__)


class LametricV2Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, client: LametricV2Client) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{client.host}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        # Single call includes audio/display/wifi/bluetooth etc on this firmware.
        return await self.client.get_device()
