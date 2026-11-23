"""A stand-in for the Memory Card app's integration feed."""

import asyncio
from collections.abc import AsyncIterator, Callable
import copy
import json
from typing import Any

from aiohttp import web
from aiohttp.test_utils import TestServer
from homeassistant.config_entries import SOURCE_HASSIO
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.memory_card.const import CONF_SLUG, DOMAIN

TOKEN = "0123456789abcdef" * 4
UUID = "fedcba9876543210fedcba9876543210"

# What the app sends today, as in its entities.rs.
ENTITIES: list[dict[str, Any]] = [
    {
        "key": "games",
        "platform": "sensor",
        "name": "Games",
        "icon": "mdi:gamepad-variant",
        "unit": "games",
        "state_class": "measurement",
        "attributes": False,
    },
    {
        "key": "copies",
        "platform": "sensor",
        "name": "Copies",
        "icon": "mdi:disc",
        "unit": "copies",
        "state_class": "measurement",
        "attributes": False,
    },
    {
        "key": "wishlist",
        "platform": "sensor",
        "name": "Wishlist",
        "icon": "mdi:heart",
        "unit": "copies",
        "state_class": "measurement",
        "attributes": False,
    },
    {
        "key": "backlog",
        "platform": "sensor",
        "name": "Backlog",
        "icon": "mdi:bookshelf",
        "unit": "games",
        "state_class": "measurement",
        "attributes": False,
    },
    {
        "key": "playing",
        "platform": "sensor",
        "name": "Playing",
        "icon": "mdi:controller",
        "unit": "games",
        "state_class": "measurement",
        "attributes": True,
    },
    {
        "key": "last_played",
        "platform": "sensor",
        "name": "Last played",
        "icon": "mdi:history",
        "attributes": True,
    },
    {
        "key": "last_added",
        "platform": "sensor",
        "name": "Last added",
        "icon": "mdi:new-box",
        "attributes": True,
    },
    {
        "key": "pick",
        "platform": "sensor",
        "name": "Current pick",
        "icon": "mdi:dice-5",
        "attributes": True,
    },
    {
        "key": "roll_pick",
        "platform": "button",
        "name": "Roll a pick",
        "icon": "mdi:dice-5",
        "attributes": False,
    },
]

STATE: dict[str, Any] = {
    "games": 3,
    "copies": 4,
    "wishlist": 1,
    "backlog": 2,
    "playing": 1,
    "last_played": "Celeste",
    "last_added": "Hades",
    "pick": None,
    "attributes": {
        "playing": {"games": ["Celeste"]},
        "last_played": {"date": "2026-11-20", "platform": "Nintendo Switch"},
        "last_added": {"added_at": "2026-11-21T10:00:00.000Z", "platform": "PC"},
        "pick": {},
    },
}


class FakeApp:
    """Serves the feed and the roll like the app does."""

    def __init__(self) -> None:
        self.port = 0
        self.api = 1
        self.token = TOKEN
        self.entities = copy.deepcopy(ENTITIES)
        self.state = copy.deepcopy(STATE)
        self.device: Any = {
            "name": "Memory Card",
            "model": "Video game collection",
            "sw_version": "0.1.0",
        }
        self.feeds: list[asyncio.Queue[dict[str, Any] | bytes | None]] = []
        self.rolls: list[Any] = []
        self.roll_users: list[str | None] = []
        self.roll_answer: tuple[int, Any] = (
            200,
            {"title": "Celeste", "platforms": ["Nintendo Switch"]},
        )
        self.roll_headers: dict[str, str] = {}
        self.connections = 0
        self.elsewhere = 0

    def _authorized(self, request: web.Request) -> bool:
        return request.headers.get("Authorization") == f"Bearer {self.token}"

    async def feed(self, request: web.Request) -> web.StreamResponse:
        if not self._authorized(request):
            return web.json_response({"code": "unauthorized"}, status=401)
        response = web.StreamResponse(headers={"Content-Type": "application/x-ndjson"})
        await response.prepare(request)
        queue: asyncio.Queue[dict[str, Any] | bytes | None] = asyncio.Queue()
        self.feeds.append(queue)
        self.connections += 1
        hello = {
            "type": "hello",
            "api": self.api,
            "version": "0.1.0",
            "device": self.device,
            "entities": self.entities,
        }
        try:
            for message in (hello, {"type": "state", "state": self.state}):
                await response.write(_line(message))
            while (message := await queue.get()) is not None:
                await response.write(message if isinstance(message, bytes) else _line(message))
        finally:
            self.feeds.remove(queue)
        return response

    async def roll(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return web.json_response({"code": "unauthorized"}, status=401)
        self.rolls.append(await request.json())
        self.roll_users.append(request.headers.get("X-Home-Assistant-User"))
        status, body = self.roll_answer
        if isinstance(body, bytes):
            return web.Response(body=body, status=status, headers=self.roll_headers)
        return web.json_response(body, status=status, headers=self.roll_headers)

    async def somewhere_else(self, request: web.Request) -> web.Response:
        self.elsewhere += 1
        return web.json_response({"title": "from elsewhere", "platforms": []})

    def send(self, message: dict[str, Any] | bytes) -> None:
        for queue in self.feeds:
            queue.put_nowait(message)

    def send_state(self, state: dict[str, Any]) -> None:
        self.state = state
        self.send({"type": "state", "state": state})

    def drop(self) -> None:
        """Close every open feed, as when the app stops."""
        for queue in self.feeds:
            queue.put_nowait(None)


def _line(message: dict[str, Any]) -> bytes:
    return json.dumps(message).encode() + b"\n"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from this repository."""


@pytest.fixture
async def fake_app(socket_enabled: None) -> AsyncIterator[FakeApp]:
    app = FakeApp()
    web_app = web.Application()
    web_app.router.add_get("/integration/v1/feed", app.feed)
    web_app.router.add_post("/integration/v1/roll", app.roll)
    web_app.router.add_route("*", "/elsewhere", app.somewhere_else)
    server = TestServer(web_app, host="127.0.0.1")
    await server.start_server()
    app.port = server.port
    yield app
    app.drop()
    await server.close()


@pytest.fixture
def config_entry(fake_app: FakeApp) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Memory Card",
        source=SOURCE_HASSIO,
        unique_id=UUID,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: fake_app.port,
            CONF_TOKEN: TOKEN,
            CONF_SLUG: "local_memory_card",
        },
    )


async def set_up(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def until(hass: HomeAssistant, done: Callable[[], bool]) -> None:
    async with asyncio.timeout(5):
        while not done():
            await asyncio.sleep(0.01)
            await hass.async_block_till_done()
