"""Canonical matchup identities used by the deterministic schedule."""

from __future__ import annotations

from dataclasses import dataclass

from battlebelief_core.canonicalization import manifest_digest


@dataclass(frozen=True, slots=True)
class BaseMatchupKey:
    hero_team: str
    opponent_team: str
    opponent_archetype: str
    opponent_policy_checkpoint: str
    schedule_block: str

    def __post_init__(self) -> None:
        for name in (
            "hero_team",
            "opponent_team",
            "opponent_archetype",
            "opponent_policy_checkpoint",
            "schedule_block",
        ):
            value = getattr(self, name)
            if type(value) is not str or not value:
                raise ValueError(f"{name} must be a non-empty string")

    def to_dict(self) -> dict[str, str]:
        return {
            "hero_team": self.hero_team,
            "opponent_team": self.opponent_team,
            "opponent_archetype": self.opponent_archetype,
            "opponent_policy_checkpoint": self.opponent_policy_checkpoint,
            "schedule_block": self.schedule_block,
        }

    @property
    def base_matchup_id(self) -> str:
        return manifest_digest(self.to_dict())


__all__ = ["BaseMatchupKey"]
