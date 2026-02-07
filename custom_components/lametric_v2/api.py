from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiohttp import BasicAuth, ClientSession
from yarl import URL


class LametricV2Error(Exception):
    pass


@dataclass(frozen=True)
class LametricEndpoints:
    base_url: str
    api_version: str | None
    endpoints: dict[str, str]


class LametricV2Client:
    """Minimal LaMetric Device API v2 client."""

    def __init__(self, session: ClientSession, *, host: str, api_key: str, verify_ssl: bool) -> None:
        self._session = session
        self._host = host
        self._api_key = api_key
        self._verify_ssl = verify_ssl
        self._endpoints: LametricEndpoints | None = None

    @property
    def host(self) -> str:
        return self._host

    async def _request_json(self, method: str, url: str, *, json_data: Any | None = None) -> Any:
        auth = BasicAuth("dev", self._api_key)
        ssl_param: ssl.SSLContext | bool | None
        if url.startswith("https://"):
            # Prefer aiohttp's ssl=False for "no verify" to avoid creating SSLContext in event loop.
            ssl_param = None if self._verify_ssl else False
        else:
            ssl_param = None
        async with self._session.request(
            method,
            url,
            json=json_data,
            auth=auth,
            ssl=ssl_param,
            headers={"Accept": "application/json"},
        ) as resp:
            resp.raise_for_status()
            if resp.content_type and "json" in resp.content_type:
                return await resp.json()
            # Some endpoints can return empty body on success.
            txt = await resp.text()
            return txt or None

    async def fetch_endpoints(self) -> LametricEndpoints:
        # Most devices expose HTTPS 4343, but we try several candidates to be resilient.
        candidates = [
            f"https://{self._host}:4343",
            f"http://{self._host}:8080",
            f"https://{self._host}",
            f"http://{self._host}",
        ]

        last_err: Exception | None = None
        payload: Any = None
        base: str | None = None

        for cand in candidates:
            try:
                payload = await self._request_json("GET", f"{cand}/api/v2")
                if isinstance(payload, dict) and "endpoints" in payload:
                    base = cand
                    break
                if isinstance(payload, dict):
                    base = cand
                    break
            except Exception as e:  # noqa: BLE001 - discovery should be resilient
                last_err = e
                continue

        if base is None or not isinstance(payload, dict) or "endpoints" not in payload:
            raise LametricV2Error(f"Failed to fetch /api/v2 endpoint map (last_err={last_err!r})")

        endpoints = payload.get("endpoints") or {}
        api_version = payload.get("api_version")
        if not isinstance(endpoints, dict):
            raise LametricV2Error("Unexpected endpoints map")

        self._endpoints = LametricEndpoints(
            base_url=base,
            api_version=api_version if isinstance(api_version, str) else None,
            endpoints={k: v for k, v in endpoints.items() if isinstance(k, str) and isinstance(v, str)},
        )
        return self._endpoints

    async def ensure_endpoints(self) -> LametricEndpoints:
        if self._endpoints is None:
            return await self.fetch_endpoints()
        return self._endpoints

    async def get_device(self) -> dict[str, Any]:
        eps = await self.ensure_endpoints()
        url = eps.endpoints.get("device_url") or f"{eps.base_url}/api/v2/device"
        data = await self._request_json("GET", url)
        if not isinstance(data, dict):
            raise LametricV2Error("Unexpected /device response shape")
        return data

    async def post_notification(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        eps = await self.ensure_endpoints()
        url = eps.endpoints.get("notifications_url") or f"{eps.base_url}/api/v2/device/notifications"
        data = await self._request_json("POST", url, json_data=payload)
        return data if isinstance(data, dict) else None

    async def dismiss_current(self) -> None:
        eps = await self.ensure_endpoints()
        url = eps.endpoints.get("current_notification_url") or f"{eps.base_url}/api/v2/device/notifications/current"
        await self._request_json("DELETE", url)

    async def dismiss_all(self) -> None:
        eps = await self.ensure_endpoints()
        url = eps.endpoints.get("notifications_url") or f"{eps.base_url}/api/v2/device/notifications"
        await self._request_json("DELETE", url)

    async def app_next(self) -> None:
        eps = await self.ensure_endpoints()
        url = eps.endpoints.get("apps_switch_next_url") or f"{eps.base_url}/api/v2/device/apps/next"
        await self._request_json("POST", url)

    async def app_prev(self) -> None:
        eps = await self.ensure_endpoints()
        url = eps.endpoints.get("apps_switch_prev_url") or f"{eps.base_url}/api/v2/device/apps/prev"
        await self._request_json("POST", url)

    async def set_display(self, data: dict[str, Any]) -> None:
        eps = await self.ensure_endpoints()
        url = eps.endpoints.get("display_url") or f"{eps.base_url}/api/v2/device/display"
        await self._request_json("PUT", url, json_data=data)

    async def set_audio(self, data: dict[str, Any]) -> None:
        eps = await self.ensure_endpoints()
        url = eps.endpoints.get("audio_url") or f"{eps.base_url}/api/v2/device/audio"
        await self._request_json("PUT", url, json_data=data)

    async def set_bluetooth(self, data: dict[str, Any]) -> None:
        eps = await self.ensure_endpoints()
        url = eps.endpoints.get("bluetooth_url") or f"{eps.base_url}/api/v2/device/bluetooth"
        await self._request_json("PUT", url, json_data=data)


def coerce_https_url(base_url: str, path: str) -> str:
    """Join base_url + path safely."""
    return str(URL(base_url).with_path(path))
