from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from battlebelief_runtime.errors.protocol import Disconnect, TransportTimeout

_LOGIN_URL = "https://play.pokemonshowdown.com/api/login"


class ShowdownAssertionProvider:
    """Fetch a Showdown login assertion without blocking the event loop."""

    def __init__(self, *, timeout: float = 10.0) -> None:
        self._timeout = timeout

    async def assertion(self, username: str, password: str, challstr: str) -> str:
        return await asyncio.to_thread(
            self._request,
            username,
            password,
            challstr,
        )

    def _request(self, username: str, password: str, challstr: str) -> str:
        form = urllib.parse.urlencode(
            {
                "name": username,
                "pass": password,
                "challstr": challstr,
            }
        ).encode("utf-8")
        request = urllib.request.Request(_LOGIN_URL, data=form, method="POST")

        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = response.read()
        except TimeoutError as exc:
            raise TransportTimeout("Showdown assertion request timed out") from exc
        except urllib.error.HTTPError as exc:
            raise Disconnect("Showdown assertion request failed") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise TransportTimeout("Showdown assertion request timed out") from exc
            raise Disconnect("Showdown assertion request failed") from exc
        except OSError as exc:
            raise Disconnect("Showdown assertion request failed") from exc

        try:
            response_data: Any = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Disconnect("Showdown assertion response was malformed") from exc

        if not isinstance(response_data, dict):
            raise Disconnect("Showdown assertion response was malformed")
        assertion = response_data.get("assertion")
        if not isinstance(assertion, str) or not assertion:
            raise Disconnect("Showdown assertion response was rejected")
        return assertion
