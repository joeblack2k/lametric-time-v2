from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client, device_registry as dr
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import ConfigEntryNotReady

from .api import LametricV2Client
from .coordinator import LametricV2Coordinator
from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_DEFAULT_TTS_ENTITY_ID,
    CONF_HOST,
    CONF_VERIFY_SSL,
    DEFAULT_ICON,
    DEFAULT_TTS_ENTITY_ID,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)

_TTS_TIMEOUT_S = 12.0


def _get_entry_for_device_id(hass: HomeAssistant, device_id: str | None) -> ConfigEntry:
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise HomeAssistantError("No lametric_v2 entries configured")

    if device_id is None:
        if len(entries) == 1:
            return entries[0]
        raise HomeAssistantError("Multiple lametric_v2 devices configured; specify device_id")

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get(device_id)
    if device is None:
        raise HomeAssistantError(f"Unknown device_id {device_id}")

    for entry in entries:
        if entry.entry_id in device.config_entries:
            return entry
    raise HomeAssistantError("device_id does not belong to lametric_v2")


def _get_tts_sink_entity_id(hass: HomeAssistant, entry: ConfigEntry) -> str:
    ent_reg = async_get_entity_registry(hass)
    sink_unique_id = f"{entry.entry_id}-tts_sink"
    for ent in ent_reg.entities.values():
        if ent.platform == DOMAIN and ent.domain == "media_player" and ent.unique_id == sink_unique_id:
            return ent.entity_id
    # Fall back to the default slug if entity registry hasn't been created yet.
    return "media_player.lametric_tts_sink"


def _get_base_url(hass: HomeAssistant, entry: ConfigEntry) -> str | None:
    # Prefer user-configured URL because it must be reachable by the LaMetric device.
    base = (entry.data.get(CONF_BASE_URL) or "").strip()
    if base:
        return base.rstrip("/")
    # Fallbacks: may be unset; may be unreachable from the device.
    for cand in (hass.config.internal_url, hass.config.external_url):
        if isinstance(cand, str) and cand:
            return cand.rstrip("/")
    return None


