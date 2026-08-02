from __future__ import annotations

from collections.abc import AsyncIterator, Iterable

from battlebelief_runtime.adapters.showdown_protocol.frame_decoder import RoomLine


class FakeConnection:
    """Deterministic connection double for complete room-session flows."""

    def __init__(self, incoming: Iterable[RoomLine | BaseException]) -> None:
        self._incoming = tuple(incoming)
        self.sent_global: list[str] = []
        self.sent_room: list[tuple[str, str]] = []

    async def connect(self) -> None:
        return None

    def lines(self) -> AsyncIterator[RoomLine]:
        return self._line_stream()

    async def _line_stream(self) -> AsyncIterator[RoomLine]:
        for item in self._incoming:
            if isinstance(item, BaseException):
                raise item
            yield item

    async def send_global(self, command: str) -> None:
        self.sent_global.append(command)

    async def send_room(self, room_id: str, command: str) -> None:
        self.sent_room.append((room_id, command))

    async def close(self) -> None:
        return None
