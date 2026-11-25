"""The Roll a pick button and the roll_pick action."""

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant.common import MockConfigEntry, MockUser
import voluptuous as vol

from custom_components.memory_card.const import DOMAIN
from custom_components.memory_card.diagnostics import async_get_config_entry_diagnostics

from .conftest import FakeApp, set_up


async def test_the_button_rolls_for_whoever_presses_it(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp, hass_admin_user: MockUser
) -> None:
    await set_up(hass, config_entry)
    press = {ATTR_ENTITY_ID: "button.memory_card_roll_pick"}
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        press,
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    assert fake_app.rolls == [{}]
    assert fake_app.roll_users == [hass_admin_user.id]

    # A press with no user, such as from an automation, has no backlog to pick from.
    with pytest.raises(ServiceValidationError) as raised:
        await hass.services.async_call(BUTTON_DOMAIN, SERVICE_PRESS, press, blocking=True)
    assert raised.value.translation_key == "person_required"
    assert len(fake_app.rolls) == 1


async def test_the_action_sends_filters_and_answers_with_the_pick(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp, hass_admin_user: MockUser
) -> None:
    await set_up(hass, config_entry)
    response = await hass.services.async_call(
        DOMAIN,
        "roll_pick",
        {"device": "switch", "min_local_players": 2},
        blocking=True,
        return_response=True,
        context=Context(user_id=hass_admin_user.id),
    )
    assert response == {"title": "Celeste", "platforms": ["Nintendo Switch"]}
    assert fake_app.rolls == [{"device": ["switch"], "min_local_players": 2}]

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "roll_pick", {"min_local_players": 0}, blocking=True)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "roll_pick", {"colour": "red"}, blocking=True)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "roll_pick", {"person": "light.ana"}, blocking=True)


async def test_a_roll_with_no_match_says_so(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp, hass_admin_user: MockUser
) -> None:
    await set_up(hass, config_entry)
    admin = Context(user_id=hass_admin_user.id)
    fake_app.roll_answer = (404, {"code": "no_candidates"})
    with pytest.raises(ServiceValidationError) as raised:
        await hass.services.async_call(DOMAIN, "roll_pick", {}, blocking=True, context=admin)
    assert raised.value.translation_key == "no_match"

    fake_app.roll_answer = (500, {"code": "internal"})
    with pytest.raises(HomeAssistantError) as raised:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.memory_card_roll_pick"},
            blocking=True,
            context=admin,
        )
    assert raised.value.translation_key == "cannot_connect"


async def test_the_action_needs_the_app_set_up(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, DOMAIN, {})
    with pytest.raises(ServiceValidationError) as raised:
        await hass.services.async_call(DOMAIN, "roll_pick", {}, blocking=True)
    assert raised.value.translation_key == "not_loaded"


async def test_diagnostics_leave_the_token_and_play_out(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    await set_up(hass, config_entry)
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diagnostics["entry"]["token"] == "**REDACTED**"
    assert diagnostics["connected"] is True
    assert "games" in diagnostics["entities"]
    assert config_entry.data["token"] not in str(diagnostics)
    assert "games" in diagnostics["state"]
    assert "Celeste" not in str(diagnostics)
    # Each person's keys carry their Home Assistant user ID.
    assert "person_1_backlog" in diagnostics["entities"]
    assert "person_1_last_played" in diagnostics["state"]
    assert "person_ana" not in str(diagnostics)


async def test_diagnostics_work_before_the_app_answers(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diagnostics["entry"]["token"] == "**REDACTED**"
    assert "connected" not in diagnostics


async def test_a_roll_is_for_one_person(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_app: FakeApp,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
) -> None:
    await set_up(hass, config_entry)
    hass.states.async_set("person.ana", "home", {"user_id": "ana-id"})
    hass.states.async_set("person.guest", "home", {})
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.memory_card_roll_pick"},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    await hass.services.async_call(
        DOMAIN, "roll_pick", {}, blocking=True, context=Context(user_id=hass_read_only_user.id)
    )
    # An automation names the person.
    await hass.services.async_call(DOMAIN, "roll_pick", {"person": "person.ana"}, blocking=True)
    assert fake_app.roll_users == [hass_admin_user.id, hass_read_only_user.id, None]
    assert fake_app.rolls[2] == {"person": "ana-id"}

    for data, key in (({}, "person_required"), ({"person": "person.guest"}, "unknown_person")):
        with pytest.raises(ServiceValidationError) as raised:
            await hass.services.async_call(DOMAIN, "roll_pick", data, blocking=True)
        assert raised.value.translation_key == key
    assert len(fake_app.rolls) == 3

    for status, code, key in (
        (403, "play_not_allowed", "play_not_allowed"),
        (403, "not_your_roll", "not_your_roll"),
        (422, "person_required", "person_required"),
    ):
        fake_app.roll_answer = (status, {"code": code})
        with pytest.raises(ServiceValidationError) as raised:
            await hass.services.async_call(
                DOMAIN, "roll_pick", {"person": "person.ana"}, blocking=True
            )
        assert raised.value.translation_key == key


async def test_a_roll_answer_is_never_followed_elsewhere_or_read_whole(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp, hass_admin_user: MockUser
) -> None:
    await set_up(hass, config_entry)
    admin = Context(user_id=hass_admin_user.id)
    fake_app.roll_answer = (307, b"")
    fake_app.roll_headers = {"Location": f"http://127.0.0.1:{fake_app.port}/elsewhere"}
    with pytest.raises(HomeAssistantError) as raised:
        await hass.services.async_call(DOMAIN, "roll_pick", {}, blocking=True, context=admin)
    assert raised.value.translation_key == "cannot_connect"
    assert fake_app.elsewhere == 0

    fake_app.roll_headers = {}
    fake_app.roll_answer = (200, b'{"title": "' + b"x" * 70_000 + b'"}')
    with pytest.raises(HomeAssistantError) as raised:
        await hass.services.async_call(DOMAIN, "roll_pick", {}, blocking=True, context=admin)
    assert raised.value.translation_key == "cannot_connect"

    fake_app.roll_answer = (200, {"title": 3, "platforms": []})
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, "roll_pick", {}, blocking=True, context=admin)
    fake_app.roll_answer = (200, {"title": "Hades", "platforms": ["PC", 4], "extra": 1})
    response = await hass.services.async_call(
        DOMAIN, "roll_pick", {}, blocking=True, return_response=True, context=admin
    )
    assert response == {"title": "Hades", "platforms": ["PC"]}
