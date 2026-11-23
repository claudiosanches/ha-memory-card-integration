"""The roll_pick action."""

from typing import Any

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .client import InvalidFilters, MemoryCardError, NoMatch
from .const import DOMAIN
from .hub import MemoryCardHub

SERVICE_ROLL_PICK = "roll_pick"

_SLUGS = vol.All(cv.ensure_list, [cv.string])
ROLL_PICK_SCHEMA = vol.Schema(
    {
        vol.Optional("play_status"): _SLUGS,
        vol.Optional("platform"): _SLUGS,
        vol.Optional("device"): _SLUGS,
        vol.Optional("genre"): _SLUGS,
        vol.Optional("game_mode"): _SLUGS,
        vol.Optional("min_local_players"): vol.All(vol.Coerce(int), vol.Range(min=1, max=64)),
    }
)


async def async_roll(hub: MemoryCardHub, filters: dict[str, Any]) -> dict[str, Any]:
    """Ask the app for a pick, with errors people can read."""
    try:
        return await hub.client.roll(filters)
    except NoMatch as err:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_match") from err
    except InvalidFilters as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="invalid_filters"
        ) from err
    except MemoryCardError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the actions."""

    async def roll_pick(call: ServiceCall) -> ServiceResponse:
        entries = call.hass.config_entries.async_loaded_entries(DOMAIN)
        if not entries:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_loaded")
        pick = await async_roll(entries[0].runtime_data, dict(call.data))
        return pick if call.return_response else None

    hass.services.async_register(
        DOMAIN,
        SERVICE_ROLL_PICK,
        roll_pick,
        schema=ROLL_PICK_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
