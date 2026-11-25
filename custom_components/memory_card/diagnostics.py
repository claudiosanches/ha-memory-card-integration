"""Diagnostics for Memory Card, without the token, anyone's play or user IDs."""

from collections.abc import Iterable
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import MemoryCardConfigEntry
from .hub import PERSON_KINDS


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MemoryCardConfigEntry
) -> dict[str, Any]:
    """Return what the integration holds for the app."""
    diagnostics: dict[str, Any] = {
        "entry": async_redact_data(dict(entry.data), {CONF_TOKEN}),
        "setup": entry.state.value,
    }
    # Set only once the app has sent its first state.
    hub = getattr(entry, "runtime_data", None)
    if hub is None:
        return diagnostics
    device = hub.device_info
    keys = _without_user_ids(hub.descriptions)
    return {
        **diagnostics,
        "connected": hub.connected,
        "device": {key: device.get(key) for key in ("name", "model", "sw_version")},
        "entities": sorted(keys.values()),
        "state": sorted(keys[key] for key in hub.state or {} if key in keys),
    }


def _without_user_ids(keys: Iterable[str]) -> dict[str, str]:
    """Each entity key, with the Home Assistant user ID in a person's keys numbered instead."""
    people: dict[str, int] = {}
    shown = {}
    for key in sorted(keys):
        kind = next((k for k in PERSON_KINDS if key.endswith(f"_{k}")), None)
        if kind is None or not key.startswith("person_"):
            shown[key] = key
            continue
        user_id = key.removeprefix("person_").removesuffix(f"_{kind}")
        shown[key] = f"person_{people.setdefault(user_id, len(people) + 1)}_{kind}"
    return shown
