from __future__ import annotations

import asyncio
import functools
import logging
from collections import deque
from collections.abc import Awaitable, Callable

import pytest
from websockets.exceptions import InvalidHandshake, InvalidProxy, InvalidURI

from battlebelief_runtime.adapters.showdown_client import connection as connection_module
from battlebelief_runtime.adapters.showdown_client.connection import ShowdownConnection
from battlebelief_runtime.adapters.showdown_protocol.frame_decoder import RoomLine
from battlebelief_runtime.errors.protocol import Disconnect, TransportTimeout


def _async_test[**P, T](function: Callable[P, Awaitable[T]]) -> Callable[P, T]:
    @functools.wraps(function)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return asyncio.run(function(*args, **kwargs))

    return wrapper


_URL = "wss://sim.smogon.com/showdown/websocket"
_ROOM = "battle-gen9ou-1"


class _FakeSocket:
    def __init__(self, frames: list[str]) -> None:
        self.frames = deque(frames)
        self.sent: list[str] = []
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def recv(self) -> str:
        if not self.frames:
            raise StopAsyncIteration
        return self.frames.popleft()

    async def close(self) -> None:
        self.closed = True


class _LoggingSocket(_FakeSocket):
    def __init__(self, frames: list[str]) -> None:
        super().__init__(frames)
        self.logger: logging.Logger | None = None

    async def send(self, message: str) -> None:
        assert self.logger is not None
        self.logger.debug("> %s", message)
        await super().send(message)


class _ReadTimeoutSocket(_FakeSocket):
    async def recv(self) -> str:
        if not self.frames:
            raise TimeoutError("timed out")
        return await super().recv()


class _WriteTimeoutSocket(_FakeSocket):
    async def send(self, message: str) -> None:
        if self.sent:
            raise TimeoutError("timed out")
        await super().send(message)


class _DelayedReadSocket(_FakeSocket):
    async def recv(self) -> str:
        if not self.frames:
            await asyncio.sleep(0.05)
        return await super().recv()


class _DelayedWriteSocket(_FakeSocket):
    async def send(self, message: str) -> None:
        if self.sent:
            await asyncio.sleep(0.05)
        await super().send(message)


class _CloseErrorSocket(_FakeSocket):
    async def close(self) -> None:
        raise OSError("cleanup failed")


class _FakeAssertionProvider:
    def __init__(self, assertion: str = "assertion-token") -> None:
        self.assertion_value = assertion
        self.calls: list[tuple[str, str, str]] = []

    async def assertion(self, username: str, password: str, challstr: str) -> str:
        self.calls.append((username, password, challstr))
        return self.assertion_value


def _connector_for(
    socket: _FakeSocket,
    captured: dict[str, object] | None = None,
) -> Callable[..., Awaitable[_FakeSocket]]:
    async def connector(url: str, *, open_timeout: float) -> _FakeSocket:
        if captured is not None:
            captured["url"] = url
            captured["open_timeout"] = open_timeout
        return socket

    return connector


def _connection(
    socket: _FakeSocket,
    provider: _FakeAssertionProvider | None = None,
    captured: dict[str, object] | None = None,
    *,
    username: str = "Ash",
    read_timeout: float = 60.0,
    write_timeout: float = 10.0,
) -> ShowdownConnection:
    return ShowdownConnection(
        url=_URL,
        username=username,
        password="password",
        assertion_provider=provider or _FakeAssertionProvider(),
        socket_connector=_connector_for(socket, captured),
        read_timeout=read_timeout,
        write_timeout=write_timeout,
    )


@_async_test
async def test_connection_sends_exact_login_command_and_preserves_challstr() -> None:
    socket = _FakeSocket(
        [
            "|updateuser| ash|1|0|{}\n|challstr|4|abc|def",
            "|updateuser| ash|1|0|{}",
        ]
    )
    provider = _FakeAssertionProvider()
    captured: dict[str, object] = {}
    connection = _connection(socket, provider, captured)

    await connection.connect()

    assert captured == {"url": _URL, "open_timeout": 10.0}
    assert socket.sent == ["|/trn Ash,0,assertion-token"]
    assert provider.calls == [("Ash", "password", "4|abc|def")]


