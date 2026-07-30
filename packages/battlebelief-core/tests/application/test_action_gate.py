from __future__ import annotations

import pytest

from battlebelief_core.application.safety.action_gate import ActionSafetyGate
from battlebelief_core.domain.actions.submission import (
    ActionKind,
    ActionProvenance,
    BattleSubmission,
    RequestIdentity,
    SafeSubmissionSet,
)
from battlebelief_core.errors import LocalActionGateRejection, StaleRequestIdentity

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _identity(rqid: int = 3) -> RequestIdentity:
    return RequestIdentity(room_id="battle-gen9ou-1", rqid=rqid, request_digest="abc")


def _move() -> BattleSubmission:
    return BattleSubmission(
        kind=ActionKind.MOVE,
        provenance=ActionProvenance.EXPLICIT_REQUEST,
        slot=1,
        move_id="surf",
    )


def _default() -> BattleSubmission:
    return BattleSubmission(kind=ActionKind.DEFAULT, provenance=ActionProvenance.SERVER_DEFAULT)


def _sss(*subs: BattleSubmission, rqid: int = 3) -> SafeSubmissionSet:
    return SafeSubmissionSet(request_identity=_identity(rqid), submissions=subs)


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


class TestActionSafetyGate:
    def test_authorizes_valid_move(self) -> None:
        sub = _move()
        sss = _sss(sub, _default())
        result = ActionSafetyGate.authorize(
            candidate=sub,
            candidate_request=_identity(),
            latest=sss,
        )
        assert result == sub

    def test_authorizes_newly_constructed_equal_submission(self) -> None:
        # A value-equal copy must be accepted — gate uses equality, not identity
        in_set = _move()
        copy = BattleSubmission(
            kind=ActionKind.MOVE,
            provenance=ActionProvenance.EXPLICIT_REQUEST,
            slot=1,
            move_id="surf",
        )
        sss = _sss(in_set, _default())
        result = ActionSafetyGate.authorize(
            candidate=copy,
            candidate_request=_identity(),
            latest=sss,
        )
        assert result == copy

    def test_authorizes_default(self) -> None:
        sub = _default()
        sss = _sss(_move(), sub)
        result = ActionSafetyGate.authorize(
            candidate=sub,
            candidate_request=_identity(),
            latest=sss,
        )
        assert result == sub

    def test_stale_request_identity_raises(self) -> None:
        sub = _move()
        sss = _sss(sub, rqid=3)
        with pytest.raises(StaleRequestIdentity):
            ActionSafetyGate.authorize(
                candidate=sub,
                candidate_request=_identity(rqid=2),  # older
                latest=sss,
            )

    def test_absent_submission_raises(self) -> None:
        other = BattleSubmission(
            kind=ActionKind.MOVE,
            provenance=ActionProvenance.EXPLICIT_REQUEST,
            slot=2,
            move_id="flamethrower",
        )
        sss = _sss(_move(), _default())
        with pytest.raises(LocalActionGateRejection):
            ActionSafetyGate.authorize(
                candidate=other,
                candidate_request=_identity(),
                latest=sss,
            )

    def test_stale_checked_before_absent(self) -> None:
        # stale rqid should short-circuit before membership check
        other = BattleSubmission(
            kind=ActionKind.MOVE,
            provenance=ActionProvenance.EXPLICIT_REQUEST,
            slot=2,
            move_id="flamethrower",
        )
        sss = _sss(_move(), rqid=3)
        with pytest.raises(StaleRequestIdentity):
            ActionSafetyGate.authorize(
                candidate=other,
                candidate_request=_identity(rqid=1),
                latest=sss,
            )
