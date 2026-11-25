"""Diagnostics for Memory Card, without the token or anyone's play."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import MemoryCardConfigEntry


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
    return {
        **diagnostics,
        "connected": hub.connected,
        "device": {key: device.get(key) for key in ("name", "model", "sw_version")},
        "entities": sorted(hub.descriptions),
        "state": sorted(key for key in hub.state or {} if key in hub.descriptions),
    }