def _absolutize_url(hass: HomeAssistant, entry: ConfigEntry, url: str) -> str:
    if url.startswith("http://") or url.startswith("https://"):
        return url
    base = _get_base_url(hass, entry)
    if not base:
        raise HomeAssistantError(
            "Need an absolute URL but no base_url is configured. "
            "Set base_url in the LaMetric v2 config flow options."
        )
    if not url.startswith("/"):
        url = "/" + url
    return base + url


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = aiohttp_client.async_get_clientsession(hass)
    client = LametricV2Client(
        session,
        host=entry.data[CONF_HOST],
        api_key=entry.data[CONF_API_KEY],
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, False),
    )
    # Prime endpoint map early to fail fast.
    try:
        await client.fetch_endpoints()
    except Exception as e:  # noqa: BLE001
        raise ConfigEntryNotReady from e

    coordinator = LametricV2Coordinator(hass, client)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as e:  # noqa: BLE001
        raise ConfigEntryNotReady from e

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "last_tts_media_url": None,
        "tts_event": asyncio.Event(),
    }

    # Ensure a device entry exists, so device_id selectors work.
    dev = coordinator.data or {}
    serial = dev.get("serial_number") if isinstance(dev.get("serial_number"), str) else None
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, serial or entry.data[CONF_HOST])},
        manufacturer="LaMetric",
        name=dev.get("name") if isinstance(dev.get("name"), str) else entry.title,
        model=dev.get("model") if isinstance(dev.get("model"), str) else None,
        sw_version=dev.get("os_version") if isinstance(dev.get("os_version"), str) else None,
        configuration_url=f"https://{entry.data[CONF_HOST]}:4343/",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, "play_mp3_url"):
        return

    async def play_mp3_url(call: ServiceCall) -> None:
        entry = _get_entry_for_device_id(hass, call.data.get("device_id"))
        client: LametricV2Client = hass.data[DOMAIN][entry.entry_id]["client"]

        text = call.data["text"]
        mp3_url = _absolutize_url(hass, entry, call.data["mp3_url"])
        icon = call.data.get("icon") or DEFAULT_ICON
        cycles = int(call.data.get("cycles") or 1)
        priority = call.data.get("priority") or "info"

        payload = {
            "priority": priority,
            "icon_type": "info",
            "model": {
                "cycles": cycles,
                "frames": [{"icon": icon, "text": text}],
                "sound": {
                    "url": mp3_url,
                    "type": "mp3",
                    "fallback": {"category": "notifications", "id": "cat"},
                },
            },
        }

        await client.post_notification(payload)

    async def dismiss_current(call: ServiceCall) -> None:
        entry = _get_entry_for_device_id(hass, call.data.get("device_id"))
        client: LametricV2Client = hass.data[DOMAIN][entry.entry_id]["client"]
        await client.dismiss_current()

    async def dismiss_all(call: ServiceCall) -> None:
        entry = _get_entry_for_device_id(hass, call.data.get("device_id"))
        client: LametricV2Client = hass.data[DOMAIN][entry.entry_id]["client"]
        await client.dismiss_all()

    async def play_tts(call: ServiceCall) -> None:
        entry = _get_entry_for_device_id(hass, call.data.get("device_id"))
        default_tts = entry.data.get(CONF_DEFAULT_TTS_ENTITY_ID, DEFAULT_TTS_ENTITY_ID)
        tts_entity_id = call.data.get("tts_entity_id") or default_tts
        message = call.data["message"]
        icon = call.data.get("icon") or DEFAULT_ICON
        priority = call.data.get("priority") or "info"

        # We generate a playable media URL by invoking tts.speak into our sink media_player.
        sink_entity_id = _get_tts_sink_entity_id(hass, entry)
        store: dict[str, Any] = hass.data[DOMAIN][entry.entry_id]
        ev: asyncio.Event = store["tts_event"]
        ev.clear()
        store["last_tts_media_url"] = None

        # Kick off TTS generation.
        data: dict[str, Any] = {
            "cache": True,
            "message": message,
            "media_player_entity_id": sink_entity_id,
        }
        voice = call.data.get("voice")
        if voice:
            data["options"] = {"voice": voice}

        await hass.services.async_call(
            "tts",
            "speak",
            service_data=data,
            target={"entity_id": tts_entity_id},
            blocking=True,
        )

        # Wait for the media_player to capture the resulting URL.
        try:
            await asyncio.wait_for(ev.wait(), timeout=_TTS_TIMEOUT_S)
        except TimeoutError as e:
            raise HomeAssistantError(
                "Timed out waiting for TTS media URL capture. "
                "If your TTS engine does not provide an HTTP URL to the media_player, "
                "this service won't work."
            ) from e

        media_url = store.get("last_tts_media_url")
        if not isinstance(media_url, str) or not media_url:
            raise HomeAssistantError("TTS media URL capture failed (empty media URL).")

        # Convert media-source URIs into real URLs when possible.
        if media_url.startswith("media-source://"):
            from homeassistant.components import media_source  # lazy import

            resolved = await media_source.async_resolve_media(hass, media_url, None)
            if not isinstance(resolved.url, str) or not resolved.url:
                raise HomeAssistantError("Failed to resolve media-source URL for TTS output.")
            media_url = resolved.url

        media_url = _absolutize_url(hass, entry, media_url)

        # Send as MP3 URL to LaMetric.
        client: LametricV2Client = hass.data[DOMAIN][entry.entry_id]["client"]
        payload = {
            "priority": priority,
            "icon_type": "info",
            "model": {
                "cycles": 1,
                "frames": [{"icon": icon, "text": message[:60]}],
                "sound": {
                    "url": media_url,
                    "type": "mp3",
                    "fallback": {"category": "notifications", "id": "cat"},
                },
            },
        }
        await client.post_notification(payload)

    async def show_setpoint_change(call: ServiceCall) -> None:
        entry = _get_entry_for_device_id(hass, call.data.get("device_id"))
        client: LametricV2Client = hass.data[DOMAIN][entry.entry_id]["client"]

        temp = float(call.data["temperature_c"])
        direction = call.data["direction"]
        priority = call.data.get("priority") or "info"
        cycles = int(call.data.get("cycles") or 2)

        # Pick icons. Defaults are intentionally generic; use the LaMetric icon gallery
        # to pick a red arrow icon and set it in the service call.
        arrow_up_icon = call.data.get("arrow_up_icon") or DEFAULT_ICON
        arrow_down_icon = call.data.get("arrow_down_icon") or DEFAULT_ICON
        arrow_icon = arrow_up_icon if direction == "up" else arrow_down_icon

        temp_text = f"{temp:.1f}C"
        frames = [
            {"icon": arrow_icon, "text": temp_text, "duration": 800},
            {"icon": arrow_icon, "text": " ", "duration": 250},
            {"icon": arrow_icon, "text": temp_text, "duration": 800},
        ]

        payload = {
            "priority": priority,
            "icon_type": "info",
            "model": {"cycles": cycles, "frames": frames},
        }
        await client.post_notification(payload)

    hass.services.async_register(
        DOMAIN,
        "play_mp3_url",
        play_mp3_url,
        schema=vol.Schema(
            {
                vol.Optional("device_id"): str,
                vol.Required("text"): str,
                vol.Required("mp3_url"): str,
                vol.Optional("icon"): str,
                vol.Optional("cycles"): vol.Coerce(int),
                vol.Optional("priority"): str,
            }
        ),
    )
    hass.services.async_register(DOMAIN, "dismiss_current", dismiss_current, schema=vol.Schema({vol.Optional("device_id"): str}))
    hass.services.async_register(DOMAIN, "dismiss_all", dismiss_all, schema=vol.Schema({vol.Optional("device_id"): str}))
    hass.services.async_register(
        DOMAIN,
        "play_tts",
        play_tts,
        schema=vol.Schema(
            {
                vol.Optional("device_id"): str,
                vol.Optional("tts_entity_id"): str,
                vol.Required("message"): str,
                vol.Optional("voice"): str,
                vol.Optional("icon"): str,
                vol.Optional("priority"): str,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "show_setpoint_change",
        show_setpoint_change,
        schema=vol.Schema(
            {
                vol.Optional("device_id"): str,
                vol.Required("temperature_c"): vol.Coerce(float),
                vol.Required("direction"): vol.In(["up", "down"]),
                vol.Optional("arrow_up_icon"): str,
                vol.Optional("arrow_down_icon"): str,
                vol.Optional("cycles"): vol.Coerce(int),
                vol.Optional("priority"): str,
            }
        ),
    )
