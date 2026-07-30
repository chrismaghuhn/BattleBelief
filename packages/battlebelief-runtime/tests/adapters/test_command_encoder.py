from __future__ import annotations

from battlebelief_core.domain.actions.submission import (
    ActionKind,
    ActionProvenance,
    BattleSubmission,
)
from battlebelief_runtime.adapters.showdown_protocol.command_encoder import encode_submission


def _move(slot: int, move_id: str, tera: bool = False) -> BattleSubmission:
    return BattleSubmission(
        kind=ActionKind.MOVE,
        provenance=ActionProvenance.EXPLICIT_REQUEST,
        slot=slot,
        move_id=move_id,
        terastallize=tera,
    )


class TestExactOutputs:
    def test_move(self) -> None:
        assert encode_submission(_move(1, "earthquake")) == "move 1"

    def test_move_terastallize(self) -> None:
        assert encode_submission(_move(1, "earthquake", tera=True)) == "move 1 terastallize"

    def test_switch(self) -> None:
        sub = BattleSubmission(
            kind=ActionKind.SWITCH, provenance=ActionProvenance.EXPLICIT_REQUEST, slot=3
        )
        assert encode_submission(sub) == "switch 3"

    def test_team(self) -> None:
        sub = BattleSubmission(
            kind=ActionKind.TEAM,
            provenance=ActionProvenance.EXPLICIT_REQUEST,
            team_order=(1, 2, 3, 4, 5, 6),
        )
        assert encode_submission(sub) == "team 123456"

    def test_default(self) -> None:
        sub = BattleSubmission(kind=ActionKind.DEFAULT, provenance=ActionProvenance.SERVER_DEFAULT)
        assert encode_submission(sub) == "default"


class TestReviveEncodesAsSwitch:
    def test_revive_wire_encodes_as_switch(self) -> None:
        sub = BattleSubmission(
            kind=ActionKind.REVIVE, provenance=ActionProvenance.EXPLICIT_REQUEST, slot=3
        )
        assert encode_submission(sub) == "switch 3"


class TestPolicyOutputEncodesExactly:
    def test_policy_selected_move_encodes_cleanly(self) -> None:
        # A HeuristicPolicy.select() result should encode without modification.
        sub = _move(2, "swordsdance")
        assert encode_submission(sub) == "move 2"

    def test_non_default_team_order_encodes_in_given_sequence(self) -> None:
        sub = BattleSubmission(
            kind=ActionKind.TEAM,
            provenance=ActionProvenance.EXPLICIT_REQUEST,
            team_order=(3, 1, 2, 6, 5, 4),
        )
        assert encode_submission(sub) == "team 312654"
