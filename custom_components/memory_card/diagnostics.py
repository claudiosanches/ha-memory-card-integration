"""Diagnostics for Memory Card, without the token."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import MemoryCardConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MemoryCardConfigEntry
) -> dict[str, Any]:
    """Return what the integration holds for the app."""
    hub = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), {CONF_TOKEN}),
        "connected": hub.connected,
        "device": hub.device,
        "entities": sorted(hub.descriptions),
        "state": hub.state,
    }
