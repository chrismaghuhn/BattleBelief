from __future__ import annotations

import pytest

from battlebelief_core.domain.actions.decision_request import DecisionRequest, RequestKind
from battlebelief_core.domain.actions.submission import (
    ActionKind,
    ActionProvenance,
    BattleSubmission,
    RequestIdentity,
    SafeSubmissionSet,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_IDENTITY = RequestIdentity(room_id="battle-gen9ou-1", rqid=3, request_digest="abc123")


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


def _default() -> BattleSubmission:
    return BattleSubmission(kind=ActionKind.DEFAULT, provenance=ActionProvenance.SERVER_DEFAULT)


def _team(order: tuple[int, ...]) -> BattleSubmission:
    return BattleSubmission(
        kind=ActionKind.TEAM,
        provenance=ActionProvenance.EXPLICIT_REQUEST,
        team_order=order,
    )


# ---------------------------------------------------------------------------
# ActionKind / RequestKind / ActionProvenance
# ---------------------------------------------------------------------------


class TestEnums:
    def test_action_kind_values(self) -> None:
        assert ActionKind.MOVE == "move"
        assert ActionKind.SWITCH == "switch"
        assert ActionKind.REVIVE == "revive"
        assert ActionKind.TEAM == "team"
        assert ActionKind.DEFAULT == "default"

    def test_request_kind_values(self) -> None:
        assert RequestKind.MOVE == "move"
        assert RequestKind.FORCED_SWITCH == "forced_switch"
        assert RequestKind.REVIVAL == "revival"
        assert RequestKind.TEAM_PREVIEW == "team_preview"
        assert RequestKind.WAIT == "wait"

    def test_provenance_values(self) -> None:
        assert ActionProvenance.EXPLICIT_REQUEST == "explicit_request"
        assert ActionProvenance.SERVER_DEFAULT == "server_default"


# ---------------------------------------------------------------------------
# RequestIdentity
# ---------------------------------------------------------------------------


class TestRequestIdentity:
    def test_fields_stored(self) -> None:
        ri = RequestIdentity(room_id="battle-gen9ou-99", rqid=7, request_digest="d1g")
        assert ri.room_id == "battle-gen9ou-99"
        assert ri.rqid == 7
        assert ri.request_digest == "d1g"

    def test_is_frozen(self) -> None:
        ri = RequestIdentity(room_id="x", rqid=1, request_digest="y")
        with pytest.raises((AttributeError, TypeError)):
            ri.rqid = 99  # type: ignore[misc]

    def test_value_equality(self) -> None:
        a = RequestIdentity(room_id="r", rqid=1, request_digest="d")
        b = RequestIdentity(room_id="r", rqid=1, request_digest="d")
        assert a == b


# ---------------------------------------------------------------------------
# BattleSubmission — form invariants
# ---------------------------------------------------------------------------


class TestBattleSubmissionMove:
    def test_valid_move(self) -> None:
        s = _move(1, "surf")
        assert s.kind == ActionKind.MOVE
        assert s.slot == 1
        assert s.move_id == "surf"
        assert s.terastallize is False
        assert s.team_order == ()

    def test_valid_move_tera(self) -> None:
        s = _move(2, "icebeam", tera=True)
        assert s.terastallize is True

    def test_move_slot_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            BattleSubmission(
                kind=ActionKind.MOVE,
                provenance=ActionProvenance.EXPLICIT_REQUEST,
                slot=0,
                move_id="surf",
            )

    def test_move_slot_too_high_raises(self) -> None:
        with pytest.raises(ValueError):
            BattleSubmission(
                kind=ActionKind.MOVE,
                provenance=ActionProvenance.EXPLICIT_REQUEST,
                slot=5,
                move_id="surf",
            )

    def test_move_without_move_id_raises(self) -> None:
        with pytest.raises(ValueError):
            BattleSubmission(
                kind=ActionKind.MOVE,
                provenance=ActionProvenance.EXPLICIT_REQUEST,
                slot=1,
            )

    def test_move_with_team_order_raises(self) -> None:
        with pytest.raises(ValueError):
            BattleSubmission(
                kind=ActionKind.MOVE,
                provenance=ActionProvenance.EXPLICIT_REQUEST,
                slot=1,
                move_id="surf",
                team_order=(1, 2, 3),
            )

    def test_move_is_frozen(self) -> None:
        s = _move(1, "surf")
        with pytest.raises((AttributeError, TypeError)):
            s.slot = 2  # type: ignore[misc]

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"slot": True},
            {"move_id": 1},
            {"terastallize": 1},
            {"kind": "move"},
            {"provenance": "explicit_request"},
            {"move_id": "Secret Nickname"},
        ],
    )
    def test_move_rejects_schema_incompatible_runtime_types(
        self, kwargs: dict[str, object]
    ) -> None:
        values: dict[str, object] = {
            "kind": ActionKind.MOVE,
            "provenance": ActionProvenance.EXPLICIT_REQUEST,
            "slot": 1,
            "move_id": "surf",
            "terastallize": False,
        }
        values.update(kwargs)
        with pytest.raises(ValueError):
            BattleSubmission(**values)  # type: ignore[arg-type]


