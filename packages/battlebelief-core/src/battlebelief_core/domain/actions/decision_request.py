from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from battlebelief_core.domain.actions.submission import RequestIdentity, SafeSubmissionSet


class RequestKind(StrEnum):
    MOVE = "move"
    FORCED_SWITCH = "forced_switch"
    REVIVAL = "revival"
    TEAM_PREVIEW = "team_preview"
    WAIT = "wait"


@dataclass(frozen=True, slots=True)
class DecisionRequest:
    identity: RequestIdentity
    kind: RequestKind
    side_id: str
    team_member_count: int
    active_identity: str | None
    safe_submissions: SafeSubmissionSet
    is_update: bool
