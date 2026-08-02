from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from battlebelief_runtime.adapters.showdown_protocol.frame_decoder import RoomLine


class AssertionProvider(Protocol):
    async def assertion(self, username: str, password: str, challstr: str) -> str:
        """Return the Showdown assertion for one challenge string."""


class BattleConnection(Protocol):
    async def connect(self) -> None:
        """Open and authenticate the connection."""

    def lines(self) -> AsyncIterator[RoomLine]:
        """Yield decoded room-scoped lines in wire order."""

    async def send_global(self, command: str) -> None:
        """Send a global Showdown command."""

    async def send_room(self, room_id: str, command: str) -> None:
        """Send a room-prefixed Showdown command."""

    async def close(self) -> None:
        """Close the underlying transport."""
