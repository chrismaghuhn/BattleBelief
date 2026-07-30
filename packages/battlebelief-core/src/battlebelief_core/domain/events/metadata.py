from __future__ import annotations

from dataclasses import dataclass

from battlebelief_core.domain.events.base import BattleEvent


@dataclass(frozen=True, slots=True)
class BattleInit(BattleEvent):
    event_index: int
    room_id: str


@dataclass(frozen=True, slots=True)
class PlayerDeclared(BattleEvent):
    event_index: int
    side_id: str
    username: str


@dataclass(frozen=True, slots=True)
class TeamSizeDeclared(BattleEvent):
    event_index: int
    side_id: str
    size: int


@dataclass(frozen=True, slots=True)
class GameTypeDeclared(BattleEvent):
    event_index: int
    game_type: str


@dataclass(frozen=True, slots=True)
class GenerationDeclared(BattleEvent):
    event_index: int
    generation: int


@dataclass(frozen=True, slots=True)
class TierDeclared(BattleEvent):
    event_index: int
    tier: str


@dataclass(frozen=True, slots=True)
class BattleRated(BattleEvent):
    event_index: int
    rated: bool


@dataclass(frozen=True, slots=True)
class RuleDeclared(BattleEvent):
    event_index: int
    rule: str


@dataclass(frozen=True, slots=True)
class PreviewPokemonDeclared(BattleEvent):
    event_index: int
    side_id: str
    details: str
    has_item: bool


@dataclass(frozen=True, slots=True)
class PreviewCleared(BattleEvent):
    event_index: int


@dataclass(frozen=True, slots=True)
class TeamPreviewStarted(BattleEvent):
    event_index: int
