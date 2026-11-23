"""Base for every Memory Card entity."""

from collections.abc import Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, KNOWN_KEYS
from .hub import EntityDescription, MemoryCardHub


class MemoryCardEntity(Entity):
    """An entity the app describes, with the same IDs as its MQTT twin."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: MemoryCardHub, description: EntityDescription) -> None:
        """Build the entity from the app's description."""
        self.hub = hub
        self.description = description
        self._attr_unique_id = f"{DOMAIN}_{description.key}"
        self.entity_id = f"{description.platform}.{DOMAIN}_{description.key}"
        if description.key in KNOWN_KEYS:
            self._attr_translation_key = description.key
        else:
            self._attr_name = description.name
        self._attr_icon = description.icon
        self._attr_device_info = hub.device_info

    @property
    def available(self) -> bool:
        """Unavailable while the app is not connected."""
        return self.hub.available

    async def async_added_to_hass(self) -> None:
        """Follow the feed."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self.hub.signal_update, self.async_write_ha_state)
        )


def follow_entities(
    hass: HomeAssistant,
    hub: MemoryCardHub,
    platform: str,
    build: Callable[[MemoryCardHub, EntityDescription], MemoryCardEntity],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> Callable[[], None]:
    """Add this platform's entities now and whenever the app sends new ones."""
    added: set[str] = set()

    @callback
    def add() -> None:
        new = [
            description
            for key, description in hub.descriptions.items()
            if description.platform == platform and key not in added
        ]
        # A key the app dropped and sent again needs a new entity.
        added.intersection_update(hub.descriptions)
        added.update(description.key for description in new)
        if new:
            async_add_entities(build(hub, description) for description in new)

    add()
    return async_dispatcher_connect(hass, hub.signal_entities, add)
