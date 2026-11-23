"""The Roll a pick button."""

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MemoryCardConfigEntry
from .entity import MemoryCardEntity, follow_entities
from .services import async_roll

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MemoryCardConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the buttons the app describes."""
    entry.async_on_unload(
        follow_entities(hass, entry.runtime_data, "button", MemoryCardButton, async_add_entities)
    )


class MemoryCardButton(MemoryCardEntity, ButtonEntity):
    """Picks a random game from the backlog, as the app's Pick for me does."""

    async def async_press(self) -> None:
        """Roll with the default filters; the pick sensor shows the result."""
        await async_roll(self.hub, {}, self._context.user_id if self._context else None)
