from __future__ import annotations

from dataclasses import dataclass

from battlebelief_runtime.errors.protocol import MalformedProtocolMessage


@dataclass(frozen=True, slots=True)
class RoomLine:
    room_id: str | None
    payload: str


def decode_frame(frame: str | bytes) -> tuple[RoomLine, ...]:
    """Split a raw Showdown WebSocket text frame into room-scoped lines.

    A frame may contain multiple room blocks; each `>room_id` marker line
    sets the room context for every following line until the next marker.
    Lines before any marker are global (room_id=None). Only a trailing '\\r'
    is stripped per line — payload content is otherwise untouched. Binary
    (non-str) frames and an empty '>' marker are rejected as malformed.
    """
    if not isinstance(frame, str):
        raise MalformedProtocolMessage("frame must be text, not binary")

    if frame == "":
        return ()

    lines: list[RoomLine] = []
    current_room: str | None = None
    for raw_line in frame.split("\n"):
        line = raw_line[:-1] if raw_line.endswith("\r") else raw_line
        if line == "":
            continue
        if line.startswith(">"):
            room_id = line[1:]
            if room_id == "":
                raise MalformedProtocolMessage("empty room marker")
            current_room = room_id
            continue
        lines.append(RoomLine(room_id=current_room, payload=line))
    return tuple(lines)
