from __future__ import annotations

from dataclasses import dataclass

from battlebelief_core.domain.events.base import BattleEvent


@dataclass(frozen=True, slots=True)
class VisibleEvidence(BattleEvent):
    event_index: int
    kind: str
    side_id: str | None
    slot: int | None
    nickname: str | None
    effect: str | None
    annotations: tuple[str, ...]
