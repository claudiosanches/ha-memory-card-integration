"""Constants for the Memory Card integration."""

from datetime import timedelta
import re

DOMAIN = "memory_card"

# The feed messages this integration understands.
API_VERSION = 1

CONF_SLUG = "slug"

# Entities the integration has translated names for; others use the app's name.
KNOWN_KEYS = frozenset(
    {
        "games",
        "copies",
        "wishlist",
        "backlog",
        "playing",
        "last_played",
        "last_added",
        "pick",
        "roll_pick",
    }
)

# Keys become entity IDs, so they follow Home Assistant's rules for those.
VALID_KEY = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*")
KEY_MAX = 64

# The app pings every 30 seconds.
READ_TIMEOUT = timedelta(seconds=90)
RETRY_MIN = timedelta(seconds=5)
RETRY_MAX = timedelta(seconds=60)
SETUP_TIMEOUT = timedelta(seconds=15)
REQUEST_TIMEOUT = timedelta(seconds=10)
