from __future__ import annotations

import asyncio
import functools
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Awaitable, Callable

import pytest

from battlebelief_runtime.adapters.showdown_client.auth import ShowdownAssertionProvider
from battlebelief_runtime.errors.protocol import Disconnect, TransportTimeout


def _async_test[**P, T](function: Callable[P, Awaitable[T]]) -> Callable[P, T]:
    @functools.wraps(function)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return asyncio.run(function(*args, **kwargs))

    return wrapper


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


@_async_test
async def test_assertion_provider_preserves_pipe_separated_challstr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request: urllib.request.Request, *, timeout: float) -> _Response:
        captured["request"] = request
        captured["timeout"] = timeout
        return _Response(json.dumps({"assertion": "assertion-token"}).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    provider = ShowdownAssertionProvider(timeout=3.5)

    assertion = await provider.assertion("Ash", "password", "4|abc|def")

    request = captured["request"]
    assert isinstance(request, urllib.request.Request)
    assert request.full_url == "https://play.pokemonshowdown.com/api/login"
    assert request.data is not None
    assert urllib.parse.parse_qs(request.data.decode("utf-8")) == {
        "name": ["Ash"],
        "pass": ["password"],
        "challstr": ["4|abc|def"],
    }
    assert captured["timeout"] == 3.5
    assert assertion == "assertion-token"


@_async_test
async def test_assertion_provider_classifies_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(*_args: object, **_kwargs: object) -> _Response:
        raise urllib.error.HTTPError(
            "https://play.pokemonshowdown.com/api/login", 500, "error", {}, None
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(Disconnect):
        await ShowdownAssertionProvider().assertion("Ash", "password", "4|abc")


@_async_test
async def test_assertion_provider_classifies_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(*_args: object, **_kwargs: object) -> _Response:
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(TransportTimeout):
        await ShowdownAssertionProvider().assertion("Ash", "password", "4|abc")
