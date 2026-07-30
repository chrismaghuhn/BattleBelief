from __future__ import annotations

from dataclasses import dataclass

from battlebelief_core.domain.events.base import BattleEvent


@dataclass(frozen=True, slots=True)
class IgnoredDisplayEvent(BattleEvent):
    event_index: int
    kind: str
