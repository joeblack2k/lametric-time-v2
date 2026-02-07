# LaMetric Time (Device API v2) for Home Assistant

Custom Home Assistant integration for LaMetric TIME using the **local Device API v2**.

## Why This Exists

Home Assistant's built-in LaMetric integration is great for basic device control, but LaMetric's newer **Device API v2** exposes functionality that isn't always convenient to automate from HA.

This custom component was created to:

- Use the Device API v2 endpoint map (`GET /api/v2`) for capability detection.
- Support **MP3 playback via notification sound URL** (`sound: { url: ..., type: mp3 }`).
- Provide a practical bridge from HA **TTS engines** (e.g. Gemini TTS via `tts.google_ai_tts`) to a URL LaMetric can fetch.

## What You Get

### Services

- `lametric_v2.play_mp3_url`
  - Show a notification and play an MP3 from a URL.
- `lametric_v2.play_tts`
  - Generate speech using a HA TTS entity and play it on LaMetric as an MP3 notification.
- `lametric_v2.show_setpoint_change`
  - Simple multi-frame "animation" (e.g. arrow up/down + temperature text).
- `lametric_v2.dismiss_current`, `lametric_v2.dismiss_all`

### Entities

- Numbers: Brightness, Volume
- Select: Brightness mode (auto/manual)
- Switch: Bluetooth
- Sensor: Wi-Fi signal
- Buttons: Next app, Previous app, Dismiss current notification, Dismiss all notifications
- Media player: `LaMetric TTS Sink` (internal helper used to capture the TTS-generated media URL)

## Installation (HACS)

1. HACS → Integrations → 3-dots menu → **Custom repositories**
2. Add this repository URL as category **Integration**
3. Install, then restart Home Assistant
4. Add the integration: Settings → Devices & services → Add integration → **LaMetric Time (Device API v2)**

### Direct HACS Link

If you are logged into Home Assistant in a browser:

- `https://my.home-assistant.io/redirect/hacs_repository/?owner=joeblack2k&repository=lametric-time-v2&category=integration`

## Configuration Notes

### `base_url` is important

LaMetric downloads the MP3 itself, so the MP3 URL must be reachable by the LaMetric device on your network.

Examples:

- Good: `http://<homeassistant-ip>:8123/local/doorbell.mp3`
- Good: `http://<homeassistant-ip>:8123/api/tts_proxy/<file>.mp3`

In the config flow, set **Home Assistant base URL (reachable by LaMetric)** to something the LaMetric can reach.

### Optional convenience: `keys.txt`

If you create `/config/lametric/keys.txt` or `/config/lametric_keys.txt` with:

- `API="<device_api_key>"`

then the config flow will prefill the API key.

## Examples

### Play a local MP3 (`/config/www/doorbell.mp3`)

```yaml
service: lametric_v2.play_mp3_url
data:
  text: "Ding dong"
  mp3_url: "/local/doorbell.mp3"
```

### TTS: "Het is nu 600 graden"

```yaml
service: lametric_v2.play_tts
data:
  tts_entity_id: tts.google_ai_tts
  message: "Het is nu 600 graden"
```

### Animated arrow up + temperature

```yaml
service: lametric_v2.show_setpoint_change
data:
  direction: up
  temperature_c: 21.1
  cycles: 3
```

## Tools

A probe script is included for debugging your device API:

- `tools/lametric_v2_probe.py`

It is stdlib-only and can dump `/api/v2` plus key endpoints.

## Disclaimer

This is a community custom integration and is not affiliated with Home Assistant or LaMetric.
