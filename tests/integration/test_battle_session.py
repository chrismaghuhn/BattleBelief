from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from battlebelief_core.domain.actions.submission import (
    ActionKind,
    ActionProvenance,
    BattleSubmission,
)
from battlebelief_runtime.adapters.showdown_protocol.frame_decoder import RoomLine
from battlebelief_runtime.composition.battle_session import BattleSession
from battlebelief_runtime.errors.actions import ServerInvalidChoice, ServerUnavailableChoice
from battlebelief_runtime.errors.protocol import (
    Disconnect,
    MalformedProtocolMessage,
    ReducerInvariantFailure,
    RequestStateReconciliationMismatch,
    TimerOrForfeit,
    UnknownProtocolEvent,
)
from battlebelief_runtime.testing.fake_connection import FakeConnection

_ROOT = Path(__file__).resolve().parents[2]
_REQUESTS = _ROOT / "tests" / "fixtures" / "requests"
_ROOM = "battle-gen9ou-1"


def _line(payload: str, room_id: str = _ROOM) -> RoomLine:
    return RoomLine(room_id=room_id, payload=payload)


def _request(name: str, rqid: int | None = None, **changes: Any) -> str:
    data = json.loads((_REQUESTS / name).read_text(encoding="utf-8"))
    if rqid is not None:
        data["rqid"] = rqid
    for key, value in changes.items():
        data[key] = value
    return "|request|" + json.dumps(data, separators=(",", ":"))


def _reconciliation_request() -> str:
    data = json.loads((_REQUESTS / "move.json").read_text(encoding="utf-8"))
    data["rqid"] = 5
    data["side"]["pokemon"][0]["ident"] = "p1: Wrong"
    return "|request|" + json.dumps(data, separators=(",", ":"))


def _metadata(*, start: bool = True, active: bool = True) -> list[RoomLine]:
    payloads = [
        "|init|battle",
        "|gametype|singles",
        "|gen|9",
        "|tier|[Gen 9] OU",
        "|player|p1|ash|1|",
        "|player|p2|misty|1|",
    ]
    if start:
        payloads.append("|start|")
    if active:
        payloads.append("|switch|p1a: Garchomp|Garchomp, L50, M|183/183")
    return [_line(payload) for payload in payloads]


def _run(
    lines: list[RoomLine | BaseException],
    *,
    policy: object | None = None,
) -> tuple[Any, FakeConnection]:
    connection = FakeConnection(lines)
    session = BattleSession(
        connection=connection,
        room_id=_ROOM,
        our_user_id="ash",
        policy=policy,
    )
    return asyncio.run(session.run()), connection


class _FixedPolicy:
    def __init__(self, submission: BattleSubmission) -> None:
        self.submission = submission

    def select(self, request: object) -> BattleSubmission:
        return self.submission


def test_request_before_turn_sends_exactly_one_action() -> None:
    result, connection = _run([*_metadata(), _line(_request("move.json", 5))])

    assert result.primary_error is None
    assert connection.sent_room == [(_ROOM, "move 1|5")]
    assert result.explicit_request_submissions == 1


def test_turn_before_request_still_sends_after_request() -> None:
    result, connection = _run([*_metadata(), _line("|turn|1"), _line(_request("move.json", 5))])

    assert result.primary_error is None
    assert connection.sent_room == [(_ROOM, "move 1|5")]


def test_forced_switch_sends_alive_switch_slot() -> None:
    result, connection = _run([*_metadata(), _line(_request("forced-switch.json", 8))])

    assert result.primary_error is None
    assert connection.sent_room == [(_ROOM, "switch 2|8")]


def test_wait_sends_nothing() -> None:
    result, connection = _run([*_metadata(), _line(_request("wait.json", 2))])

    assert result.primary_error is None
    assert connection.sent_room == []
    assert result.explicit_request_submissions == 0
    assert result.default_submissions == 0


def test_identical_request_is_not_submitted_twice() -> None:
    request = _line(_request("move.json", 5))
    result, connection = _run(
        [
            *_metadata(),
            request,
            _line("|switch|p1a: Rotom|Rotom, L50|100/100"),
            request,
        ]
    )

    assert result.primary_error is None
    assert connection.sent_room == [(_ROOM, "move 1|5")]


