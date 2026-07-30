from __future__ import annotations

from dataclasses import dataclass

from battlebelief_core.domain.state.values import EvidenceInterval, HpObservation

# Canonical boost-stat order: atk, def, spa, spd, spe, acc, eva
BOOST_STATS: tuple[str, ...] = ("atk", "def", "spa", "spd", "spe", "acc", "eva")
ZERO_BOOSTS: tuple[int, ...] = (0, 0, 0, 0, 0, 0, 0)


@dataclass(frozen=True, slots=True)
class PokemonView:
    side_id: str
    nickname: str
    identity_intervals: tuple[EvidenceInterval, ...]
    preview_details: str | None
    current_details: str | None
    active: bool
    hp: HpObservation | None
    status: str | None
    fainted: bool
    revealed_moves: tuple[str, ...]
    item_intervals: tuple[EvidenceInterval, ...]
    ability_intervals: tuple[EvidenceInterval, ...]
    tera_type: str | None
    boosts: tuple[int, ...]  # 7 values matching BOOST_STATS order
    volatiles: tuple[str, ...]  # sorted
    recharging: bool
    transform_target: str | None

    @classmethod
    def new(cls, side_id: str, nickname: str, details: str | None = None) -> PokemonView:
        return cls(
            side_id=side_id,
            nickname=nickname,
            identity_intervals=(),
            preview_details=None,
            current_details=details,
            active=False,
            hp=None,
            status=None,
            fainted=False,
            revealed_moves=(),
            item_intervals=(),
            ability_intervals=(),
            tera_type=None,
            boosts=ZERO_BOOSTS,
            volatiles=(),
            recharging=False,
            transform_target=None,
        )
