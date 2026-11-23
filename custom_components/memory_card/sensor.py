"""Memory Card sensors: counts, titles and the current pick."""

import math
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import MAX_LENGTH_STATE_STATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MemoryCardConfigEntry
from .entity import MemoryCardEntity, follow_entities
from .hub import EntityDescription, MemoryCardHub

PARALLEL_UPDATES = 0
# Counts stay far below it; past it a float loses whole numbers.
NUMBER_MAX = 2**53


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MemoryCardConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the sensors the app describes."""
    entry.async_on_unload(
        follow_entities(hass, entry.runtime_data, "sensor", MemoryCardSensor, async_add_entities)
    )


class MemoryCardSensor(MemoryCardEntity, SensorEntity):
    """A value from the app's state."""

    def __init__(self, hub: MemoryCardHub, description: EntityDescription) -> None:
        """Take the unit and state class the app names."""
        super().__init__(hub, description)
        self._attr_native_unit_of_measurement = description.unit
        if description.state_class in SensorStateClass:
            self._attr_state_class = SensorStateClass(description.state_class)

    @property
    def native_value(self) -> Any:
        """The value under this sensor's key."""
        value = (self.hub.state or {}).get(self.description.key)
        numeric = self.description.unit is not None or self.description.state_class is not None
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return value if math.isfinite(value) and abs(value) < NUMBER_MAX else None
        if isinstance(value, str) and not numeric:
            return value[:MAX_LENGTH_STATE_STATE]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Details the app sends next to the value."""
        if not self.description.attributes:
            return None
        attributes = (self.hub.state or {}).get("attributes")
        if not isinstance(attributes, dict):
            return None
        mine = attributes.get(self.description.key)
        return mine if isinstance(mine, dict) else None
