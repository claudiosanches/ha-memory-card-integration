"""Talks to the Memory Card app's integration feed."""

from collections.abc import AsyncIterator
import json
from typing import Any

import aiohttp
from yarl import URL

from .const import READ_TIMEOUT, REQUEST_TIMEOUT


class MemoryCardError(Exception):
    """The app could not be reached or answered something unexpected."""


class Unauthorized(MemoryCardError):
    """The app refused the token."""


class NoMatch(MemoryCardError):
    """No game matches the roll's filters."""


class InvalidFilters(MemoryCardError):
    """The app could not read the roll's filters."""


class MemoryCardClient:
    """Reads the feed and asks for rolls."""

    def __init__(self, session: aiohttp.ClientSession, host: str, port: int, token: str) -> None:
        """Point the client at the app."""
        self._session = session
        self._base = URL.build(scheme="http", host=host, port=port, path="/integration/v1")
        self._headers = {"Authorization": f"Bearer {token}"}

    async def feed(self) -> AsyncIterator[dict[str, Any]]:
        """Yield each message until the app closes the feed."""
        timeout = aiohttp.ClientTimeout(
            total=None,
            connect=REQUEST_TIMEOUT.total_seconds(),
            sock_read=READ_TIMEOUT.total_seconds(),
        )
        try:
            async with self._session.get(
                self._base / "feed", headers=self._headers, timeout=timeout
            ) as response:
                _check(response)
                async for line in response.content:
                    if line.strip():
                        message = json.loads(line)
                        if isinstance(message, dict):
                            yield message
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise MemoryCardError(str(err) or type(err).__name__) from err

    async def roll(self, filters: dict[str, Any]) -> dict[str, Any]:
        """Pick a game; returns its title and platforms."""
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT.total_seconds())
        try:
            async with self._session.post(
                self._base / "roll", headers=self._headers, json=filters, timeout=timeout
            ) as response:
                if response.status == 404:
                    raise NoMatch
                if response.status == 422:
                    raise InvalidFilters
                _check(response)
                pick = await response.json()
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise MemoryCardError(str(err) or type(err).__name__) from err
        if not isinstance(pick, dict):
            raise MemoryCardError("unexpected roll answer")
        return pick


def _check(response: aiohttp.ClientResponse) -> None:
    if response.status == 401:
        raise Unauthorized
    if response.status != 200:
        raise MemoryCardError(f"the app answered {response.status}")
