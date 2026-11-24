"""Keeps the feed open and holds what the app last sent."""

import asyncio
from contextlib import aclosing
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .client import MemoryCardClient, MemoryCardError, Unauthorized
from .const import API_VERSION, CONF_SLUG, DOMAIN, KEY_MAX, RETRY_MAX, RETRY_MIN, VALID_KEY

_LOGGER = logging.getLogger(__name__)

PLATFORMS_SENT = ("sensor", "button")
# Far more than the app sends, so a broken feed cannot flood the registry.
ENTITIES_MAX = 64
# The app sends a change about a second after it happens, so faster states
# are a fault and wait.
UPDATE_COOLDOWN = 1.0
# Names, icons, units and versions are short.
TEXT_MAX = 100
# What a person's own sensors are, each with a translated name.
PERSON_KINDS = ("backlog", "playing", "last_played")


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
    # What follows memory_card_ in the entity ID.
    object_id: str
    # A person's own sensor: their name and which of theirs it is.
    person: str | None = None
    kind: str | None = None


def valid_key(key: Any) -> bool:
    """Whether a key from the app can name an entity."""
    return isinstance(key, str) and len(key) <= KEY_MAX and VALID_KEY.fullmatch(key) is not None


def _text(value: Any) -> str | None:
    return value[:TEXT_MAX] if isinstance(value, str) and value else None


def _description(raw: Any) -> EntityDescription | None:
    if not isinstance(raw, dict):
        return None
    key = raw.get("key")
    platform = raw.get("platform")
    if not valid_key(key):
        return None
    if platform not in PLATFORMS_SENT:
        return None
    object_id = raw.get("object_id")
    if not valid_key(object_id):
        object_id = key
    person, kind = None, None
    if isinstance(raw.get("person"), dict) and raw["person"].get("kind") in PERSON_KINDS:
        person = _text(raw["person"].get("name"))
        kind = raw["person"]["kind"] if person else None

    return EntityDescription(
        key=key,
        platform=platform,
        name=_text(raw.get("name")) or key,
        icon=_text(raw.get("icon")),
        unit=_text(raw.get("unit")),
        state_class=_text(raw.get("state_class")),
        attributes=raw.get("attributes") is True,
        object_id=object_id,
        person=person,
        kind=kind,
    )


def _entities(message: dict[str, Any]) -> tuple[dict[str, Any], dict[str, EntityDescription]]:
    """Read the device and entity descriptions in a hello."""
    device = message.get("device")
    entities = message.get("entities")
    if not isinstance(entities, list):
        entities = []
    if len(entities) > ENTITIES_MAX:
        raise MemoryCardError(f"the app sent {len(entities)} entities")
    descriptions = (_description(raw) for raw in entities)
    return (
        device if isinstance(device, dict) else {},
        {d.key: d for d in descriptions if d is not None},
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
        self._update = Debouncer(
            hass, _LOGGER, cooldown=UPDATE_COOLDOWN, immediate=True, function=self._send_update
        )
        self._next: tuple[dict[str, Any], dict[str, EntityDescription]] | None = None
        self._entities = Debouncer(
            hass, _LOGGER, cooldown=UPDATE_COOLDOWN, immediate=True, function=self._apply_entities
        )

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
            name=_text(self.device.get("name")) or "Memory Card",
            model=_text(self.device.get("model")),
            sw_version=_text(self.device.get("sw_version")),
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
        self._update.async_shutdown()
        self._entities.async_shutdown()
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
            except Exception as err:
                # A fault must not end the feed for good.
                if failures == 0:
                    _LOGGER.exception("Memory Card's feed failed")
                error = MemoryCardError(type(err).__name__)
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
        # The entity list opens each feed, and comes again when the people
        # who keep play change.
        if self._hello_due and kind != "hello":
            raise MemoryCardError("the feed did not start with its entities")
        if kind == "hello":
            if message.get("api") != API_VERSION:
                raise UnsupportedApi(f"feed version {message.get('api')}")
            started = self._hello_due
            self._hello_due = False
            self._next = _entities(message)
            if started:
                self._apply_entities(always=True)
            else:
                # The people who keep play changed; applied once a second at most.
                self._entities.async_schedule_call()
            return started
        if kind == "state" and isinstance(message.get("state"), dict):
            self.state = message["state"]
            self._ready.set()
            if self.connected:
                self._update.async_schedule_call()
            else:
                self._set_connected(True)
        return False

    @callback
    def _apply_entities(self, always: bool = False) -> None:
        """Use the latest entity list, unless it is the one in use."""
        if self._next is None:
            return
        self.device, descriptions = self._next
        self._next = None
        if descriptions == self.descriptions and not always:
            return
        self.descriptions = descriptions
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

    @callback
    def _send_update(self) -> None:
        async_dispatcher_send(self.hass, self.signal_update)

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
