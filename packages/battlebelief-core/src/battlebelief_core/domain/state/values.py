from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class HpPrecision(StrEnum):
    EXACT = "exact"
    PERCENT = "percent"
    PIXEL = "pixel"


@dataclass(frozen=True, slots=True)
class HpObservation:
    current: int
    maximum: int
    precision: HpPrecision
    fainted: bool = False

    def __post_init__(self) -> None:
        if self.maximum <= 0 or self.current < 0 or self.current > self.maximum:
            raise ValueError("invalid HP observation")
        if self.fainted and self.current != 0:
            raise ValueError("fainted HP observation must be zero")


@dataclass(frozen=True, slots=True)
class HpToken:
    """Raw HP value parsed from a wire frame; precision is not yet known."""

    current: int
    maximum: int
    status: str | None
    fainted: bool = False


@dataclass(frozen=True, slots=True)
class EvidenceInterval:
    value: str | None
    source_event_index: int
    valid_from: int
    valid_until: int | None = None


@dataclass(frozen=True, slots=True)
class EffectCounter:
    effect_id: str
    count: int


@dataclass(frozen=True, slots=True)
class PreviewPokemon:
    details: str
    has_item: bool
