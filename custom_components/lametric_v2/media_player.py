from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


@dataclass
class _TtsCapture:
    media_content_id: str | None = None
    media_content_type: str | None = None
    event: asyncio.Event | None = None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([LametricTtsSink(entry)])


class LametricTtsSink(MediaPlayerEntity):
    """A dummy media_player that captures TTS-generated media URLs.

    We use this to bridge HA TTS engines into a plain HTTP URL we can hand
    to LaMetric's "sound.url" mp3 notification field.
    """

    _attr_supported_features = MediaPlayerEntityFeature.PLAY_MEDIA
    _attr_media_content_type = None
    _attr_media_content_id = None
    _attr_available = True

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}-tts_sink"
        self._attr_name = "LaMetric TTS Sink"
        self._capture = _TtsCapture(event=asyncio.Event())
        self._attr_media_content_id = None
        self._attr_media_content_type = None
        self._state = MediaPlayerState.IDLE

    @property
    def state(self) -> MediaPlayerState:
        return self._state

    @property
    def capture(self) -> _TtsCapture:
        return self._capture

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        # Home Assistant may pass MediaType.MUSIC or MediaType.AUDIO for TTS.
        self._capture.media_content_type = media_type
        self._capture.media_content_id = media_id
        self._attr_media_content_type = media_type
        self._attr_media_content_id = media_id
        # Expose the last URL to the integration so services can wait for it deterministically.
        store = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if isinstance(store, dict):
            store["last_tts_media_url"] = media_id
            ev = store.get("tts_event")
            if isinstance(ev, asyncio.Event):
                ev.set()
        if self._capture.event:
            self._capture.event.set()
        self.async_write_ha_state()

    async def async_get_last_media(self, timeout: float = 10.0) -> str | None:
        self._capture.event = asyncio.Event()
        try:
            await asyncio.wait_for(self._capture.event.wait(), timeout=timeout)
        except TimeoutError:
            return None
        return self._capture.media_content_id
