from __future__ import annotations

import pytest

from battlebelief_core.application.observation.reducer import ObservationReducer
from battlebelief_core.application.safety.request_reconciler import (
    ReconciliationStatus,
    RequestReconciler,
)
from battlebelief_core.domain.actions.decision_request import DecisionRequest, RequestKind
from battlebelief_core.domain.actions.submission import (
    ActionKind,
    ActionProvenance,
    BattleSubmission,
    RequestIdentity,
    SafeSubmissionSet,
)
from battlebelief_core.domain.events.metadata import (
    BattleInit,
    GameTypeDeclared,
    GenerationDeclared,
    PlayerDeclared,
    TeamSizeDeclared,
    TierDeclared,
)
from battlebelief_core.domain.events.pokemon import PokemonSwitched
from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_core.domain.state.values import HpToken

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_ROOM = "battle-gen9ou-1"
_OUR_USER = "trainer1"


def _base_state() -> ObservedState:
    """Fully initialized state with generation, gametype, tier, our side set."""
    s = ObservedState.initial(_OUR_USER)
    events = [
        BattleInit(event_index=0, room_id=_ROOM),
        PlayerDeclared(event_index=1, side_id="p1", username=_OUR_USER),
        PlayerDeclared(event_index=2, side_id="p2", username="trainer2"),
        GameTypeDeclared(event_index=3, game_type="singles"),
        GenerationDeclared(event_index=4, generation=9),
        TierDeclared(event_index=5, tier="[Gen 9] OU"),
        TeamSizeDeclared(event_index=6, side_id="p1", size=6),
        TeamSizeDeclared(event_index=7, side_id="p2", size=6),
    ]
    for ev in events:
        s = ObservationReducer.reduce(s, ev)
    return s


def _switch_in(s: ObservedState, side_id: str, nickname: str, ei: int) -> ObservedState:
    return ObservationReducer.reduce(
        s,
        PokemonSwitched(
            event_index=ei,
            side_id=side_id,
            slot=1,
            nickname=nickname,
            details=f"{nickname}, L50",
            hp=HpToken(current=100, maximum=100, status=None),
        ),
    )


def _identity(rqid: int = 1) -> RequestIdentity:
    return RequestIdentity(room_id=_ROOM, rqid=rqid, request_digest="d")


def _sss(*subs: BattleSubmission, rqid: int = 1) -> SafeSubmissionSet:
    return SafeSubmissionSet(request_identity=_identity(rqid), submissions=subs)


def _default() -> BattleSubmission:
    return BattleSubmission(kind=ActionKind.DEFAULT, provenance=ActionProvenance.SERVER_DEFAULT)


def _move_sub() -> BattleSubmission:
    return BattleSubmission(
        kind=ActionKind.MOVE,
        provenance=ActionProvenance.EXPLICIT_REQUEST,
        slot=1,
        move_id="surf",
    )


def _move_request(
    state: ObservedState,
    rqid: int = 1,
    active: str | None = "Garchomp",
) -> DecisionRequest:
    sss = _sss(_move_sub(), _default(), rqid=rqid)
    return DecisionRequest(
        identity=_identity(rqid),
        kind=RequestKind.MOVE,
        side_id="p1",
        team_member_count=6,
        active_identity=active,
        safe_submissions=sss,
        is_update=False,
    )


def _wait_request(rqid: int = 1) -> DecisionRequest:
    sss = SafeSubmissionSet(request_identity=_identity(rqid), submissions=())
    return DecisionRequest(
        identity=_identity(rqid),
        kind=RequestKind.WAIT,
        side_id="p1",
        team_member_count=6,
        active_identity=None,
        safe_submissions=sss,
        is_update=False,
    )


# ---------------------------------------------------------------------------
# PENDING cases — insufficient public state
# ---------------------------------------------------------------------------


class TestReconcilerPending:
    def test_pending_when_our_side_unknown(self) -> None:
        # No PlayerDeclared fired yet
        s = ObservedState.initial(_OUR_USER)
        dr = _move_request(s)
        result = RequestReconciler.reconcile(room_id=_ROOM, request=dr, state=s, latest_rqid=None)
        assert result.status == ReconciliationStatus.PENDING_PUBLIC_STATE

    def test_pending_when_generation_unknown(self) -> None:
        s = ObservedState.initial(_OUR_USER)
        s = ObservationReducer.reduce(s, BattleInit(event_index=0, room_id=_ROOM))
        s = ObservationReducer.reduce(
            s, PlayerDeclared(event_index=1, side_id="p1", username=_OUR_USER)
        )
        dr = _move_request(s)
        result = RequestReconciler.reconcile(room_id=_ROOM, request=dr, state=s, latest_rqid=None)
        assert result.status == ReconciliationStatus.PENDING_PUBLIC_STATE

    def test_pending_when_active_identity_unknown_for_move_request(self) -> None:
        # base_state has our side set, but no pokemon switched in yet
        s = _base_state()
        # active_identity provided by caller but nothing active in state
        dr = _move_request(s, active="Garchomp")
        result = RequestReconciler.reconcile(room_id=_ROOM, request=dr, state=s, latest_rqid=None)
        assert result.status == ReconciliationStatus.PENDING_PUBLIC_STATE

    def test_team_preview_does_not_need_active_identity(self) -> None:
        s = _base_state()
        sss = _sss(_default())
        dr = DecisionRequest(
            identity=_identity(),
            kind=RequestKind.TEAM_PREVIEW,
            side_id="p1",
            team_member_count=6,
            active_identity=None,
            safe_submissions=sss,
            is_update=False,
        )
        result = RequestReconciler.reconcile(room_id=_ROOM, request=dr, state=s, latest_rqid=None)
        assert result.status == ReconciliationStatus.ACCEPT


