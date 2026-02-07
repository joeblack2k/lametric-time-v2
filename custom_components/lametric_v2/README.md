# LaMetric Time (Device API v2) - Custom Component

This custom component targets LaMetric TIME's local **Device API v2** (HTTPS `:4343`).

It exists to make it easy to use newer v2 notification features (notably **MP3 sound URLs**) and to provide a small
bridge from Home Assistant **TTS entities** (e.g. `tts.google_ai_tts`) into a URL LaMetric can fetch.

## What We Probed On Your Device

Using the probe script (see repo root `tools/lametric_v2_probe.py`) against device firmware `2.3.9`, we confirmed:

- `/api/v2` reports `api_version: 2.3.0`
- endpoint map includes:
  - `device_url`, `display_url`, `audio_url`, `wifi_url`, `bluetooth_url`
  - `notifications_url`, `current_notification_url`, `concrete_notification_url`
  - `apps_list_url`, `apps_get_url`, `apps_switch_next_url`, `apps_switch_prev_url`, `apps_action_url`, `apps_switch_url`
  - `widget_update_url`

Probe outputs are written to the output directory you pass in (defaults to a local folder).

## Services

- `lametric_v2.play_mp3_url`: display text + play an MP3 from a URL (`sound.url`).
- `lametric_v2.play_tts`: generate audio using a HA TTS entity by calling `tts.speak` into a dummy media_player, capture the
  resulting media URL, and play it as an MP3 notification on LaMetric.
- `lametric_v2.show_setpoint_change`: show a simple "animated" notification by alternating frames.
- `lametric_v2.dismiss_current`, `lametric_v2.dismiss_all`

## Notes

LaMetric needs to **fetch the MP3 URL itself**. If you provide URLs like `/local/doorbell.mp3`, the integration must
convert them into an absolute URL. Configure `base_url` in the config flow to a URL reachable by the LaMetric device,
for example `http://<homeassistant-ip>:8123`.
