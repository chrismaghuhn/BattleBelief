from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SealedTeam:
    digest: str
    member_count: int