@_async_test
async def test_websocket_debug_logging_cannot_expose_authentication_or_team_frames(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assertion = "assertion-secret-must-not-leak"
    packed_team = "packed-team-secret-must-not-leak"
    socket = _LoggingSocket(["|challstr|4|abc", "|updateuser| ash|1|0|{}"])

    async def connector(
        _url: str,
        *,
        open_timeout: float,
        logger: logging.Logger,
    ) -> _LoggingSocket:
        assert open_timeout == 10.0
        socket.logger = logger
        return socket

    caplog.set_level(
        logging.DEBUG,
        logger=connection_module._WEBSOCKET_LOGGER.name,
    )
    assert connection_module._WEBSOCKET_LOGGER.isEnabledFor(logging.DEBUG)
    monkeypatch.setattr(connection_module, "connect", connector)
    connection = ShowdownConnection(
        url=_URL,
        username="Ash",
        password="password-secret-must-not-leak",
        assertion_provider=_FakeAssertionProvider(assertion),
    )

    await connection.connect()
    await connection.send_global(f"|/utm {packed_team}")

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert assertion not in messages
    assert packed_team not in messages


@_async_test
@pytest.mark.parametrize(
    "updateuser",
    ["|updateuser| ash|0|0|{}", "|updateuser| ashley|1|0|{}"],
)
async def test_connection_does_not_accept_non_matching_login(
    updateuser: str,
) -> None:
    socket = _FakeSocket(["|challstr|4|abc", updateuser])
    connection = _connection(socket)

    with pytest.raises(Disconnect):
        await connection.connect()


@_async_test
async def test_connection_accepts_updateuser_with_kelvin_sign_as_matching_identity() -> None:
    socket = _FakeSocket(["|challstr|4|abc", "|updateuser| Misty\u212a|1|0|{}"])
    connection = _connection(socket, username="MistyK")

    await connection.connect()

    assert socket.sent == ["|/trn MistyK,0,assertion-token"]


@_async_test
async def test_connection_rejects_updateuser_with_kelvin_sign_as_different_identity() -> None:
    socket = _FakeSocket(["|challstr|4|abc", "|updateuser| Misty\u212a|1|0|{}"])
    connection = _connection(socket, username="Misty")

    with pytest.raises(Disconnect):
        await connection.connect()
    assert socket.closed


@_async_test
async def test_connection_classifies_nametaken_as_disconnect() -> None:
    socket = _FakeSocket(["|challstr|4|abc", "|nametaken|ash"])
    connection = _connection(socket)

    with pytest.raises(Disconnect):
        await connection.connect()
    assert socket.closed


@_async_test
@pytest.mark.parametrize(
    "handshake_error",
    [
        InvalidHandshake("handshake failed"),
        InvalidProxy("http://proxy", "proxy failed"),
        InvalidURI("not-a-websocket", "invalid URI"),
        ValueError("cross-origin redirect rejected"),
    ],
)
async def test_connection_classifies_websocket_handshake_errors(
    handshake_error: Exception,
) -> None:
    async def connector(*_args: object, **_kwargs: object) -> _FakeSocket:
        raise handshake_error

    provider = _FakeAssertionProvider()
    connection = ShowdownConnection(
        url=_URL,
        username="Ash",
        password="password",
        assertion_provider=provider,
        socket_connector=connector,
    )

    with pytest.raises(Disconnect):
        await connection.connect()
    assert provider.calls == []


@_async_test
async def test_pinned_transport_origin_rejects_redirect_before_authentication() -> None:
    captured: dict[str, object] = {}
    provider = _FakeAssertionProvider()

    async def connector(url: str, **kwargs: object) -> _FakeSocket:
        captured.update({"url": url, **kwargs})
        raise ValueError("cross-origin redirect rejected")

    connection = ShowdownConnection(
        url="wss://sim3.psim.us/showdown/websocket",
        username="Ash",
        password="password",
        assertion_provider=provider,
        connect_host="sim3.psim.us",
        connect_port=443,
        socket_connector=connector,
    )

    with pytest.raises(Disconnect):
        await connection.connect()

    assert captured == {
        "url": "wss://sim3.psim.us/showdown/websocket",
        "open_timeout": 10.0,
        "host": "sim3.psim.us",
        "port": 443,
    }
    assert provider.calls == []


@_async_test
async def test_default_pinned_transport_disables_ambient_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket = _FakeSocket(["|challstr|4|abc", "|updateuser| ash|1|0|{}"])
    provider = _FakeAssertionProvider()

    async def connector(
        url: str,
        *,
        open_timeout: float,
        logger: logging.Logger,
        proxy: None,
        host: str,
        port: int,
    ) -> _FakeSocket:
        assert url == "wss://sim3.psim.us/showdown/websocket"
        assert open_timeout == 10.0
        assert logger is connection_module._WEBSOCKET_LOGGER
        assert proxy is None
        assert host == "sim3.psim.us"
        assert port == 443
        return socket

    monkeypatch.setattr(connection_module, "connect", connector)
    connection = ShowdownConnection(
        url="wss://sim3.psim.us/showdown/websocket",
        username="Ash",
        password="password",
        assertion_provider=provider,
        connect_host="sim3.psim.us",
        connect_port=443,
    )

    await connection.connect()

    assert socket.sent == ["|/trn Ash,0,assertion-token"]
    assert provider.calls == [("Ash", "password", "4|abc")]


@_async_test
async def test_authentication_error_closes_socket_and_preserves_error() -> None:
    socket = _FakeSocket(["|challstr|4|abc"])

    class _FailingProvider:
        async def assertion(self, *_args: str) -> str:
            raise RuntimeError("assertion provider failed")

    connection = _connection(socket, _FailingProvider())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="assertion provider failed"):
        await connection.connect()
    assert socket.closed