class TestBattleSubmissionSwitch:
    def test_valid_switch(self) -> None:
        s = _switch(3)
        assert s.kind == ActionKind.SWITCH
        assert s.slot == 3
        assert s.move_id is None
        assert s.terastallize is False

    def test_switch_slot_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            BattleSubmission(
                kind=ActionKind.SWITCH,
                provenance=ActionProvenance.EXPLICIT_REQUEST,
                slot=7,
            )

    def test_switch_with_tera_raises(self) -> None:
        with pytest.raises(ValueError):
            BattleSubmission(
                kind=ActionKind.SWITCH,
                provenance=ActionProvenance.EXPLICIT_REQUEST,
                slot=2,
                terastallize=True,
            )

    def test_switch_with_move_id_raises(self) -> None:
        with pytest.raises(ValueError):
            BattleSubmission(
                kind=ActionKind.SWITCH,
                provenance=ActionProvenance.EXPLICIT_REQUEST,
                slot=2,
                move_id="surf",
            )


class TestBattleSubmissionRevive:
    def test_valid_revive(self) -> None:
        s = _revive(4)
        assert s.kind == ActionKind.REVIVE
        assert s.slot == 4

    def test_revive_slot_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            BattleSubmission(
                kind=ActionKind.REVIVE,
                provenance=ActionProvenance.EXPLICIT_REQUEST,
                slot=0,
            )

    def test_revive_with_tera_raises(self) -> None:
        with pytest.raises(ValueError):
            BattleSubmission(
                kind=ActionKind.REVIVE,
                provenance=ActionProvenance.EXPLICIT_REQUEST,
                slot=2,
                terastallize=True,
            )

    def test_revive_with_move_id_raises(self) -> None:
        with pytest.raises(ValueError):
            BattleSubmission(
                kind=ActionKind.REVIVE,
                provenance=ActionProvenance.EXPLICIT_REQUEST,
                slot=2,
                move_id="surf",
            )


class TestBattleSubmissionTeam:
    def test_valid_team(self) -> None:
        s = _team((1, 2, 3))
        assert s.kind == ActionKind.TEAM
        assert s.team_order == (1, 2, 3)
        assert s.slot is None
        assert s.move_id is None

    def test_team_empty_order_raises(self) -> None:
        with pytest.raises(ValueError):
            BattleSubmission(
                kind=ActionKind.TEAM,
                provenance=ActionProvenance.EXPLICIT_REQUEST,
                team_order=(),
            )

    def test_team_with_slot_raises(self) -> None:
        with pytest.raises(ValueError):
            BattleSubmission(
                kind=ActionKind.TEAM,
                provenance=ActionProvenance.EXPLICIT_REQUEST,
                slot=1,
                team_order=(1, 2),
            )

    def test_team_with_tera_raises(self) -> None:
        with pytest.raises(ValueError):
            BattleSubmission(
                kind=ActionKind.TEAM,
                provenance=ActionProvenance.EXPLICIT_REQUEST,
                team_order=(1, 2),
                terastallize=True,
            )

    @pytest.mark.parametrize("order", [(1, 1), (0, 1), (1, 7)])
    def test_team_order_must_use_unique_slots_one_through_six(self, order: tuple[int, ...]) -> None:
        with pytest.raises(ValueError):
            _team(order)


