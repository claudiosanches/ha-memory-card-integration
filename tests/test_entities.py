"""The entities follow what the app sends."""

import copy
from datetime import timedelta
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.memory_card.const import DOMAIN
from custom_components.memory_card.hub import MemoryCardHub

from .conftest import STATE, FakeApp, set_up, until

FAST_RETRY = patch("custom_components.memory_card.hub.RETRY_MIN", timedelta(milliseconds=20))


async def test_every_entity_keeps_the_id_the_mqtt_one_had(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    await set_up(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, config_entry.entry_id)
    assert sorted(entity.entity_id for entity in entities) == [
        "button.memory_card_roll_pick",
        "sensor.memory_card_ana_backlog",
        "sensor.memory_card_ana_last_played",
        "sensor.memory_card_ana_playing",
        "sensor.memory_card_copies",
        "sensor.memory_card_games",
        "sensor.memory_card_last_added",
        "sensor.memory_card_pick",
        "sensor.memory_card_playing",
        "sensor.memory_card_wishlist",
    ]
    assert registry.async_get("sensor.memory_card_games").unique_id == "memory_card_games"

    games = hass.states.get("sensor.memory_card_games")
    assert games.state == "3"
    assert games.attributes[ATTR_UNIT_OF_MEASUREMENT] == "games"
    assert games.attributes["state_class"] == "measurement"
    assert games.attributes[ATTR_FRIENDLY_NAME] == "Memory Card Games"
    assert games.attributes["icon"] == "mdi:gamepad-variant"

    playing = hass.states.get("sensor.memory_card_playing")
    assert playing.attributes["games"] == ["Celeste"]
    last_played = hass.states.get("sensor.memory_card_ana_last_played")
    assert last_played.state == "Celeste"
    assert last_played.attributes["platform"] == "Nintendo Switch"
    assert last_played.attributes[ATTR_FRIENDLY_NAME] == "Memory Card Ana last played"
    assert (
        registry.async_get("sensor.memory_card_ana_backlog").unique_id
        == "memory_card_person_ana_backlog"
    )
    assert hass.states.get("sensor.memory_card_pick").state == "unknown"
    assert (
        hass.states.get("button.memory_card_roll_pick").attributes[ATTR_FRIENDLY_NAME]
        == "Memory Card Roll a pick"
    )

    [device] = dr.async_entries_for_config_entry(dr.async_get(hass), config_entry.entry_id)
    assert device.identifiers == {(DOMAIN, DOMAIN)}
    assert device.name == "Memory Card"
    assert device.sw_version == "0.1.0"
    assert device.configuration_url == "homeassistant://hassio/ingress/local_memory_card"


async def test_changes_in_the_app_show_at_once(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    await set_up(hass, config_entry)
    state = copy.deepcopy(STATE)
    state["games"] = 4
    state["pick"] = "Hades"
    state["attributes"]["pick"] = {"suggested_at": "2026-11-23", "platforms": ["PC"]}
    fake_app.send_state(state)
    await until(hass, lambda: hass.states.get("sensor.memory_card_games").state == "4")
    pick = hass.states.get("sensor.memory_card_pick")
    assert pick.state == "Hades"
    assert pick.attributes["platforms"] == ["PC"]

    fake_app.send({"type": "ping"})
    fake_app.send({"type": "something new"})
    await hass.async_block_till_done()
    assert hass.states.get("sensor.memory_card_games").state == "4"


async def test_entities_are_unavailable_while_the_app_is_away(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    with FAST_RETRY:
        await set_up(hass, config_entry)
        fake_app.token = "refused"
        fake_app.drop()
        await until(
            hass, lambda: hass.states.get("sensor.memory_card_games").state == STATE_UNAVAILABLE
        )
        assert hass.states.get("button.memory_card_roll_pick").state == STATE_UNAVAILABLE

        fake_app.token = config_entry.data["token"]
        state = copy.deepcopy(STATE)
        state["games"] = 5
        fake_app.state = state
        with patch("custom_components.memory_card.hub.RETRY_MAX", timedelta(milliseconds=50)):
            await until(hass, lambda: hass.states.get("sensor.memory_card_games").state == "5")


async def test_new_entities_from_the_app_appear_and_dropped_ones_go(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    with FAST_RETRY:
        await set_up(hass, config_entry)
        fake_app.entities = [e for e in fake_app.entities if e["key"] != "wishlist"]
        fake_app.entities.append(
            {
                "key": "hours",
                "platform": "sensor",
                "name": "Hours played",
                "icon": "mdi:clock",
                "unit": "h",
                "state_class": "measurement",
                "attributes": False,
            }
        )
        fake_app.entities.append({"key": "Bad Key!", "platform": "sensor"})
        fake_app.entities.append({"key": "lights", "platform": "light"})
        fake_app.state = {**copy.deepcopy(STATE), "hours": 12}
        fake_app.drop()
        await until(hass, lambda: hass.states.get("sensor.memory_card_hours") is not None)

    hours = hass.states.get("sensor.memory_card_hours")
    assert hours.state == "12"
    assert hours.attributes[ATTR_FRIENDLY_NAME] == "Memory Card Hours played"
    registry = er.async_get(hass)
    assert registry.async_get("sensor.memory_card_wishlist") is None
    assert hass.states.get("sensor.memory_card_wishlist") is None
    assert len(er.async_entries_for_config_entry(registry, config_entry.entry_id)) == 10


async def test_keys_that_make_no_entity_id_are_skipped(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_app: FakeApp,
    caplog: pytest.LogCaptureFixture,
) -> None:
    for key in ("hours\n", "_hours", "hours_", "my__hours", "h" * 65):
        fake_app.entities.append({"key": key, "platform": "sensor", "name": "Hours"})
    await set_up(hass, config_entry)
    registry = er.async_get(hass)
    assert len(er.async_entries_for_config_entry(registry, config_entry.entry_id)) == 10
    assert "Invalid entity ID" not in caplog.text


async def test_a_newer_feed_is_not_misread(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    fake_app.api = 2
    with patch("custom_components.memory_card.SETUP_TIMEOUT", timedelta(milliseconds=200)):
        await set_up(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.states.get("sensor.memory_card_games") is None


async def test_setup_waits_for_the_app(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    fake_app.token = "refused"
    with patch("custom_components.memory_card.SETUP_TIMEOUT", timedelta(milliseconds=200)):
        await set_up(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unloading_closes_the_feed(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    await set_up(hass, config_entry)
    assert len(fake_app.feeds) == 1
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await until(hass, lambda: not fake_app.feeds)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_a_new_entity_list_adds_and_drops_entities_without_starting_over(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    await set_up(hass, config_entry)
    registry = er.async_get(hass)
    bo = [
        {
            **entity,
            "key": entity["key"].replace("ana", "bo"),
            "object_id": entity["object_id"].replace("ana", "bo"),
            "person": {"name": "Bo", "kind": entity["person"]["kind"]},
        }
        for entity in fake_app.entities
        if "person" in entity
    ]
    household = [entity for entity in fake_app.entities if "person" not in entity]
    fake_app.send({"type": "hello", "api": 1, "entities": household + bo})
    await until(hass, lambda: registry.async_get("sensor.memory_card_bo_backlog") is not None)
    assert registry.async_get("sensor.memory_card_ana_backlog") is None
    assert fake_app.connections == 1
    assert (
        hass.states.get("sensor.memory_card_bo_backlog").attributes[ATTR_FRIENDLY_NAME]
        == "Memory Card Bo backlog"
    )


async def test_a_key_moved_to_another_platform_and_back_comes_back(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    await set_up(hass, config_entry)
    registry = er.async_get(hass)
    entities = fake_app.entities
    moved = [{**e, "platform": "button"} if e["key"] == "games" else e for e in entities]
    fake_app.send({"type": "hello", "api": 1, "entities": moved})
    await until(hass, lambda: registry.async_get("button.memory_card_games") is not None)
    assert registry.async_get("sensor.memory_card_games") is None
    fake_app.send({"type": "hello", "api": 1, "entities": entities})
    await until(hass, lambda: registry.async_get("sensor.memory_card_games") is not None)
    assert registry.async_get("button.memory_card_games") is None


async def test_a_burst_of_entity_lists_changes_the_entities_once_a_second(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    await set_up(hass, config_entry)
    registry = er.async_get(hass)
    household = [entity for entity in fake_app.entities if "person" not in entity]
    ana = [entity for entity in fake_app.entities if "person" in entity]

    def person(name: str) -> list[dict]:
        return [
            {
                **entity,
                "key": entity["key"].replace("ana", name.lower()),
                "object_id": entity["object_id"].replace("ana", name.lower()),
                "person": {"name": name, "kind": entity["person"]["kind"]},
            }
            for entity in ana
        ]

    applied = 0
    real = MemoryCardHub._remove_gone

    def counted(hub: MemoryCardHub) -> None:
        nonlocal applied
        applied += 1
        real(hub)

    with patch.object(MemoryCardHub, "_remove_gone", counted):
        for n in range(49):
            people = person("Bo") if n % 2 == 0 else ana
            fake_app.send({"type": "hello", "api": 1, "entities": household + people})
        fake_app.send({"type": "hello", "api": 1, "entities": household + person("Cy")})
        await until(hass, lambda: registry.async_get("sensor.memory_card_cy_backlog") is not None)
    assert registry.async_get("sensor.memory_card_ana_backlog") is None
    assert applied == 2
    assert fake_app.connections == 1


async def test_an_entity_list_past_the_cap_is_refused(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    fake_app.entities = [
        {"key": f"sensor_{n}", "platform": "sensor", "name": f"Sensor {n}"} for n in range(65)
    ]
    with patch("custom_components.memory_card.SETUP_TIMEOUT", timedelta(milliseconds=200)):
        await set_up(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id) == []


async def test_an_entity_list_with_nothing_usable_is_refused(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    fake_app.entities = [{"key": "", "platform": "sensor"}, {"key": "games", "platform": "x"}]
    with patch("custom_components.memory_card.SETUP_TIMEOUT", timedelta(milliseconds=200)):
        await set_up(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_a_hello_without_an_entity_list_is_refused(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    fake_app.entities = None
    with patch("custom_components.memory_card.SETUP_TIMEOUT", timedelta(milliseconds=200)):
        await set_up(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_text_home_assistant_cannot_save_is_refused(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    fake_app.state["last_added"] = "\ud800"
    with patch("custom_components.memory_card.SETUP_TIMEOUT", timedelta(milliseconds=200)):
        await set_up(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_a_feed_line_too_deep_to_read_starts_over(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    with FAST_RETRY:
        await set_up(hass, config_entry)
        fake_app.send(b"[" * 65_000 + b"]" * 65_000 + b"\n")
        await until(hass, lambda: fake_app.connections == 2)
        await until(hass, lambda: hass.states.get("sensor.memory_card_games").state == "3")


async def test_any_fault_while_reading_starts_the_feed_over(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_app: FakeApp,
    caplog: pytest.LogCaptureFixture,
) -> None:
    real = MemoryCardHub._remove_gone
    calls = 0

    def fails_once(hub: MemoryCardHub) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("boom")
        real(hub)

    with FAST_RETRY, patch.object(MemoryCardHub, "_remove_gone", fails_once):
        await set_up(hass, config_entry)
        await until(hass, lambda: hass.states.get("sensor.memory_card_games").state == "3")
    assert fake_app.connections == 2
    assert "Memory Card's feed failed" in caplog.text


async def test_a_burst_of_states_updates_the_entities_once_a_second(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    await set_up(hass, config_entry)
    written: list[Event] = []

    @callback
    def changed(event: Event) -> None:
        if event.data["entity_id"] == "sensor.memory_card_games":
            written.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, changed)
    for games in range(4, 54):
        state = copy.deepcopy(STATE)
        state["games"] = games
        fake_app.send_state(state)
    await until(hass, lambda: hass.states.get("sensor.memory_card_games").state == "53")
    assert len(written) <= 2


async def test_values_a_sensor_cannot_show_are_left_out(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    await set_up(hass, config_entry)
    state = copy.deepcopy(STATE)
    state["games"] = True
    state["copies"] = "many"
    state["pick"] = "x" * 300
    fake_app.send_state(state)
    await until(hass, lambda: hass.states.get("sensor.memory_card_pick").state == "x" * 255)
    assert hass.states.get("sensor.memory_card_games").state == STATE_UNKNOWN
    assert hass.states.get("sensor.memory_card_copies").state == STATE_UNKNOWN

    huge = b"1" + b"0" * 400
    fake_app.send(
        b'{"type": "state", "state": {"games": 1e999, "wishlist": ' + huge + b', "copies": 3}}\n'
    )
    await until(hass, lambda: hass.states.get("sensor.memory_card_copies").state == "3")
    assert hass.states.get("sensor.memory_card_games").state == STATE_UNKNOWN
    assert hass.states.get("sensor.memory_card_wishlist").state == STATE_UNKNOWN


async def test_attributes_are_short_values_home_assistant_does_not_read_itself(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    await set_up(hass, config_entry)
    state = copy.deepcopy(STATE)
    state["attributes"]["person_ana_last_played"] = {
        "date": "2026-11-22",
        "platform": "p" * 300,
        "entity_picture": "https://example.com/x.png",
        "latitude": 1.5,
        "state_class": "measurement",
        "Bad Key": 1,
        "nested": {"deep": [1]},
        "games": ["Celeste", {"x": 1}, 2**60, *["t"] * 60],
        **{f"extra_{n}": n for n in range(30)},
    }
    fake_app.send_state(state)
    last_played = "sensor.memory_card_ana_last_played"
    await until(hass, lambda: hass.states.get(last_played).attributes["date"] == "2026-11-22")

    attributes = hass.states.get(last_played).attributes
    assert attributes["platform"] == "p" * 255
    for name in ("entity_picture", "latitude", "state_class", "Bad Key"):
        assert name not in attributes
    assert attributes["nested"] is None
    assert attributes["games"] == ["Celeste", *["t"] * 47]
    assert sum(name.startswith("extra_") for name in attributes) == 16


async def test_a_feed_with_nan_starts_over(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    with FAST_RETRY:
        await set_up(hass, config_entry)
        fake_app.send(b'{"type": "state", "state": {"games": NaN}}\n')
        await until(hass, lambda: fake_app.connections == 2)
        await until(hass, lambda: hass.states.get("sensor.memory_card_games").state == "3")


async def test_device_details_that_are_not_short_text_are_left_out(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    fake_app.device = {"name": {"nested": True}, "model": "m" * 500, "sw_version": 1}
    await set_up(hass, config_entry)
    [device] = dr.async_entries_for_config_entry(dr.async_get(hass), config_entry.entry_id)
    assert device.name == "Memory Card"
    assert device.model == "m" * 100
    assert device.sw_version is None
