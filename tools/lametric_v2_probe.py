#!/usr/bin/env python3
"""
Probe LaMetric TIME Device API v2 and dump available endpoints/capabilities.

This script is intentionally stdlib-only (no requests/aiohttp), because this
machine's Python environment doesn't have extra packages installed.

It will:
1) Load host/api_key from a Home Assistant config entry (domain=lametric) if available.
2) Call GET /api/v2 (trying common base URLs) and write the raw JSON to a file.
3) Optionally send a small test notification.

Outputs are written to .lametric_probe by default.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable


DEFAULT_STORAGE_CONFIG_ENTRIES = Path(".storage/core.config_entries")
DEFAULT_OUT_DIR = Path(".lametric_probe")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_lametric_entry(storage_config_entries: Path) -> dict[str, Any] | None:
    if not storage_config_entries.exists():
        return None

    data = _load_json(storage_config_entries)
    if not isinstance(data, dict):
        return None

    entries = data.get("data", {}).get("entries", [])
    if not isinstance(entries, list):
        return None

    for entry in entries:
        if isinstance(entry, dict) and entry.get("domain") == "lametric":
            return entry
    return None


def _basic_auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _urlopen_json(
    url: str,
    headers: dict[str, str],
    method: str = "GET",
    data: dict[str, Any] | None = None,
    timeout: float = 8.0,
    insecure_tls: bool = True,
) -> Any:
    body: bytes | None = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers = {
            **headers,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    ctx = None
    if url.startswith("https://") and insecure_tls:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        raw = resp.read()
        if not raw:
            return None
        return json.loads(raw.decode("utf-8"))


def _try_api_v2(
    host: str,
    headers: dict[str, str],
    insecure_tls: bool,
) -> tuple[str, dict[str, Any]]:
    candidates = [
        f"https://{host}:4343",
        f"http://{host}:8080",
        f"https://{host}",
        f"http://{host}",
    ]

    last_err = None
    for base in candidates:
        url = f"{base}/api/v2"
        try:
            payload = _urlopen_json(url, headers=headers, insecure_tls=insecure_tls)
            if isinstance(payload, dict) and payload.get("api_version"):
                return base, payload
            # Still accept dict payloads; some firmware might not include api_version key.
            if isinstance(payload, dict):
                return base, payload
        except Exception as e:  # noqa: BLE001 (probe tool)
            last_err = e
            continue

    raise RuntimeError(f"Failed to GET /api/v2 from host={host}. Last error: {last_err!r}")


def _safe_filename(s: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in s)[:180]


def _dump_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _scrub_secret(s: str, secret: str) -> str:
    if not secret:
        return s
    return s.replace(secret, "***")


def _endpoint_urls(api_v2: dict[str, Any]) -> dict[str, str]:
    """
    Device API returns an endpoint map. Different docs/firmware variants
    use different keys. We'll pull anything that looks like a URL.
    """
    out: dict[str, str] = {}
    for k, v in api_v2.items():
        if isinstance(v, str) and (v.startswith("http://") or v.startswith("https://")):
            out[k] = v
        if isinstance(v, dict):
            for k2, v2 in v.items():
                if isinstance(v2, str) and (v2.startswith("http://") or v2.startswith("https://")):
                    out[f"{k}.{k2}"] = v2
    return out


def _best_guess_endpoint(endpoints: dict[str, str], suffix: str) -> str | None:
    # Prefer exact-ish matches, but accept "device.<thing>" forms too.
    suffix = suffix.lstrip("/")
    for v in endpoints.values():
        if v.rstrip("/").endswith("/" + suffix.rstrip("/")):
            return v
    return None


def _probe_some_endpoints(
    base: str,
    api_v2: dict[str, Any],
    headers: dict[str, str],
    insecure_tls: bool,
) -> dict[str, Any]:
    endpoints = _endpoint_urls(api_v2)
    results: dict[str, Any] = {"base_url": base, "probed": {}}

    guesses = {
        "device.display": "/api/v2/device/display",
        "device.audio": "/api/v2/device/audio",
        "device.notifications": "/api/v2/device/notifications",
        "device.apps": "/api/v2/device/apps",
    }

    for name, path in guesses.items():
        url = _best_guess_endpoint(endpoints, path) or (base.rstrip("/") + path)
        try:
            results["probed"][name] = _urlopen_json(url, headers=headers, insecure_tls=insecure_tls)
        except urllib.error.HTTPError as e:
            results["probed"][name] = {"_error": f"HTTP {e.code}", "_reason": getattr(e, "reason", None)}
        except Exception as e:  # noqa: BLE001
            results["probed"][name] = {"_error": repr(e)}

    return results


def _send_test_notification(
    base: str,
    headers: dict[str, str],
    insecure_tls: bool,
    text: str,
) -> Any:
    url = f"{base.rstrip('/')}/api/v2/device/notifications"
    payload = {
        "priority": "info",
        "icon_type": "info",
        "model": {
            "cycles": 1,
            "frames": [{"icon": "i3092", "text": text}],
        },
    }
    return _urlopen_json(url, headers=headers, method="POST", data=payload, insecure_tls=insecure_tls)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--host", help="LaMetric host/IP. If omitted, read from HA .storage config entry.")
    p.add_argument("--api-key", help="LaMetric device API key. If omitted, read from HA .storage config entry.")
    p.add_argument(
        "--storage-config-entries",
        default=str(DEFAULT_STORAGE_CONFIG_ENTRIES),
        help="Path to Home Assistant .storage/core.config_entries JSON",
    )
    p.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help="Directory to write probe outputs",
    )
    p.add_argument(
        "--insecure-tls",
        action="store_true",
        default=True,
        help="Disable TLS verification (device often uses self-signed cert)",
    )
    p.add_argument("--send-test", action="store_true", help="POST a small test notification")
    p.add_argument("--test-text", default="LaMetric v2 probe OK", help="Text for test notification")
    args = p.parse_args(argv)

    storage_path = Path(args.storage_config_entries)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    host = args.host
    api_key = args.api_key

    if not host or not api_key:
        entry = _find_lametric_entry(storage_path)
        if not entry:
            print("Could not find domain=lametric config entry and --host/--api-key not provided.", file=sys.stderr)
            return 2
        data = entry.get("data", {})
        host = host or data.get("host")
        api_key = api_key or data.get("api_key")

    if not host or not api_key:
        print("Missing host or api_key.", file=sys.stderr)
        return 2

    headers = {
        "Authorization": _basic_auth_header("dev", api_key),
        "Accept": "application/json",
    }

    base, api_v2 = _try_api_v2(host, headers=headers, insecure_tls=args.insecure_tls)
    now = time.strftime("%Y%m%d-%H%M%S")
    api_path = out_dir / f"lametric_api_v2_{_safe_filename(host)}_{now}.json"
    _dump_json(api_path, api_v2)

    probe = _probe_some_endpoints(base, api_v2, headers=headers, insecure_tls=args.insecure_tls)
    probe_path = out_dir / f"lametric_probe_{_safe_filename(host)}_{now}.json"
    _dump_json(probe_path, probe)

    if args.send_test:
        try:
            resp = _send_test_notification(base, headers=headers, insecure_tls=args.insecure_tls, text=args.test_text)
        except Exception as e:  # noqa: BLE001
            resp = {"_error": repr(e)}
        test_path = out_dir / f"lametric_test_notification_{_safe_filename(host)}_{now}.json"
        _dump_json(test_path, resp)

    # Print minimal summary without leaking the API key.
    endpoints = _endpoint_urls(api_v2)
    print(json.dumps(
        {
            "host": host,
            "base_url": base,
            "api_version": api_v2.get("api_version"),
            "endpoints_found": sorted(endpoints.keys())[:50],
            "endpoints_count": len(endpoints),
            "wrote": [str(api_path), str(probe_path)],
        },
        indent=2,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

