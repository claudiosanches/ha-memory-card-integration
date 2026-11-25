"""Talks to the Memory Card app's integration feed."""

from collections.abc import AsyncIterator
import json
from typing import Any

import aiohttp
from yarl import URL

from .const import READ_TIMEOUT, REQUEST_TIMEOUT

# The Home Assistant user behind a roll; automations send none.
USER_HEADER = "X-Home-Assistant-User"
# A pick is a title and a few platform names.
ROLL_MAX = 64 * 1024


class MemoryCardError(Exception):
    """The app could not be reached or answered something unexpected."""


class Unauthorized(MemoryCardError):
    """The app refused the token."""


class NoMatch(MemoryCardError):
    """No game matches the roll's filters."""


class InvalidFilters(MemoryCardError):
    """The app could not read the roll's filters."""


class NotAllowed(MemoryCardError):
    """Memory Card refused the roll; `code` says why."""

    def __init__(self, code: str) -> None:
        """Keep the app's reason: play_not_allowed or not_your_roll."""
        super().__init__(code)
        self.code = code


class PersonRequired(MemoryCardError):
    """A roll with no Home Assistant user must name a person."""


# Error answers are a short code.
ERROR_MAX = 4096


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
                self._base / "feed",
                headers=self._headers,
                timeout=timeout,
                allow_redirects=False,
            ) as response:
                _check(response)
                async for line in response.content:
                    if line.strip():
                        message = json.loads(line, parse_constant=_not_a_number)
                        if isinstance(message, dict):
                            yield message
        # Deeply nested JSON raises RecursionError.
        except (aiohttp.ClientError, TimeoutError, ValueError, RecursionError) as err:
            raise MemoryCardError(str(err) or type(err).__name__) from err

    async def roll(
        self, filters: dict[str, Any], user_id: str | None = None, person: str | None = None
    ) -> dict[str, Any]:
        """Pick a game from a person's backlog: the user who asks, or the one named."""
        headers = dict(self._headers)
        if user_id:
            headers[USER_HEADER] = user_id
        body = {**filters, "person": person} if person else filters
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT.total_seconds())
        try:
            async with self._session.post(
                self._base / "roll",
                headers=headers,
                json=body,
                timeout=timeout,
                allow_redirects=False,
            ) as response:
                if response.status == 403:
                    raise NotAllowed(await _code(response))
                if response.status == 404:
                    raise NoMatch
                if response.status == 413:
                    raise InvalidFilters
                if response.status == 422:
                    if await _code(response) in ("person_required", "invalid_user"):
                        raise PersonRequired
                    raise InvalidFilters
                _check(response)
                body = b""
                async for chunk in response.content.iter_chunked(4096):
                    body += chunk
                    if len(body) > ROLL_MAX:
                        raise MemoryCardError("the roll answer is too large")
            pick = json.loads(body)
        except (aiohttp.ClientError, TimeoutError, ValueError, RecursionError) as err:
            raise MemoryCardError(str(err) or type(err).__name__) from err
        if not isinstance(pick, dict) or not isinstance(pick.get("title"), str):
            raise MemoryCardError("unexpected roll answer")
        platforms = pick.get("platforms")
        return {
            "title": pick["title"],
            "platforms": [p for p in platforms if isinstance(p, str)]
            if isinstance(platforms, list)
            else [],
        }


async def _code(response: aiohttp.ClientResponse) -> str:
    """Read the error code from a short answer; an empty string when there is none."""
    body = b""
    while len(body) < ERROR_MAX and (chunk := await response.content.read(ERROR_MAX - len(body))):
        body += chunk
    try:
        code = json.loads(body).get("code")
    except ValueError, AttributeError:
        return ""
    return code if isinstance(code, str) else ""


def _not_a_number(name: str) -> Any:
    raise ValueError(f"the feed sent {name}, which JSON does not allow")


def _check(response: aiohttp.ClientResponse) -> None:
    if response.status == 401:
        raise Unauthorized
    if response.status != 200:
        raise MemoryCardError(f"the app answered {response.status}")
