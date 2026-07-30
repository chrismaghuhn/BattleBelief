from __future__ import annotations

from dataclasses import dataclass

from battlebelief_core.domain.events.base import BattleEvent


@dataclass(frozen=True, slots=True)
class WeatherChanged(BattleEvent):
    event_index: int
    weather: str | None
    action: str


@dataclass(frozen=True, slots=True)
class FieldConditionChanged(BattleEvent):
    event_index: int
    condition: str
    action: str
    annotations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SideConditionChanged(BattleEvent):
    event_index: int
    side_id: str
    condition: str
    action: str


@dataclass(frozen=True, slots=True)
class SideConditionsSwapped(BattleEvent):
    event_index: int
