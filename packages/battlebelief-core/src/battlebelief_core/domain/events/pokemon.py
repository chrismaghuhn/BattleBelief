from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from battlebelief_core.domain.events.base import BattleEvent
from battlebelief_core.domain.state.values import HpToken


class BoostChangeMode(StrEnum):
    DELTA = "delta"
    SET = "set"


class FormChangeKind(StrEnum):
    # detailschange: permanent form change carrying full DETAILS; updates
    # the pokemon's switch-identity key (e.g. Power Construct's Zygarde
    # Complete Forme, Shaymin's Sky/Land forme).
    PERSISTENT_DETAILS = "persistent_details"
    # -formechange: temporary/cosmetic change carrying SPECIES only; display
    # only, must not affect switch-identity (e.g. Mimikyu Busted, Zen Mode).
    TEMPORARY_SPECIES = "temporary_species"


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
    # None when the wire POKEMON identifier carries no position letter
    # (e.g. "p1: Name" for a Revival Blessing target) — distinct from an
    # active-slot reference ("p1a: Name"), which always carries a position.
    slot: int | None
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
    mode: BoostChangeMode
    amount: int


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
    """side_id/slot/nickname are all None for -clearallboost (both sides' active pokemon)."""

    event_index: int
    side_id: str | None
    slot: int | None
    nickname: str | None
    scope: str

    def __post_init__(self) -> None:
        target = (self.side_id, self.slot, self.nickname)
        if not (all(f is None for f in target) or all(f is not None for f in target)):
            raise ValueError("BoostsCleared target fields must be all-None or all-set")
        if self.side_id is None and self.scope != "all":
            raise ValueError("global BoostsCleared (-clearallboost) only supports scope='all'")


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
    hp: HpToken


@dataclass(frozen=True, slots=True)
class FormChanged(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    kind: FormChangeKind
    value: str  # full details for PERSISTENT_DETAILS, bare species for TEMPORARY_SPECIES
    hp: HpToken


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
class RechargeChanged(BattleEvent):
    event_index: int
    side_id: str
    slot: int
    nickname: str
    recharging: bool
