"""The Memory Card integration: the app's sensors without an MQTT broker."""

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .client import MemoryCardClient
from .const import DOMAIN, SETUP_TIMEOUT
from .hub import MemoryCardHub
from .services import async_setup_services

PLATFORMS = [Platform.BUTTON, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type MemoryCardConfigEntry = ConfigEntry[MemoryCardHub]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the actions."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MemoryCardConfigEntry) -> bool:
    """Open the feed and add the entities the app describes."""
    client = MemoryCardClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_TOKEN],
    )
    hub = MemoryCardHub(hass, entry, client)
    hub.start()
    try:
        async with asyncio.timeout(SETUP_TIMEOUT.total_seconds()):
            await hub.wait_ready()
    except TimeoutError as err:
        await hub.stop()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err
    entry.runtime_data = hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MemoryCardConfigEntry) -> bool:
    """Close the feed."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.stop()
    return unloaded
