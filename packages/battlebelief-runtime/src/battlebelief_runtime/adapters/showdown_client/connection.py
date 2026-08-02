from __future__ import annotations

from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from typing import Protocol, cast

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from battlebelief_runtime.adapters.showdown_client.types import AssertionProvider
from battlebelief_runtime.adapters.showdown_protocol.frame_decoder import (
    RoomLine,
    decode_frame,
)
from battlebelief_runtime.errors.protocol import Disconnect, TransportTimeout


class _Socket(Protocol):
    async def send(self, message: str) -> None:
        """Send one text frame."""

    async def recv(self) -> str | bytes:
        """Receive one WebSocket frame."""

    async def close(self) -> None:
        """Close the WebSocket."""


SocketConnector = Callable[..., Awaitable[_Socket]]


class ShowdownConnection:
    """One authenticated, room-preserving Showdown WebSocket connection."""

    def __init__(
        self,
        *,
        url: str,
        username: str,
        password: str,
        assertion_provider: AssertionProvider,
        open_timeout: float = 10.0,
        socket_connector: SocketConnector | None = None,
    ) -> None:
        self._url = url
        self._username = username
        self._password = password
        self._assertion_provider = assertion_provider
        self._open_timeout = open_timeout
        self._socket_connector: SocketConnector = (
            socket_connector if socket_connector is not None else cast(SocketConnector, connect)
        )
        self._socket: _Socket | None = None
        self._authenticated = False
        self._queued_lines: deque[RoomLine] = deque()

    async def connect(self) -> None:
        if self._socket is not None:
            raise Disconnect("Showdown connection is already open")

        try:
            self._socket = await self._socket_connector(
                self._url,
                open_timeout=self._open_timeout,
            )
        except TimeoutError as exc:
            raise TransportTimeout("Showdown connection open timed out") from exc
        except (ConnectionClosed, OSError, StopAsyncIteration) as exc:
            raise Disconnect("Showdown connection could not be opened") from exc

        await self._authenticate()

    def lines(self) -> AsyncIterator[RoomLine]:
        return self._line_stream()

    async def _line_stream(self) -> AsyncIterator[RoomLine]:
        if not self._authenticated:
            raise Disconnect("Showdown connection is not authenticated")

        while True:
            if self._queued_lines:
                yield self._queued_lines.popleft()
                continue

            frame = await self._receive()
            for line in decode_frame(frame):
                yield line

    async def send_global(self, command: str) -> None:
        await self._send(command)

    async def send_room(self, room_id: str, command: str) -> None:
        await self._send(f"{room_id}|{command}")

    async def close(self) -> None:
        socket = self._socket
        self._socket = None
        self._authenticated = False
        self._queued_lines.clear()
        if socket is None:
            return

        try:
            await socket.close()
        except TimeoutError as exc:
            raise TransportTimeout("Showdown connection close timed out") from exc
        except ConnectionClosed:
            return
        except OSError:
            return

    async def _authenticate(self) -> None:
        pending: list[RoomLine] = []
        login_sent = False

        while True:
            frame_lines = decode_frame(await self._receive())
            for index, line in enumerate(frame_lines):
                if line.room_id is not None:
                    pending.append(line)
                    continue

                kind = _login_control_kind(line.payload)
                if kind == "nametaken":
                    raise Disconnect("Showdown username was rejected")

                if kind == "challstr":
                    if login_sent:
                        raise Disconnect("Showdown sent a duplicate challenge string")
                    challstr = _parse_challstr(line.payload)
                    assertion = await self._assertion_provider.assertion(
                        self._username,
                        self._password,
                        challstr,
                    )
                    await self._send(f"|/trn {self._username},0,{assertion}")
                    login_sent = True
                    continue

                if kind == "updateuser":
                    if login_sent and _is_valid_updateuser(line.payload, self._username):
                        self._finish_authentication(pending, frame_lines[index + 1 :])
                        return
                    if not login_sent:
                        pending.append(line)
                    continue

                pending.append(line)

    def _finish_authentication(
        self,
        pending: Iterable[RoomLine],
        remaining: Iterable[RoomLine],
    ) -> None:
        self._authenticated = True
        self._queue_non_login_lines(pending)
        self._queue_non_login_lines(remaining)

    def _queue_non_login_lines(self, lines: Iterable[RoomLine]) -> None:
        for line in lines:
            if line.room_id is None and _login_control_kind(line.payload) in {
                "challstr",
                "updateuser",
                "nametaken",
            }:
                continue
            self._queued_lines.append(line)

    async def _receive(self) -> str | bytes:
        socket = self._require_socket()
        try:
            return await socket.recv()
        except TimeoutError as exc:
            raise TransportTimeout("Showdown read timed out") from exc
        except (ConnectionClosed, OSError, StopAsyncIteration) as exc:
            raise Disconnect("Showdown socket closed unexpectedly") from exc

    async def _send(self, message: str) -> None:
        socket = self._require_socket()
        try:
            await socket.send(message)
        except TimeoutError as exc:
            raise TransportTimeout("Showdown write timed out") from exc
        except (ConnectionClosed, OSError, StopAsyncIteration) as exc:
            raise Disconnect("Showdown socket closed unexpectedly") from exc

    def _require_socket(self) -> _Socket:
        if self._socket is None:
            raise Disconnect("Showdown connection is not open")
        return self._socket


def _login_control_kind(payload: str) -> str | None:
    if payload.startswith("|challstr|"):
        return "challstr"
    if payload.startswith("|updateuser|"):
        return "updateuser"
    if payload.startswith("|nametaken|") or payload == "|nametaken":
        return "nametaken"
    return None


def _parse_challstr(payload: str) -> str:
    parts = payload.split("|", 2)
    if len(parts) != 3 or parts[0] != "" or parts[1] != "challstr" or not parts[2]:
        raise Disconnect("Showdown challenge string was malformed")
    return parts[2]


def _is_valid_updateuser(payload: str, expected_username: str) -> bool:
    parts = payload.split("|")
    if len(parts) < 4 or parts[0] != "" or parts[1] != "updateuser":
        return False
    return parts[3] == "1" and _to_id(parts[2]) == _to_id(expected_username)


def _to_id(value: str) -> str:
    return "".join(
        character.lower() for character in value if character.isascii() and character.isalnum()
    )
