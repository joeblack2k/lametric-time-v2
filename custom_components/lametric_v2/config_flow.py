from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from aiohttp import ClientResponseError

from .api import LametricV2Client, LametricV2Error
from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_DEFAULT_TTS_ENTITY_ID,
    CONF_HOST,
    CONF_VERIFY_SSL,
    DEFAULT_TTS_ENTITY_ID,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

def _read_keys_file(hass: HomeAssistant) -> dict[str, str]:
    """Read KEY=\"VALUE\" lines from a local keys.txt (best-effort).

    Optional convenience: if you create one of these files in your HA config dir:
    - /config/lametric/keys.txt
    - /config/lametric_keys.txt
    and include API="...device_api_key...", the config flow will prefill the API key.
    """
    candidates = [
        Path(hass.config.path("lametric", "keys.txt")),
        Path(hass.config.path("lametric_keys.txt")),
    ]
    for path in candidates:
        try:
            if not path.exists():
                continue
            out: dict[str, str] = {}
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("\"")
                if k:
                    out[k] = v
            return out
        except Exception:  # noqa: BLE001
            continue
    return {}


def _normalize_host(raw: str) -> str:
    raw = raw.strip()
    # Accept full URL (https://ip:4343/...) or host:port.
    if "://" in raw:
        try:
            from yarl import URL

            u = URL(raw)
            if u.host:
                return u.host
        except Exception:  # noqa: BLE001
            pass
    # Strip port if user entered host:port
    if raw.count(":") == 1 and raw.rsplit(":", 1)[-1].isdigit():
        return raw.rsplit(":", 1)[0]
    return raw


async def _validate(hass: HomeAssistant, host: str, api_key: str, verify_ssl: bool) -> tuple[str | None, str | None]:
    session = aiohttp_client.async_get_clientsession(hass)
    client = LametricV2Client(session, host=host, api_key=api_key, verify_ssl=verify_ssl)
    await client.fetch_endpoints()
    device = await client.get_device()
    # Common keys: serial_number, name, model
    unique_id = device.get("serial_number") if isinstance(device.get("serial_number"), str) else None
    title = device.get("name") if isinstance(device.get("name"), str) else None
    return unique_id, title


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            host = _normalize_host(user_input[CONF_HOST])
            api_key = (user_input[CONF_API_KEY] or "").strip()
            verify_ssl = user_input[CONF_VERIFY_SSL]

            try:
                unique_id, title = await _validate(self.hass, host, api_key, verify_ssl)
            except ClientResponseError as e:
                _LOGGER.warning(
                    "LaMetric v2 config flow HTTP error host=%s status=%s message=%s",
                    host,
                    e.status,
                    getattr(e, "message", None),
                )
                if e.status in (401, 403):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except (LametricV2Error, Exception):  # noqa: BLE001 - config flow should be resilient
                _LOGGER.exception("LaMetric v2 config flow failed host=%s", host)
                errors["base"] = "cannot_connect"
            else:
                if unique_id:
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                data = {
                    CONF_HOST: host,
                    CONF_API_KEY: api_key,
                    CONF_VERIFY_SSL: verify_ssl,
                    CONF_BASE_URL: (user_input.get(CONF_BASE_URL) or "").strip(),
                    CONF_DEFAULT_TTS_ENTITY_ID: (user_input.get(CONF_DEFAULT_TTS_ENTITY_ID) or DEFAULT_TTS_ENTITY_ID).strip(),
                }
                return self.async_create_entry(title=title or host, data=data)

        keys = _read_keys_file(self.hass)
        default_api_key = keys.get("API", "")

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_API_KEY, default=default_api_key): str,
                vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
                vol.Optional(CONF_BASE_URL, default=""): str,
                vol.Optional(CONF_DEFAULT_TTS_ENTITY_ID, default=DEFAULT_TTS_ENTITY_ID): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
