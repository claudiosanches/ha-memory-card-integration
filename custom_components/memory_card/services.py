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

from .client import InvalidFilters, MemoryCardError, NoMatch, NotAllowed, PersonRequired
from .const import DOMAIN
from .hub import MemoryCardHub

SERVICE_ROLL_PICK = "roll_pick"

_SLUGS = vol.All(cv.ensure_list, [cv.string])
ROLL_PICK_SCHEMA = vol.Schema(
    {
        vol.Optional("person"): cv.entity_domain("person"),
        vol.Optional("play_status"): _SLUGS,
        vol.Optional("platform"): _SLUGS,
        vol.Optional("device"): _SLUGS,
        vol.Optional("genre"): _SLUGS,
        vol.Optional("game_mode"): _SLUGS,
        vol.Optional("min_local_players"): vol.All(vol.Coerce(int), vol.Range(min=1, max=64)),
    }
)


async def async_roll(
    hub: MemoryCardHub, filters: dict[str, Any], user_id: str | None, person: str | None = None
) -> dict[str, Any]:
    """Ask the app for a pick from one person's backlog, with errors people can read.

    The person is the Home Assistant user who asks, or, for an automation, the
    user ID it names.
    """
    if not user_id and not person:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="person_required")
    try:
        return await hub.client.roll(filters, user_id, person)
    except PersonRequired as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="person_required"
        ) from err
    except NotAllowed as err:
        key = "not_your_roll" if err.code == "not_your_roll" else "play_not_allowed"
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key=key) from err
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
        filters = dict(call.data)
        person = None
        if entity_id := filters.pop("person", None):
            state = call.hass.states.get(entity_id)
            person = state.attributes.get("user_id") if state else None
            if not isinstance(person, str) or not person:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="unknown_person"
                )
        pick = await async_roll(entries[0].runtime_data, filters, call.context.user_id, person)
        return pick if call.return_response else None

    hass.services.async_register(
        DOMAIN,
        SERVICE_ROLL_PICK,
        roll_pick,
        schema=ROLL_PICK_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
