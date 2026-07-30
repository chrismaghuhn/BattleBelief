from __future__ import annotations

from dataclasses import dataclass

from battlebelief_core.domain.teams.sealed_team import SealedTeam


@dataclass(frozen=True, slots=True)
class PackedTeam:
    sealed: SealedTeam
    packed: str
