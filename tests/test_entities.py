"""The entities follow what the app sends."""

import copy
from datetime import timedelta
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

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
        "sensor.memory_card_backlog",
        "sensor.memory_card_copies",
        "sensor.memory_card_games",
        "sensor.memory_card_last_added",
        "sensor.memory_card_last_played",
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
    last_played = hass.states.get("sensor.memory_card_last_played")
    assert last_played.state == "Celeste"
    assert last_played.attributes["platform"] == "Nintendo Switch"
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
    assert len(er.async_entries_for_config_entry(registry, config_entry.entry_id)) == 9


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


async def test_a_feed_that_breaks_its_order_starts_over(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    with FAST_RETRY:
        await set_up(hass, config_entry)
        assert fake_app.connections == 1
        fake_app.send({"type": "hello", "api": 1, "entities": []})
        await until(hass, lambda: fake_app.connections == 2)
        await until(hass, lambda: hass.states.get("sensor.memory_card_games").state == "3")
    assert len(er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)) == 9


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
