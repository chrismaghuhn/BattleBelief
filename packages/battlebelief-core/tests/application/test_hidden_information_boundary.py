from __future__ import annotations

from battlebelief_core.application.observation.reducer import ObservationReducer
from battlebelief_core.domain.events.metadata import PlayerDeclared
from battlebelief_core.domain.events.pokemon import (
    HealthChanged,
    MoveUsed,
    PokemonSwitched,
)
from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_core.domain.state.values import HpToken

_OWN = "ash"
_OPP = "misty"


def _base() -> ObservedState:
    s = ObservedState.initial(_OWN)
    s = ObservationReducer.reduce(s, PlayerDeclared(event_index=0, side_id="p1", username=_OWN))
    s = ObservationReducer.reduce(s, PlayerDeclared(event_index=1, side_id="p2", username=_OPP))
    return s


def _switch(s: ObservedState, side: str, nick: str, idx: int) -> ObservedState:
    return ObservationReducer.reduce(
        s,
        PokemonSwitched(
            event_index=idx,
            side_id=side,
            slot=1,
            nickname=nick,
            details=f"{nick}",
            hp=HpToken(current=100, maximum=100, status=None),
        ),
    )


def _active(s: ObservedState, side: str):  # type: ignore[return]
    side_view = s.p1 if side == "p1" else s.p2
    for pv in side_view.pokemon:
        if pv.active:
            return pv
    return None


class TestHiddenInformationBoundary:
    def test_opponent_has_no_unrevealed_moves(self) -> None:
        s = _base()
        s = _switch(s, "p2", "Garchomp", 10)
        s = ObservationReducer.reduce(
            s,
            MoveUsed(
                event_index=11,
                side_id="p2",
                slot=1,
                nickname="Garchomp",
                move_id="earthquake",
                target_side_id="p1",
                target_slot=1,
                target_nickname="Togekiss",
                annotations=(),
            ),
        )
        pv = _active(s, "p2")
        assert pv is not None
        # Only the revealed move appears — there are no hidden moves stored
        assert "earthquake" in pv.revealed_moves
        assert len(pv.revealed_moves) == 1

    def test_own_revealed_moves_accumulate(self) -> None:
        s = _base()
        s = _switch(s, "p1", "Garchomp", 10)
        s = ObservationReducer.reduce(
            s,
            MoveUsed(
                event_index=11,
                side_id="p1",
                slot=1,
                nickname="Garchomp",
                move_id="earthquake",
                target_side_id="p2",
                target_slot=1,
                target_nickname="Togekiss",
                annotations=(),
            ),
        )
        s = ObservationReducer.reduce(
            s,
            MoveUsed(
                event_index=12,
                side_id="p1",
                slot=1,
                nickname="Garchomp",
                move_id="swordsdance",
                target_side_id=None,
                target_slot=None,
                target_nickname=None,
                annotations=(),
            ),
        )
        pv = _active(s, "p1")
        assert pv is not None
        assert "earthquake" in pv.revealed_moves
        assert "swordsdance" in pv.revealed_moves

    def test_opponent_hp_is_observed_not_oracle(self) -> None:
        """Opponent HP comes from the wire token, not from oracle knowledge."""
        s = _base()
        s = _switch(s, "p2", "Togekiss", 10)
        s = ObservationReducer.reduce(
            s,
            HealthChanged(
                event_index=11,
                side_id="p2",
                slot=1,
                nickname="Togekiss",
                hp=HpToken(current=48, maximum=48, status=None),
                annotations=(),
            ),
        )
        pv = _active(s, "p2")
        assert pv is not None
        hp = pv.hp
        assert hp is not None
        # The state carries only what was visible on the wire
        # For an opponent with non-100 denominator this is pixel precision
        from battlebelief_core.domain.state.values import HpPrecision

        assert hp.precision == HpPrecision.PIXEL
        assert hp.current == 48

    def test_own_side_hp_is_exact(self) -> None:
        s = _base()
        s = _switch(s, "p1", "Garchomp", 10)
        pv = _active(s, "p1")
        assert pv is not None
        hp = pv.hp
        assert hp is not None
        from battlebelief_core.domain.state.values import HpPrecision

        assert hp.precision == HpPrecision.EXACT

    def test_no_oracle_hidden_stats(self) -> None:
        """PokemonView must not carry a 'hidden_stats' or similar oracle field."""
        s = _base()
        s = _switch(s, "p2", "Garchomp", 10)
        pv = _active(s, "p2")
        assert pv is not None
        assert not hasattr(pv, "hidden_stats")
        assert not hasattr(pv, "base_stats")
        assert not hasattr(pv, "full_hp")

    def test_p1_and_p2_views_are_independent(self) -> None:
        s = _base()
        s = _switch(s, "p1", "Garchomp", 10)
        s = _switch(s, "p2", "Togekiss", 11)
        assert s.p1.pokemon[0].nickname == "Garchomp"
        assert s.p2.pokemon[0].nickname == "Togekiss"
        # Modifying one side via reduce must not bleed into the other
        from battlebelief_core.domain.events.pokemon import StatusChanged

        s2 = ObservationReducer.reduce(
            s,
            StatusChanged(
                event_index=12,
                side_id="p1",
                slot=1,
                nickname="Garchomp",
                status="brn",
                annotations=(),
            ),
        )
        assert s2.p2.pokemon[0].status is None