@_async_test
async def test_authentication_timeout_closes_socket() -> None:
    socket = _FakeSocket(["|challstr|4|abc"])

    class _TimingOutProvider:
        async def assertion(self, *_args: str) -> str:
            raise TransportTimeout("assertion timed out")

    connection = _connection(socket, _TimingOutProvider())  # type: ignore[arg-type]

    with pytest.raises(TransportTimeout):
        await connection.connect()
    assert socket.closed


@_async_test
async def test_failed_authentication_resets_connection_for_retry() -> None:
    failed_socket = _FakeSocket(["|challstr|4|abc", "|nametaken|ash"])
    successful_socket = _FakeSocket(["|challstr|4|abc", "|updateuser| ash|1|0|{}"])
    sockets = deque([failed_socket, successful_socket])

    async def connector(*_args: object, **_kwargs: object) -> _FakeSocket:
        return sockets.popleft()

    connection = ShowdownConnection(
        url=_URL,
        username="Ash",
        password="password",
        assertion_provider=_FakeAssertionProvider(),
        socket_connector=connector,
    )

    with pytest.raises(Disconnect):
        await connection.connect()
    await connection.connect()

    assert failed_socket.closed
    assert successful_socket.sent == ["|/trn Ash,0,assertion-token"]


@_async_test
async def test_cleanup_error_does_not_mask_authentication_error() -> None:
    socket = _CloseErrorSocket(["|challstr|4|abc"])

    class _FailingProvider:
        async def assertion(self, *_args: str) -> str:
            raise RuntimeError("authentication failed")

    connection = _connection(socket, _FailingProvider())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="authentication failed"):
        await connection.connect()


@_async_test
async def test_configured_read_deadline_is_classified() -> None:
    socket = _DelayedReadSocket(["|challstr|4|abc", "|updateuser| ash|1|0|{}"])
    connection = _connection(socket, read_timeout=0.001)
    await connection.connect()

    with pytest.raises(TransportTimeout):
        await connection.lines().__anext__()


@_async_test
async def test_configured_write_deadline_is_classified() -> None:
    socket = _DelayedWriteSocket(["|challstr|4|abc", "|updateuser| ash|1|0|{}"])
    connection = _connection(socket, write_timeout=0.001)
    await connection.connect()

    with pytest.raises(TransportTimeout):
        await connection.send_room(_ROOM, "/choose move 1")


@_async_test
async def test_connection_classifies_open_timeout() -> None:
    async def connector(*_args: object, **_kwargs: object) -> _FakeSocket:
        raise TimeoutError("timed out")

    connection = ShowdownConnection(
        url=_URL,
        username="Ash",
        password="password",
        assertion_provider=_FakeAssertionProvider(),
        socket_connector=connector,
    )

    with pytest.raises(TransportTimeout):
        await connection.connect()


@_async_test
async def test_login_buffer_preserves_battle_room_line_and_room_prefix() -> None:
    socket = _FakeSocket(
        [
            "|challstr|4|abc\n|updateuser| ash|1|0|{}\n>battle-gen9ou-1\n|init|battle",
        ]
    )
    connection = _connection(socket)

    await connection.connect()
    line = await connection.lines().__anext__()

    assert line == RoomLine(room_id=_ROOM, payload="|init|battle")


@_async_test
async def test_lines_yields_queued_lines_before_later_socket_frames() -> None:
    socket = _FakeSocket(
        [
            "|challstr|4|abc\n|updateuser| ash|1|0|{}\n>battle-gen9ou-1\n|init|battle",
            ">battle-gen9ou-1\n|turn|1",
        ]
    )
    connection = _connection(socket)
    await connection.connect()
    lines = connection.lines()

    assert await lines.__anext__() == RoomLine(room_id=_ROOM, payload="|init|battle")
    assert await lines.__anext__() == RoomLine(room_id=_ROOM, payload="|turn|1")


@_async_test
async def test_socket_close_is_classified_as_disconnect() -> None:
    socket = _FakeSocket(["|challstr|4|abc", "|updateuser| ash|1|0|{}"])
    connection = _connection(socket)
    await connection.connect()

    with pytest.raises(Disconnect):
        await connection.lines().__anext__()


@_async_test
async def test_socket_read_timeout_is_classified() -> None:
    socket = _ReadTimeoutSocket(["|challstr|4|abc", "|updateuser| ash|1|0|{}"])
    connection = _connection(socket)
    await connection.connect()

    with pytest.raises(TransportTimeout):
        await connection.lines().__anext__()


@_async_test
async def test_socket_write_timeout_is_classified() -> None:
    socket = _WriteTimeoutSocket(["|challstr|4|abc", "|updateuser| ash|1|0|{}"])
    connection = _connection(socket)
    await connection.connect()

    with pytest.raises(TransportTimeout):
        await connection.send_room(_ROOM, "/choose move 1")


@_async_test
async def test_send_room_prefixes_command_exactly() -> None:
    socket = _FakeSocket(["|challstr|4|abc", "|updateuser| ash|1|0|{}"])
    connection = _connection(socket)
    await connection.connect()

    await connection.send_room(_ROOM, "/choose move 1|5")

    assert socket.sent == ["|/trn Ash,0,assertion-token", "battle-gen9ou-1|/choose move 1|5"]
