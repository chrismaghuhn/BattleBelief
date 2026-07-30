from __future__ import annotations

from dataclasses import dataclass

from battlebelief_core.domain.events.base import BattleEvent
from battlebelief_core.domain.state.values import HpToken


@dataclass(frozen=True, slots=True)
class PokemonSwitched(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    details: str
    hp: HpToken


@dataclass(frozen=True, slots=True)
class PokemonDragged(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    details: str
    hp: HpToken


@dataclass(frozen=True, slots=True)
class PokemonFainted(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str


@dataclass(frozen=True, slots=True)
class MoveUsed(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    move_id: str
    target_side_id: str | None
    target_slot: int | None
    target_nickname: str | None
    annotations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MovePrevented(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    reason: str
    move_id: str | None


@dataclass(frozen=True, slots=True)
class HealthChanged(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    hp: HpToken
    annotations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StatusChanged(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    status: str | None
    annotations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TeamStatusCured(BattleEvent):
    event_index: int
    side_id: str


@dataclass(frozen=True, slots=True)
class BoostChanged(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    stat: str
    delta: int


@dataclass(frozen=True, slots=True)
class BoostsSwapped(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    target_side_id: str
    target_slot: int
    target_nickname: str
    stats: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BoostsCopied(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    source_side_id: str
    source_slot: int
    source_nickname: str
    stats: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BoostsCleared(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    scope: str


@dataclass(frozen=True, slots=True)
class BoostsInverted(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str


@dataclass(frozen=True, slots=True)
class ItemChanged(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    item: str | None
    action: str
    annotations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AbilityChanged(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    ability: str | None
    action: str
    annotations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IdentityChanged(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    details: str


@dataclass(frozen=True, slots=True)
class FormChanged(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    details: str


@dataclass(frozen=True, slots=True)
class PokemonTransformed(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    target_side_id: str
    target_slot: int
    target_nickname: str


@dataclass(frozen=True, slots=True)
class Terastallized(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    tera_type: str


@dataclass(frozen=True, slots=True)
class VolatileChanged(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    volatile: str
    action: str
    annotations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TransientEffectObserved(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    effect_id: str
    annotations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RechargeChanged(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    recharging: bool
