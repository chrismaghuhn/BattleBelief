from __future__ import annotations

import pytest

from battlebelief_core.application.decision.heuristic_policy import HeuristicPolicy
from battlebelief_core.domain.actions.decision_request import DecisionRequest, RequestKind
from battlebelief_core.domain.actions.submission import (
    ActionKind,
    ActionProvenance,
    BattleSubmission,
    RequestIdentity,
    SafeSubmissionSet,
)
from battlebelief_core.errors import NoLegalActionError

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _identity() -> RequestIdentity:
    return RequestIdentity(room_id="battle-gen9ou-1", rqid=1, request_digest="d")


def _move(slot: int, move_id: str, tera: bool = False) -> BattleSubmission:
    return BattleSubmission(
        kind=ActionKind.MOVE,
        provenance=ActionProvenance.EXPLICIT_REQUEST,
        slot=slot,
        move_id=move_id,
        terastallize=tera,
    )


def _switch(slot: int) -> BattleSubmission:
    return BattleSubmission(
        kind=ActionKind.SWITCH,
        provenance=ActionProvenance.EXPLICIT_REQUEST,
        slot=slot,
    )


def _revive(slot: int) -> BattleSubmission:
    return BattleSubmission(
        kind=ActionKind.REVIVE,
        provenance=ActionProvenance.EXPLICIT_REQUEST,
        slot=slot,
    )


def _team(order: tuple[int, ...]) -> BattleSubmission:
    return BattleSubmission(
        kind=ActionKind.TEAM,
        provenance=ActionProvenance.EXPLICIT_REQUEST,
        team_order=order,
    )


def _default() -> BattleSubmission:
    return BattleSubmission(kind=ActionKind.DEFAULT, provenance=ActionProvenance.SERVER_DEFAULT)


def _request(kind: RequestKind, *subs: BattleSubmission) -> DecisionRequest:
    sss = SafeSubmissionSet(request_identity=_identity(), submissions=subs)
    return DecisionRequest(
        identity=_identity(),
        kind=kind,
        side_id="p1",
        team_member_count=6,
        active_identity="Garchomp",
        safe_submissions=sss,
        is_update=False,
    )


# ---------------------------------------------------------------------------
# Priority order: move > revive > switch > team > tera-move > default
# ---------------------------------------------------------------------------


class TestHeuristicPolicyPriority:
    def test_prefers_normal_move_over_default(self) -> None:
        m = _move(1, "surf")
        dr = _request(RequestKind.MOVE, m, _default())
        result = HeuristicPolicy.select(dr)
        assert result == m

    def test_picks_first_normal_move_when_multiple(self) -> None:
        m1 = _move(1, "surf")
        m2 = _move(2, "flamethrower")
        dr = _request(RequestKind.MOVE, m1, m2, _default())
        result = HeuristicPolicy.select(dr)
        assert result == m1

    def test_prefers_revive_over_switch_and_default(self) -> None:
        rv = _revive(4)
        sw = _switch(2)
        dr = _request(RequestKind.REVIVAL, rv, sw, _default())
        result = HeuristicPolicy.select(dr)
        assert result == rv

    def test_prefers_switch_over_tera_move_and_default(self) -> None:
        sw = _switch(2)
        tera = _move(1, "surf", tera=True)
        dr = _request(RequestKind.FORCED_SWITCH, sw, tera, _default())
        result = HeuristicPolicy.select(dr)
        assert result == sw

    def test_prefers_team_order_over_tera_and_default(self) -> None:
        tm = _team((1, 2, 3, 4, 5, 6))
        tera = _move(1, "surf", tera=True)
        dr = _request(RequestKind.TEAM_PREVIEW, tm, tera, _default())
        result = HeuristicPolicy.select(dr)
        assert result == tm

    def test_prefers_tera_move_over_default(self) -> None:
        tera = _move(1, "icebeam", tera=True)
        dr = _request(RequestKind.MOVE, tera, _default())
        result = HeuristicPolicy.select(dr)
        assert result == tera

    def test_falls_back_to_default(self) -> None:
        dr = _request(RequestKind.MOVE, _default())
        result = HeuristicPolicy.select(dr)
        assert result == _default()

    def test_empty_submission_set_raises(self) -> None:
        dr = _request(RequestKind.MOVE)
        with pytest.raises(NoLegalActionError):
            HeuristicPolicy.select(dr)


# ---------------------------------------------------------------------------
# Determinism and immutability
# ---------------------------------------------------------------------------


class TestHeuristicPolicyDeterminism:
    def test_same_input_same_output(self) -> None:
        m = _move(1, "surf")
        dr = _request(RequestKind.MOVE, m, _default())
        assert HeuristicPolicy.select(dr) == HeuristicPolicy.select(dr)

    def test_does_not_mutate_safe_submission_set(self) -> None:
        m = _move(1, "surf")
        dr = _request(RequestKind.MOVE, m, _default())
        original_count = len(dr.safe_submissions.submissions)
        HeuristicPolicy.select(dr)
        assert len(dr.safe_submissions.submissions) == original_count

    def test_does_not_mutate_decision_request(self) -> None:
        m = _move(1, "surf")
        dr = _request(RequestKind.MOVE, m, _default())
        original_kind = dr.kind
        HeuristicPolicy.select(dr)
        assert dr.kind == original_kind