class TestBattleSubmissionDefault:
    def test_valid_default(self) -> None:
        s = _default()
        assert s.kind == ActionKind.DEFAULT
        assert s.provenance == ActionProvenance.SERVER_DEFAULT
        assert s.slot is None
        assert s.move_id is None
        assert s.terastallize is False
        assert s.team_order == ()

    def test_default_with_slot_raises(self) -> None:
        with pytest.raises(ValueError):
            BattleSubmission(
                kind=ActionKind.DEFAULT,
                provenance=ActionProvenance.SERVER_DEFAULT,
                slot=1,
            )

    def test_default_with_explicit_provenance_raises(self) -> None:
        with pytest.raises(ValueError):
            BattleSubmission(
                kind=ActionKind.DEFAULT,
                provenance=ActionProvenance.EXPLICIT_REQUEST,
            )

    def test_non_default_with_server_default_provenance_raises(self) -> None:
        with pytest.raises(ValueError):
            BattleSubmission(
                kind=ActionKind.MOVE,
                provenance=ActionProvenance.SERVER_DEFAULT,
                slot=1,
                move_id="surf",
            )


# ---------------------------------------------------------------------------
# SafeSubmissionSet
# ---------------------------------------------------------------------------


class TestSafeSubmissionSet:
    def test_contains_returns_true_for_equal_submission(self) -> None:
        sub = _move(1, "surf")
        sss = SafeSubmissionSet(request_identity=_IDENTITY, submissions=(sub,))
        assert sss.contains(_move(1, "surf"))

    def test_contains_returns_false_for_absent(self) -> None:
        sss = SafeSubmissionSet(request_identity=_IDENTITY, submissions=(_move(1, "surf"),))
        assert not sss.contains(_move(2, "flamethrower"))

    def test_wait_has_empty_submissions(self) -> None:
        sss = SafeSubmissionSet(request_identity=_IDENTITY, submissions=())
        assert sss.submissions == ()

    def test_is_frozen(self) -> None:
        sss = SafeSubmissionSet(request_identity=_IDENTITY, submissions=())
        with pytest.raises((AttributeError, TypeError)):
            sss.submissions = (_default(),)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DecisionRequest
# ---------------------------------------------------------------------------


class TestDecisionRequest:
    def _make_move_request(self) -> DecisionRequest:
        sss = SafeSubmissionSet(
            request_identity=_IDENTITY,
            submissions=(_move(1, "surf"), _default()),
        )
        return DecisionRequest(
            identity=_IDENTITY,
            kind=RequestKind.MOVE,
            side_id="p1",
            team_member_count=6,
            active_identity="Garchomp",
            safe_submissions=sss,
            is_update=False,
        )

    def test_fields_stored(self) -> None:
        dr = self._make_move_request()
        assert dr.kind == RequestKind.MOVE
        assert dr.side_id == "p1"
        assert dr.team_member_count == 6
        assert dr.active_identity == "Garchomp"
        assert dr.is_update is False

    def test_is_frozen(self) -> None:
        dr = self._make_move_request()
        with pytest.raises((AttributeError, TypeError)):
            dr.side_id = "p2"  # type: ignore[misc]

    def test_wait_has_no_active_identity(self) -> None:
        sss = SafeSubmissionSet(request_identity=_IDENTITY, submissions=())
        dr = DecisionRequest(
            identity=_IDENTITY,
            kind=RequestKind.WAIT,
            side_id="p1",
            team_member_count=6,
            active_identity=None,
            safe_submissions=sss,
            is_update=False,
        )
        assert dr.active_identity is None

    def test_no_raw_dict_or_wire_content(self) -> None:
        dr = self._make_move_request()
        assert not hasattr(dr, "raw")
        assert not hasattr(dr, "json")
        assert not hasattr(dr, "wire")
