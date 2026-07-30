from __future__ import annotations

from dataclasses import dataclass

from battlebelief_core.domain.state.values import EvidenceInterval, HpObservation

# Canonical boost-stat order: atk, def, spa, spd, spe, acc, eva
BOOST_STATS: tuple[str, ...] = ("atk", "def", "spa", "spd", "spe", "acc", "eva")
ZERO_BOOSTS: tuple[int, ...] = (0, 0, 0, 0, 0, 0, 0)


def normalize_identity_details(details: str) -> str:
    """Strip a Gen9 tera-type suffix (", tera:TYPE") before using a details
    string as a stable switch-identity key — Terastallizing must not create
    a new identity for the same physical pokemon on a later switch-in.
    """
    parts = details.split(", ")
    kept = [p for p in parts if not p.startswith("tera:")]
    return ", ".join(kept)


@dataclass(frozen=True, slots=True)
class PokemonView:
    side_id: str
    nickname: str
    identity_intervals: tuple[EvidenceInterval, ...]
    preview_details: str | None
    # Stable switch-identity key (tera-suffix-normalized full details from
    # switch/drag, or a corrected identity from IdentityChanged/replace).
    # Never written by FormChanged: -formechange's SPECIES-only payload must
    # not corrupt the key used to recognize this pokemon on a later switch.
    switch_identity: str
    current_details: str | None  # display only — may be species-only after a form change
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
            switch_identity=normalize_identity_details(details) if details else "",
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
