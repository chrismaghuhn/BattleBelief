from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from battlebelief_runtime.adapters.showdown_protocol.wire_types import (
    BATTLE_EVENT_TYPES,
    ROOM_CONTROL_TYPES,
)


class RoomPayloadKind(StrEnum):
    BATTLE_EVENT = "battle_event"
    DECISION_REQUEST = "decision_request"
    BATTLE_ERROR = "battle_error"
    TIMER_MESSAGE = "timer_message"
    ROOM_CONTROL_OR_CHAT = "room_control_or_chat"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ClassifiedRoomPayload:
    kind: RoomPayloadKind
    payload: str


def classify_room_payload(payload: str) -> ClassifiedRoomPayload:
    """Classify a single room-scoped payload line per the M1 plan's binding
    order. Reads only the first, outer type field — never re-parses or
    re-classifies embedded pipe-delimited content (e.g. inside chat text).
    """
    if payload == "|":
        return ClassifiedRoomPayload(kind=RoomPayloadKind.BATTLE_EVENT, payload=payload)
    if not payload.startswith("|") or payload.startswith("||"):
        return ClassifiedRoomPayload(kind=RoomPayloadKind.ROOM_CONTROL_OR_CHAT, payload=payload)

    parts = payload.split("|")
    wire_type = parts[1] if len(parts) > 1 else ""

    if wire_type == "request":
        return ClassifiedRoomPayload(kind=RoomPayloadKind.DECISION_REQUEST, payload=payload)
    if wire_type == "error":
        return ClassifiedRoomPayload(kind=RoomPayloadKind.BATTLE_ERROR, payload=payload)
    if wire_type in ("inactive", "inactiveoff"):
        return ClassifiedRoomPayload(kind=RoomPayloadKind.TIMER_MESSAGE, payload=payload)
    if wire_type in BATTLE_EVENT_TYPES:
        return ClassifiedRoomPayload(kind=RoomPayloadKind.BATTLE_EVENT, payload=payload)
    if wire_type in ROOM_CONTROL_TYPES:
        return ClassifiedRoomPayload(kind=RoomPayloadKind.ROOM_CONTROL_OR_CHAT, payload=payload)
    return ClassifiedRoomPayload(kind=RoomPayloadKind.UNKNOWN, payload=payload)