@pytest.mark.parametrize("missing_rqid", [False, True])
def test_stale_or_missing_rqid_is_never_sent(missing_rqid: bool) -> None:
    if missing_rqid:
        missing = json.loads((_REQUESTS / "move.json").read_text(encoding="utf-8"))
        del missing["rqid"]
        lines = [*_metadata(), _line("|request|" + json.dumps(missing))]
        expected = MalformedProtocolMessage
    else:
        lines = [*_metadata(), _line(_request("move.json", 5)), _line(_request("wait.json", 4))]
        expected = RuntimeError

    result, connection = _run(lines)

    assert isinstance(result.primary_error, expected)
    if not missing_rqid:
        assert getattr(result.primary_error, "code", None) == "stale_rqid"
    if missing_rqid:
        assert connection.sent_room == []
    else:
        assert connection.sent_room == [(_ROOM, "move 1|5")]


def test_policy_out_of_set_is_blocked_by_action_gate() -> None:
    foreign = BattleSubmission(
        kind=ActionKind.MOVE,
        provenance=ActionProvenance.EXPLICIT_REQUEST,
        slot=4,
        move_id="moonblast",
    )
    result, connection = _run(
        [*_metadata(), _line(_request("move.json", 5))],
        policy=_FixedPolicy(foreign),
    )

    assert result.primary_error is not None
    assert getattr(result.primary_error, "code", None) == "local_action_gate_rejection"
    assert connection.sent_room == []


@pytest.mark.parametrize(
    ("fixture", "submission", "wire"),
    [
        (
            "move-tera.json",
            BattleSubmission(
                kind=ActionKind.MOVE,
                provenance=ActionProvenance.EXPLICIT_REQUEST,
                slot=1,
                move_id="earthquake",
                terastallize=True,
            ),
            "move 1 terastallize|6",
        ),
        (
            "team-preview.json",
            BattleSubmission(
                kind=ActionKind.TEAM,
                provenance=ActionProvenance.EXPLICIT_REQUEST,
                team_order=(1, 2, 3, 4, 5, 6),
            ),
            "team 123456|6",
        ),
    ],
)
def test_tera_and_team_preview_actions_are_encodable(
    fixture: str, submission: BattleSubmission, wire: str
) -> None:
    result, connection = _run(
        [*_metadata(), _line(_request(fixture, 6))],
        policy=_FixedPolicy(submission),
    )

    assert result.primary_error is None
    assert connection.sent_room == [(_ROOM, wire)]


@pytest.mark.parametrize(
    ("payload", "error_type"),
    [
        ("|error|[Invalid choice] Can't do that", ServerInvalidChoice),
        ("|error|[Unavailable choice] Not available", ServerUnavailableChoice),
    ],
)
def test_invalid_and_unavailable_server_errors_abort_on_first_event(
    payload: str, error_type: type[RuntimeError]
) -> None:
    result, connection = _run([_line(payload)])

    assert isinstance(result.primary_error, error_type)
    assert connection.sent_room == []


@pytest.mark.parametrize(
    ("lines", "error_type"),
    [
        ([_line("|-notarealwiretype|p1a: Garchomp")], UnknownProtocolEvent),
        ([_line("|switch|p1a: Garchomp")], MalformedProtocolMessage),
        (
            [*_metadata(), _line(_reconciliation_request())],
            RequestStateReconciliationMismatch,
        ),
        ([_line("|player|p3|ash|1|")], ReducerInvariantFailure),
        ([_line("|inactive|You lost due to inactivity.")], TimerOrForfeit),
        ([Disconnect("socket closed")], Disconnect),
    ],
)
def test_each_protocol_failure_has_one_primary_class(
    lines: list[RoomLine | BaseException], error_type: type[BaseException]
) -> None:
    result, connection = _run(lines)

    assert isinstance(result.primary_error, error_type)
    assert connection.sent_room == []


