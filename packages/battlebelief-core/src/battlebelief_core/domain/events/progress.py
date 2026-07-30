from __future__ import annotations

from dataclasses import dataclass

from battlebelief_core.domain.events.base import BattleEvent


@dataclass(frozen=True, slots=True)
class BattleStarted(BattleEvent):
    event_index: int


@dataclass(frozen=True, slots=True)
class TurnStarted(BattleEvent):
    event_index: int
    turn: int


@dataclass(frozen=True, slots=True)
class BattleWon(BattleEvent):
    event_index: int
    winner: str


@dataclass(frozen=True, slots=True)
class BattleTied(BattleEvent):
    event_index: int
