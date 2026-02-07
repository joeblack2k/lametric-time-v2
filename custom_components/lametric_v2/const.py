DOMAIN = "lametric_v2"

CONF_HOST = "host"
CONF_API_KEY = "api_key"
CONF_VERIFY_SSL = "verify_ssl"
CONF_BASE_URL = "base_url"

DEFAULT_VERIFY_SSL = False

# TTS glue: optional service that can attempt to generate a URL for a given TTS entity.
CONF_DEFAULT_TTS_ENTITY_ID = "default_tts_entity_id"
DEFAULT_TTS_ENTITY_ID = "tts.google_ai_tts"

# Default icon used in examples (matches your existing rest_command).
DEFAULT_ICON = "i3092"

PLATFORMS: list[str] = ["media_player", "number", "select", "switch", "sensor", "button"]

# Coordinator refresh. We can keep this fairly low; LaMetric is local and fast.
DEFAULT_SCAN_INTERVAL_SECONDS = 30
