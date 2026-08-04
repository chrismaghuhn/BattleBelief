from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

_MOVE_ID_RE = re.compile(r"^[a-z0-9]{1,100}$")


class ActionKind(StrEnum):
    MOVE = "move"
    SWITCH = "switch"
    REVIVE = "revive"
    TEAM = "team"
    DEFAULT = "default"


class ActionProvenance(StrEnum):
    EXPLICIT_REQUEST = "explicit_request"
    SERVER_DEFAULT = "server_default"


@dataclass(frozen=True, slots=True)
class RequestIdentity:
    room_id: str
    rqid: int
    request_digest: str


@dataclass(frozen=True, slots=True)
class BattleSubmission:
    kind: ActionKind
    provenance: ActionProvenance
    slot: int | None = None
    move_id: str | None = None
    terastallize: bool = False
    team_order: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ActionKind):
            raise ValueError("kind must be an ActionKind")
        if not isinstance(self.provenance, ActionProvenance):
            raise ValueError("provenance must be an ActionProvenance")
        if self.slot is not None and type(self.slot) is not int:
            raise ValueError("slot must be an integer or null")
        if self.move_id is not None and (
            type(self.move_id) is not str or not _MOVE_ID_RE.fullmatch(self.move_id)
        ):
            raise ValueError("move_id must be a Showdown identifier or null")
        if type(self.terastallize) is not bool:
            raise ValueError("terastallize must be a boolean")
        if type(self.team_order) is not tuple or any(
            type(slot) is not int for slot in self.team_order
        ):
            raise ValueError("team_order must be a tuple of integers")
        k = self.kind
        if k == ActionKind.MOVE:
            if self.slot is None or not (1 <= self.slot <= 4):
                raise ValueError("move slot must be 1-4")
            if not self.move_id:
                raise ValueError("move requires move_id")
            if self.team_order:
                raise ValueError("move must not carry team_order")
            if self.provenance != ActionProvenance.EXPLICIT_REQUEST:
                raise ValueError("move must carry EXPLICIT_REQUEST")
        elif k == ActionKind.SWITCH:
            if self.slot is None or not (1 <= self.slot <= 6):
                raise ValueError("switch slot must be 1-6")
            if self.terastallize:
                raise ValueError("switch must not terastallize")
            if self.move_id is not None:
                raise ValueError("switch must not carry move_id")
            if self.team_order:
                raise ValueError("switch must not carry team_order")
            if self.provenance != ActionProvenance.EXPLICIT_REQUEST:
                raise ValueError("switch must carry EXPLICIT_REQUEST")
        elif k == ActionKind.REVIVE:
            if self.slot is None or not (1 <= self.slot <= 6):
                raise ValueError("revive slot must be 1-6")
            if self.terastallize:
                raise ValueError("revive must not terastallize")
            if self.move_id is not None:
                raise ValueError("revive must not carry move_id")
            if self.team_order:
                raise ValueError("revive must not carry team_order")
            if self.provenance != ActionProvenance.EXPLICIT_REQUEST:
                raise ValueError("revive must carry EXPLICIT_REQUEST")
        elif k == ActionKind.TEAM:
            if not self.team_order:
                raise ValueError("team requires non-empty team_order")
            if len(set(self.team_order)) != len(self.team_order) or any(
                slot < 1 or slot > 6 for slot in self.team_order
            ):
                raise ValueError("team_order must contain unique slots from 1 through 6")
            if self.slot is not None:
                raise ValueError("team must not carry slot")
            if self.terastallize:
                raise ValueError("team must not terastallize")
            if self.move_id is not None:
                raise ValueError("team must not carry move_id")
            if self.provenance != ActionProvenance.EXPLICIT_REQUEST:
                raise ValueError("team must carry EXPLICIT_REQUEST")
        elif k == ActionKind.DEFAULT:
            if self.provenance != ActionProvenance.SERVER_DEFAULT:
                raise ValueError("default must carry SERVER_DEFAULT")
            if self.slot is not None:
                raise ValueError("default must not carry slot")
            if self.move_id is not None:
                raise ValueError("default must not carry move_id")
            if self.terastallize:
                raise ValueError("default must not terastallize")
            if self.team_order:
                raise ValueError("default must not carry team_order")
        else:
            # non-default kinds must not use SERVER_DEFAULT
            if self.provenance == ActionProvenance.SERVER_DEFAULT:
                raise ValueError(f"{k} must not carry SERVER_DEFAULT")


@dataclass(frozen=True, slots=True)
class SafeSubmissionSet:
    request_identity: RequestIdentity
    submissions: tuple[BattleSubmission, ...]

    def contains(self, submission: BattleSubmission) -> bool:
        return submission in self.submissions
