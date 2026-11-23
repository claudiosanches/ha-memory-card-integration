"""Keeps the feed open and holds what the app last sent."""

import asyncio
from contextlib import aclosing
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .client import MemoryCardClient, MemoryCardError, Unauthorized
from .const import API_VERSION, CONF_SLUG, DOMAIN, RETRY_MAX, RETRY_MIN, VALID_KEY

_LOGGER = logging.getLogger(__name__)

PLATFORMS_SENT = ("sensor", "button")
# Far more than the app sends, so a broken feed cannot flood the registry.
ENTITIES_MAX = 64


class UnsupportedApi(MemoryCardError):
    """The app speaks a newer feed than this integration reads."""


@dataclass(frozen=True, slots=True)
class EntityDescription:
    """One entity as the app describes it."""

    key: str
    platform: str
    name: str
    icon: str | None
    unit: str | None
    state_class: str | None
    attributes: bool


def _description(raw: Any) -> EntityDescription | None:
    if not isinstance(raw, dict):
        return None
    key = raw.get("key")
    platform = raw.get("platform")
    if not isinstance(key, str) or not VALID_KEY.match(key):
        return None
    if platform not in PLATFORMS_SENT:
        return None

    def text(field: str) -> str | None:
        value = raw.get(field)
        return value if isinstance(value, str) and value else None

    return EntityDescription(
        key=key,
        platform=platform,
        name=text("name") or key,
        icon=text("icon"),
        unit=text("unit"),
        state_class=text("state_class"),
        attributes=raw.get("attributes") is True,
    )


class MemoryCardHub:
    """The app's entities and state, updated from the feed."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: MemoryCardClient) -> None:
        """Hold the feed for one app."""
        self.hass = hass
        self.entry = entry
        self.client = client
        self.descriptions: dict[str, EntityDescription] = {}
        self.device: dict[str, Any] = {}
        self.state: dict[str, Any] | None = None
        self.connected = False
        self._ready = asyncio.Event()
        self._hello_due = True
        self._task: asyncio.Task[None] | None = None

    @property
    def signal_entities(self) -> str:
        """Sent when the app's entity list arrives."""
        return f"{DOMAIN}_{self.entry.entry_id}_entities"

    @property
    def signal_update(self) -> str:
        """Sent when the state or the connection changes."""
        return f"{DOMAIN}_{self.entry.entry_id}_update"

    @property
    def available(self) -> bool:
        """Whether entities have a current value to show."""
        return self.connected and self.state is not None

    @property
    def device_info(self) -> DeviceInfo:
        """The one Memory Card device."""
        info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name=str(self.device.get("name") or "Memory Card"),
            model=self.device.get("model"),
            sw_version=self.device.get("sw_version"),
        )
        if slug := self.entry.data.get(CONF_SLUG):
            info["configuration_url"] = f"homeassistant://hassio/ingress/{slug}"
        return info

    def start(self) -> None:
        """Open the feed in the background."""
        self._task = self.entry.async_create_background_task(
            self.hass, self._run(), f"{DOMAIN} feed"
        )

    async def wait_ready(self) -> None:
        """Wait for the entities and their first state."""
        await self._ready.wait()

    async def stop(self) -> None:
        """Close the feed."""
        if self._task is not None:
            self._task.cancel()
            await asyncio.wait([self._task])
            self._task = None

    async def _run(self) -> None:
        delay = RETRY_MIN.total_seconds()
        failures = 0
        while True:
            try:
                self._hello_due = True
                async with aclosing(self.client.feed()) as feed:
                    async for message in feed:
                        if not self._handle(message):
                            continue
                        if failures:
                            _LOGGER.info("Memory Card is available again")
                        failures = 0
                        delay = RETRY_MIN.total_seconds()
                error: MemoryCardError = MemoryCardError("the app closed the feed")
            except MemoryCardError as err:
                error = err
            self._set_connected(False)
            if isinstance(error, (Unauthorized, UnsupportedApi)):
                delay = RETRY_MAX.total_seconds()
            if failures == 0 and isinstance(error, (Unauthorized, UnsupportedApi)):
                _LOGGER.warning("Memory Card is unavailable: %s", _explain(error))
            elif failures == 0:
                # The app stops for updates and restarts, so this is no fault.
                _LOGGER.info("Memory Card is unavailable: %s", _explain(error))
            else:
                _LOGGER.debug("Cannot reach Memory Card: %s", _explain(error))
            failures += 1
            await asyncio.sleep(delay)
            delay = min(delay * 2, RETRY_MAX.total_seconds())

    def _handle(self, message: dict[str, Any]) -> bool:
        """Apply one message; returns whether it was the start of a feed."""
        kind = message.get("type")
        # The entity list opens each feed and never comes again within it.
        if (kind == "hello") != self._hello_due:
            raise MemoryCardError("the feed did not start with its entities")
        if kind == "hello":
            if message.get("api") != API_VERSION:
                raise UnsupportedApi(f"feed version {message.get('api')}")
            self._hello_due = False
            self._hello(message)
            return True
        if kind == "state" and isinstance(message.get("state"), dict):
            self.state = message["state"]
            self.connected = True
            self._ready.set()
            async_dispatcher_send(self.hass, self.signal_update)
        return False

    def _hello(self, message: dict[str, Any]) -> None:
        device = message.get("device")
        self.device = device if isinstance(device, dict) else {}
        entities = message.get("entities")
        if not isinstance(entities, list):
            entities = []
        if len(entities) > ENTITIES_MAX:
            raise MemoryCardError(f"the app sent {len(entities)} entities")
        descriptions = (_description(raw) for raw in entities)
        self.descriptions = {d.key: d for d in descriptions if d is not None}
        self._remove_gone()
        async_dispatcher_send(self.hass, self.signal_entities)

    @callback
    def _remove_gone(self) -> None:
        """Drop entities the app no longer sends."""
        registry = er.async_get(self.hass)
        kept = {f"{DOMAIN}_{key}" for key in self.descriptions}
        for entry in er.async_entries_for_config_entry(registry, self.entry.entry_id):
            if entry.unique_id not in kept:
                registry.async_remove(entry.entity_id)

    def _set_connected(self, connected: bool) -> None:
        if self.connected != connected:
            self.connected = connected
            async_dispatcher_send(self.hass, self.signal_update)


def _explain(error: MemoryCardError) -> str:
    if isinstance(error, Unauthorized):
        return "it refused the token; restart the Memory Card app to announce it again"
    if isinstance(error, UnsupportedApi):
        return f"it sends a {error}, update the Memory Card integration"
    return str(error) or type(error).__name__