def test_request_before_player_declaration_resolves_after_metadata() -> None:
    lines = [
        _line("|init|battle"),
        _line("|gametype|singles"),
        _line("|gen|9"),
        _line("|tier|[Gen 9] OU"),
        _line(_request("move.json", 5)),
        _line("|player|p1|ash|1|"),
        _line("|player|p2|misty|1|"),
        _line("|switch|p1a: Garchomp|Garchomp, L50, M|183/183"),
        _line("|start|"),
    ]

    result, connection = _run(lines)

    assert result.primary_error is None
    assert connection.sent_room == [(_ROOM, "move 1|5")]


def test_request_before_matching_switch_resolves_once() -> None:
    result, connection = _run(
        [
            *_metadata(active=False),
            _line(_request("move.json", 5)),
            _line("|switch|p1a: Garchomp|Garchomp, L50, M|183/183"),
        ]
    )

    assert result.primary_error is None
    assert connection.sent_room == [(_ROOM, "move 1|5")]


def test_request_after_battle_start_does_not_wait_for_missing_metadata() -> None:
    result, connection = _run(
        [
            _line("|init|battle"),
            _line("|player|p1|ash|1|"),
            _line("|player|p2|misty|1|"),
            _line("|start|"),
            _line(_request("move.json", 5)),
        ]
    )

    assert isinstance(result.primary_error, RequestStateReconciliationMismatch)
    assert connection.sent_room == []


def test_pending_request_with_contradictory_side_aborts_without_send() -> None:
    lines = [
        _line("|init|battle"),
        _line("|gametype|singles"),
        _line("|gen|9"),
        _line("|tier|[Gen 9] OU"),
        _line(_request("move.json", 5)),
        _line("|player|p1|misty|1|"),
        _line("|player|p2|ash|1|"),
    ]

    result, connection = _run(lines)

    assert isinstance(result.primary_error, RequestStateReconciliationMismatch)
    assert connection.sent_room == []


def test_two_pending_requests_execute_only_the_newest_rqid() -> None:
    result, connection = _run(
        [
            *_metadata(active=False),
            _line(_request("move.json", 4)),
            _line(_request("move.json", 5)),
            _line("|switch|p1a: Garchomp|Garchomp, L50, M|183/183"),
        ]
    )

    assert result.primary_error is None
    assert connection.sent_room == [(_ROOM, "move 1|5")]


def test_battle_end_discards_pending_request() -> None:
    result, connection = _run(
        [*_metadata(active=False), _line(_request("move.json", 5)), _line("|win|misty")]
    )

    assert result.primary_error is None
    assert result.state.winner == "misty"
    assert connection.sent_room == []


def test_revival_sends_only_fainted_inactive_target() -> None:
    result, connection = _run([*_metadata(), _line(_request("reviving.json", 9))])

    assert result.primary_error is None
    assert connection.sent_room == [(_ROOM, "switch 3|9")]


def test_explicit_and_default_submissions_are_counted_separately() -> None:
    result, connection = _run(
        [
            *_metadata(),
            _line(_request("move.json", 5)),
            _line(
                _request(
                    "move.json",
                    6,
                    active=[{"moves": [], "canTerastallize": "", "maybeDisabled": True}],
                )
            ),
        ]
    )

    assert result.primary_error is None
    assert connection.sent_room == [(_ROOM, "move 1|5"), (_ROOM, "default|6")]
    assert result.explicit_request_submissions == 1
    assert result.default_submissions == 1


def test_room_controls_and_embedded_request_text_do_not_trigger_actions() -> None:
    lines = [
        _line("|title|Ash vs. Misty"),
        _line("|J|ash"),
        _line("|c:|1700000000|ash|embedded |request|{} text"),
        *_metadata(),
        _line("|move|p1a: Garchomp|Earthquake|p2a: Togekiss"),
        _line(_request("move.json", 5)),
        _line("|L|ash"),
    ]

    result, connection = _run(lines)

    assert result.primary_error is None
    assert result.room_control_or_chat_count == 4
    assert connection.sent_room == [(_ROOM, "move 1|5")]


def test_spacer_before_battle_start_only_increments_ignored_display_count() -> None:
    result, connection = _run(
        [
            _line("|init|battle"),
            _line("|"),
            _line("|start|"),
        ]
    )

    assert result.primary_error is None
    assert result.state.battle_started is True
    assert result.state.ignored_display_count == 1
    assert result.room_control_or_chat_count == 0
    assert connection.sent_room == []