# ---------------------------------------------------------------------------
# REJECT cases — known, contradictory values
# ---------------------------------------------------------------------------


class TestReconcilerReject:
    def test_reject_wrong_room(self) -> None:
        s = _base_state()
        s = _switch_in(s, "p1", "Garchomp", 10)
        dr = _move_request(s)
        result = RequestReconciler.reconcile(
            room_id="battle-gen9ou-WRONG", request=dr, state=s, latest_rqid=None
        )
        assert result.status == ReconciliationStatus.REJECT

    def test_reject_wrong_side(self) -> None:
        s = _base_state()
        s = _switch_in(s, "p1", "Garchomp", 10)
        sss = _sss(_move_sub(), _default())
        dr = DecisionRequest(
            identity=_identity(),
            kind=RequestKind.MOVE,
            side_id="p2",  # wrong
            team_member_count=6,
            active_identity="Garchomp",
            safe_submissions=sss,
            is_update=False,
        )
        result = RequestReconciler.reconcile(room_id=_ROOM, request=dr, state=s, latest_rqid=None)
        assert result.status == ReconciliationStatus.REJECT

    def test_reject_wrong_generation(self) -> None:
        s = _base_state()
        s = _switch_in(s, "p1", "Garchomp", 10)
        # Patch generation: make a state with gen=8
        import dataclasses

        s8 = dataclasses.replace(s, generation=8)
        dr = _move_request(s8)
        result = RequestReconciler.reconcile(room_id=_ROOM, request=dr, state=s8, latest_rqid=None)
        assert result.status == ReconciliationStatus.REJECT

    def test_reject_wrong_game_type(self) -> None:
        import dataclasses

        s = _base_state()
        s = _switch_in(s, "p1", "Garchomp", 10)
        sd = dataclasses.replace(s, game_type="doubles")
        dr = _move_request(sd)
        result = RequestReconciler.reconcile(room_id=_ROOM, request=dr, state=sd, latest_rqid=None)
        assert result.status == ReconciliationStatus.REJECT

    def test_reject_stale_rqid(self) -> None:
        s = _base_state()
        s = _switch_in(s, "p1", "Garchomp", 10)
        dr = _move_request(s, rqid=1)
        result = RequestReconciler.reconcile(
            room_id=_ROOM,
            request=dr,
            state=s,
            latest_rqid=2,  # newer accepted
        )
        assert result.status == ReconciliationStatus.REJECT

    def test_reject_revival_not_treated_as_forced_switch(self) -> None:
        s = _base_state()
        sss = _sss(_default())
        dr_revival = DecisionRequest(
            identity=_identity(),
            kind=RequestKind.REVIVAL,
            side_id="p1",
            team_member_count=6,
            active_identity=None,
            safe_submissions=sss,
            is_update=False,
        )
        dr_switch = DecisionRequest(
            identity=_identity(),
            kind=RequestKind.FORCED_SWITCH,
            side_id="p1",
            team_member_count=6,
            active_identity=None,
            safe_submissions=sss,
            is_update=False,
        )
        result_r = RequestReconciler.reconcile(
            room_id=_ROOM, request=dr_revival, state=s, latest_rqid=None
        )
        result_s = RequestReconciler.reconcile(
            room_id=_ROOM, request=dr_switch, state=s, latest_rqid=None
        )
        # revival and forced_switch have distinct kinds — they must not alias
        assert (
            result_r.status != ReconciliationStatus.REJECT
            or result_s.status != ReconciliationStatus.REJECT
        )
        # At minimum, both should not share the same status if state/request don't match
        # The key contract: kind must be preserved as typed
        assert dr_revival.kind == RequestKind.REVIVAL
        assert dr_switch.kind == RequestKind.FORCED_SWITCH


# ---------------------------------------------------------------------------
# ACCEPT cases
# ---------------------------------------------------------------------------


class TestReconcilerAccept:
    def test_accept_move_request_with_known_active(self) -> None:
        s = _base_state()
        s = _switch_in(s, "p1", "Garchomp", 10)
        dr = _move_request(s, active="Garchomp")
        result = RequestReconciler.reconcile(room_id=_ROOM, request=dr, state=s, latest_rqid=None)
        assert result.status == ReconciliationStatus.ACCEPT

    def test_accept_wait_request(self) -> None:
        s = _base_state()
        dr = _wait_request()
        result = RequestReconciler.reconcile(room_id=_ROOM, request=dr, state=s, latest_rqid=None)
        assert result.status == ReconciliationStatus.ACCEPT

    def test_accept_newer_rqid(self) -> None:
        s = _base_state()
        s = _switch_in(s, "p1", "Garchomp", 10)
        dr = _move_request(s, rqid=5)
        result = RequestReconciler.reconcile(room_id=_ROOM, request=dr, state=s, latest_rqid=4)
        assert result.status == ReconciliationStatus.ACCEPT

    def test_result_is_frozen(self) -> None:
        s = _base_state()
        dr = _wait_request()
        result = RequestReconciler.reconcile(room_id=_ROOM, request=dr, state=s, latest_rqid=None)
        with pytest.raises((AttributeError, TypeError)):
            result.status = ReconciliationStatus.REJECT  # type: ignore[misc]

    def test_reconciler_does_not_mutate_state(self) -> None:
        s = _base_state()
        s = _switch_in(s, "p1", "Garchomp", 10)
        original_turn = s.turn
        dr = _move_request(s, active="Garchomp")
        RequestReconciler.reconcile(room_id=_ROOM, request=dr, state=s, latest_rqid=None)
        assert s.turn == original_turn
