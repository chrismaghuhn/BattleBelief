from __future__ import annotations

from dataclasses import dataclass

from battlebelief_core.domain.events.evidence import VisibleEvidence
from battlebelief_core.domain.state.side_view import SideView
from battlebelief_core.errors import ReducerInvariantError


def _empty_side(side_id: str) -> SideView:
    return SideView(
        side_id=side_id,
        user_id=None,
        display_name=None,
        team_size=None,
        preview_roster=(),
        active_slot=None,
        pokemon=(),
        side_conditions=(),
    )


@dataclass(frozen=True, slots=True)
class ObservedState:
    our_user_id: str
    event_index: int
    room_initialized: bool
    generation: int | None
    game_type: str | None
    tier: str | None
    rated: bool | None
    rules: tuple[str, ...]
    turn: int
    battle_started: bool
    team_preview_started: bool
    winner: str | None
    tied: bool
    our_side: str | None
    p1: SideView
    p2: SideView
    weather: str | None
    field_conditions: tuple[str, ...]
    visible_evidence: tuple[VisibleEvidence, ...]
    ignored_display_count: int

    @classmethod
    def initial(cls, our_user_id: str) -> ObservedState:
        return cls(
            our_user_id=our_user_id,
            event_index=-1,
            room_initialized=False,
            generation=None,
            game_type=None,
            tier=None,
            rated=None,
            rules=(),
            turn=0,
            battle_started=False,
            team_preview_started=False,
            winner=None,
            tied=False,
            our_side=None,
            p1=_empty_side("p1"),
            p2=_empty_side("p2"),
            weather=None,
            field_conditions=(),
            visible_evidence=(),
            ignored_display_count=0,
        )

    def side(self, side_id: str) -> SideView:
        if side_id == "p1":
            return self.p1
        if side_id == "p2":
            return self.p2
        raise ReducerInvariantError(f"invalid side id: {side_id!r}")
