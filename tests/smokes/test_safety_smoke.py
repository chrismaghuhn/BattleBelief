from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from battlebelief_core.domain.actions.decision_request import DecisionRequest
from battlebelief_core.domain.actions.submission import (
    ActionKind,
    ActionProvenance,
    BattleSubmission,
)
from battlebelief_core.errors import LocalActionGateRejection, StaleRequestIdentity
from battlebelief_runtime.adapters.showdown_protocol.frame_decoder import RoomLine, decode_frame
from battlebelief_runtime.composition.battle_session import (
    BattleSession,
    BattleSessionResult,
)
from battlebelief_runtime.errors.actions import ServerInvalidChoice, ServerUnavailableChoice
from battlebelief_runtime.errors.protocol import (
    MalformedProtocolMessage,
    RequestStateReconciliationMismatch,
    TimerOrForfeit,
    UnknownProtocolEvent,
)
from battlebelief_runtime.testing.fake_connection import FakeConnection

_ROOT = Path(__file__).resolve().parents[2]
_REQUESTS = _ROOT / "tests" / "fixtures" / "requests"
_ROOM = "battle-gen9ou-safety"
_OTHER_ROOM = "battle-gen9ou-other"


def _line(payload: str, room_id: str = _ROOM) -> RoomLine:
    return RoomLine(room_id=room_id, payload=payload)


def _request(name: str, rqid: int, **changes: Any) -> str:
    data = json.loads((_REQUESTS / name).read_text(encoding="utf-8"))
    data["rqid"] = rqid
    data.update(changes)
    return "|request|" + json.dumps(data, separators=(",", ":"))


def _request_without_rqid(name: str) -> str:
    data = json.loads((_REQUESTS / name).read_text(encoding="utf-8"))
    del data["rqid"]
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


def _first_submission(request: DecisionRequest) -> BattleSubmission:
    return request.safe_submissions.submissions[0]


class _RecordingPolicy:
    def __init__(
        self,
        selector: Callable[[DecisionRequest], BattleSubmission] = _first_submission,
    ) -> None:
        self._selector = selector
        self.selections: list[tuple[DecisionRequest, BattleSubmission]] = []

    def select(self, request: DecisionRequest) -> BattleSubmission:
        candidate = self._selector(request)
        self.selections.append((request, candidate))
        return candidate


class _UnexpectedPolicy:
    def select(self, request: DecisionRequest) -> BattleSubmission:
        raise AssertionError(f"policy must not be called for {request.kind}")


def _run(
    lines: list[RoomLine | BaseException],
    *,
    policy: object,
) -> tuple[BattleSessionResult, FakeConnection]:
    connection = FakeConnection(lines)
    session = BattleSession(
        connection=connection,
        room_id=_ROOM,
        our_user_id="ash",
        policy=policy,
    )
    return asyncio.run(session.run()), connection


def _assert_validated_sends(
    connection: FakeConnection,
    policy: _RecordingPolicy,
    expected_commands: list[str],
    *,
    result: BattleSessionResult,
) -> None:
    assert connection.sent_room == [(_ROOM, command) for command in expected_commands]
    assert len(connection.sent_room) == len(policy.selections)

    identities = []
    for (room_id, command), (request, candidate) in zip(
        connection.sent_room, policy.selections, strict=True
    ):
        safe_set = request.safe_submissions
        assert room_id == request.identity.room_id == _ROOM
        assert safe_set.request_identity == request.identity
        assert safe_set.contains(candidate)
        assert command.endswith(f"|{request.identity.rqid}")
        identities.append(request.identity)

    assert len(identities) == len(set(identities))
    assert result.explicit_request_submissions == sum(
        candidate.provenance == ActionProvenance.EXPLICIT_REQUEST
        for _, candidate in policy.selections
    )
    assert result.default_submissions == sum(
        candidate.provenance == ActionProvenance.SERVER_DEFAULT
        for _, candidate in policy.selections
    )


def _assert_primary_error(
    result: BattleSessionResult,
    error_type: type[BaseException],
    code: str,
) -> None:
    assert type(result.primary_error) is error_type
    assert getattr(result.primary_error, "code", None) == code


def test_normal_move_uses_current_safe_set_once() -> None:
    policy = _RecordingPolicy()
    result, connection = _run(
        [*_metadata(), _line(_request("move.json", 5))],
        policy=policy,
    )

    assert result.primary_error is None
    assert result.explicit_request_submissions == 1
    assert result.default_submissions == 0
    _assert_validated_sends(connection, policy, ["/choose move 1|5"], result=result)


def test_request_after_turn_is_the_decision_trigger() -> None:
    policy = _RecordingPolicy()
    result, connection = _run(
        [*_metadata(), _line("|turn|1"), _line(_request("move.json", 6))],
        policy=policy,
    )

    assert result.primary_error is None
    assert result.state.turn == 1
    _assert_validated_sends(connection, policy, ["/choose move 1|6"], result=result)


@pytest.mark.parametrize(
    ("fixture", "rqid", "kind", "command"),
    [
        ("forced-switch.json", 8, ActionKind.SWITCH, "/choose switch 2|8"),
        ("reviving.json", 9, ActionKind.REVIVE, "/choose switch 3|9"),
    ],
)
def test_forced_switch_and_revival_remain_distinct_safe_actions(
    fixture: str,
    rqid: int,
    kind: ActionKind,
    command: str,
) -> None:
    policy = _RecordingPolicy()
    result, connection = _run(
        [*_metadata(), _line(_request(fixture, rqid))],
        policy=policy,
    )

    assert result.primary_error is None
    assert policy.selections[0][1].kind == kind
    assert policy.selections[0][1].provenance == ActionProvenance.EXPLICIT_REQUEST
    _assert_validated_sends(connection, policy, [command], result=result)


def test_tera_variant_is_validated_before_encoding() -> None:
    def select_tera(request: DecisionRequest) -> BattleSubmission:
        return next(sub for sub in request.safe_submissions.submissions if sub.terastallize)

    policy = _RecordingPolicy(select_tera)
    result, connection = _run(
        [*_metadata(), _line(_request("move-tera.json", 10))],
        policy=policy,
    )

    assert result.primary_error is None
    assert policy.selections[0][1].provenance == ActionProvenance.EXPLICIT_REQUEST
    _assert_validated_sends(
        connection,
        policy,
        ["/choose move 1 terastallize|10"],
        result=result,
    )


def test_maybe_trapped_request_excludes_voluntary_switches() -> None:
    policy = _RecordingPolicy()
    result, connection = _run(
        [*_metadata(), _line(_request("maybe-trapped.json", 11))],
        policy=policy,
    )

    assert result.primary_error is None
    safe_actions = policy.selections[0][0].safe_submissions.submissions
    assert all(action.kind != ActionKind.SWITCH for action in safe_actions)
    _assert_validated_sends(connection, policy, ["/choose move 1|11"], result=result)


def test_team_preview_before_start_uses_current_room_and_rqid() -> None:
    policy = _RecordingPolicy()
    result, connection = _run(
        [*_metadata(start=False, active=False), _line(_request("team-preview.json", 1))],
        policy=policy,
    )

    assert result.primary_error is None
    assert policy.selections[0][1].kind == ActionKind.TEAM
    _assert_validated_sends(connection, policy, ["/choose team 123456|1"], result=result)


def test_wait_request_is_consumed_without_policy_or_send() -> None:
    result, connection = _run(
        [*_metadata(), _line(_request("wait.json", 2))],
        policy=_UnexpectedPolicy(),
    )

    assert result.primary_error is None
    assert connection.sent_room == []
    assert result.explicit_request_submissions == 0
    assert result.default_submissions == 0


def test_pending_request_reconciles_after_public_identity_arrives() -> None:
    policy = _RecordingPolicy()
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

    result, connection = _run(lines, policy=policy)

    assert result.primary_error is None
    assert result.state.battle_started is True
    _assert_validated_sends(connection, policy, ["/choose move 1|5"], result=result)


def test_only_newest_pending_request_is_submitted() -> None:
    policy = _RecordingPolicy()
    result, connection = _run(
        [
            *_metadata(active=False),
            _line(_request("move.json", 4)),
            _line(_request("move.json", 5)),
            _line("|switch|p1a: Garchomp|Garchomp, L50, M|183/183"),
        ],
        policy=policy,
    )

    assert result.primary_error is None
    assert [request.identity.rqid for request, _ in policy.selections] == [5]
    _assert_validated_sends(connection, policy, ["/choose move 1|5"], result=result)


def test_terminal_result_discards_pending_request() -> None:
    policy = _RecordingPolicy()
    result, connection = _run(
        [*_metadata(active=False), _line(_request("move.json", 5)), _line("|win|misty")],
        policy=policy,
    )

    assert result.primary_error is None
    assert result.state.winner == "misty"
    assert result.state.tied is False
    assert policy.selections == []
    assert connection.sent_room == []


def test_identical_request_is_never_answered_twice() -> None:
    policy = _RecordingPolicy()
    request = _line(_request("move.json", 5))
    result, connection = _run(
        [*_metadata(), request, _line("|turn|1"), request],
        policy=policy,
    )

    assert result.primary_error is None
    _assert_validated_sends(connection, policy, ["/choose move 1|5"], result=result)


def test_explicit_and_server_default_provenance_have_separate_counters() -> None:
    policy = _RecordingPolicy()
    default_only_active = [
        {
            "moves": [{"move": "Earthquake", "id": "earthquake"}],
            "canTerastallize": "",
            "maybeDisabled": True,
        }
    ]
    result, connection = _run(
        [
            *_metadata(),
            _line(_request("move.json", 5)),
            _line(_request("move.json", 6, active=default_only_active)),
        ],
        policy=policy,
    )

    assert result.primary_error is None
    assert [candidate.provenance for _, candidate in policy.selections] == [
        ActionProvenance.EXPLICIT_REQUEST,
        ActionProvenance.SERVER_DEFAULT,
    ]
    assert result.explicit_request_submissions == 1
    assert result.default_submissions == 1
    _assert_validated_sends(
        connection,
        policy,
        ["/choose move 1|5", "/choose default|6"],
        result=result,
    )


def test_room_control_chat_and_embedded_request_text_are_state_neutral() -> None:
    policy = _RecordingPolicy()
    control_policy = _RecordingPolicy()
    metadata = _metadata(active=False)
    request = _line(_request("move.json", 5))
    reconciliation = _line("|switch|p1a: Garchomp|Garchomp, L50, M|183/183")
    battle_lines = [*metadata, request, reconciliation]
    lines = [
        _line("|title|Ash vs. Misty"),
        _line("|J|ash"),
        *metadata,
        request,
        _line("|c:|1700000000|ash|embedded |request|{} text"),
        reconciliation,
        _line("|L|ash"),
    ]

    result, connection = _run(lines, policy=policy)
    control_result, control_connection = _run(battle_lines, policy=control_policy)

    assert result.primary_error is None
    assert control_result.primary_error is None
    assert result.room_control_or_chat_count == 4
    assert control_result.room_control_or_chat_count == 0
    assert result.state == control_result.state
    assert [request.identity for request, _ in policy.selections] == [
        request.identity for request, _ in control_policy.selections
    ]
    _assert_validated_sends(connection, policy, ["/choose move 1|5"], result=result)
    _assert_validated_sends(
        control_connection,
        control_policy,
        ["/choose move 1|5"],
        result=control_result,
    )


def test_inactiveoff_records_visible_timer_cleared_evidence() -> None:
    result, connection = _run(
        [_line("|init|battle"), _line("|inactiveoff|Timer is now off.")],
        policy=_UnexpectedPolicy(),
    )

    assert result.primary_error is None
    assert connection.sent_room == []
    assert result.state.event_index == 1
    assert result.state.ignored_display_count == 0
    assert result.state.visible_evidence[-1].kind == "timer_warning_cleared"
    assert result.state.visible_evidence[-1].effect == "Timer is now off."


def test_spacer_is_counted_as_ignored_display_state() -> None:
    result, connection = _run(
        [_line("|init|battle"), _line("|"), _line("|start|")],
        policy=_UnexpectedPolicy(),
    )

    assert result.primary_error is None
    assert connection.sent_room == []
    assert result.state.battle_started is True
    assert result.state.event_index == 2
    assert result.state.ignored_display_count == 1
    assert result.room_control_or_chat_count == 0


def test_nonterminal_message_is_ignored_display_not_terminal_error() -> None:
    result, connection = _run(
        [_line("|-message|Battle timer is ON: inactive players will automatically lose.")],
        policy=_UnexpectedPolicy(),
    )

    assert result.primary_error is None
    assert connection.sent_room == []
    assert result.state.ignored_display_count == 1
    assert result.state.event_index == 0


def test_parallel_room_prefixes_never_cross_session_boundary() -> None:
    policy = _RecordingPolicy()
    frame = "\n".join(
        (
            f">{_OTHER_ROOM}",
            "|init|battle",
            _request("move.json", 90),
            f">{_ROOM}",
            *[line.payload for line in _metadata()],
            _request("move.json", 5),
            f">{_OTHER_ROOM}",
            "|win|other",
        )
    )
    result, connection = _run(list(decode_frame(frame)), policy=policy)

    assert result.primary_error is None
    assert result.state.event_index == 7
    assert result.state.winner is None
    _assert_validated_sends(connection, policy, ["/choose move 1|5"], result=result)


def test_stale_request_retains_only_the_previously_validated_send() -> None:
    policy = _RecordingPolicy()
    result, connection = _run(
        [
            *_metadata(),
            _line(_request("move.json", 5)),
            _line(_request("wait.json", 4)),
            _line(_request("move.json", 6)),
        ],
        policy=policy,
    )

    _assert_primary_error(result, StaleRequestIdentity, "stale_rqid")
    _assert_validated_sends(connection, policy, ["/choose move 1|5"], result=result)


def test_missing_rqid_fails_closed_before_policy_and_future_send() -> None:
    policy = _RecordingPolicy()
    result, connection = _run(
        [
            *_metadata(),
            _line(_request_without_rqid("move.json")),
            _line(_request("move.json", 6)),
        ],
        policy=policy,
    )

    _assert_primary_error(
        result,
        RequestStateReconciliationMismatch,
        "request_state_reconciliation_mismatch",
    )
    assert policy.selections == []
    assert connection.sent_room == []


def test_policy_out_of_set_is_blocked_before_send() -> None:
    foreign = BattleSubmission(
        kind=ActionKind.MOVE,
        provenance=ActionProvenance.EXPLICIT_REQUEST,
        slot=4,
        move_id="moonblast",
    )
    policy = _RecordingPolicy(lambda request: foreign)
    result, connection = _run(
        [
            *_metadata(),
            _line(_request("move.json", 5)),
            _line(_request("move.json", 6)),
        ],
        policy=policy,
    )

    _assert_primary_error(
        result,
        LocalActionGateRejection,
        "local_action_gate_rejection",
    )
    assert not policy.selections[0][0].safe_submissions.contains(foreign)
    assert connection.sent_room == []


@pytest.mark.parametrize(
    ("payload", "error_type", "code"),
    [
        (
            "|error|[Invalid choice] Can't do that",
            ServerInvalidChoice,
            "server_invalid_choice",
        ),
        (
            "|error|[Unavailable choice] Not available",
            ServerUnavailableChoice,
            "server_unavailable_choice",
        ),
    ],
)
def test_server_rejections_preserve_only_earlier_validated_send(
    payload: str,
    error_type: type[BaseException],
    code: str,
) -> None:
    policy = _RecordingPolicy()
    result, connection = _run(
        [
            *_metadata(),
            _line(_request("move.json", 5)),
            _line(payload),
            _line(_request("move.json", 6)),
        ],
        policy=policy,
    )

    _assert_primary_error(result, error_type, code)
    _assert_validated_sends(connection, policy, ["/choose move 1|5"], result=result)


@pytest.mark.parametrize(
    ("payload", "error_type", "code"),
    [
        ("|-notarealwiretype|p1a: Garchomp", UnknownProtocolEvent, "unknown_protocol_event"),
        ("|switch|p1a: Garchomp", MalformedProtocolMessage, "malformed_protocol_message"),
    ],
)
def test_unknown_and_malformed_messages_abort_before_future_send(
    payload: str,
    error_type: type[BaseException],
    code: str,
) -> None:
    policy = _RecordingPolicy()
    result, connection = _run(
        [*_metadata(), _line(payload), _line(_request("move.json", 6))],
        policy=policy,
    )

    _assert_primary_error(result, error_type, code)
    assert policy.selections == []
    assert connection.sent_room == []


@pytest.mark.parametrize(
    "payload",
    [
        "|-message|ash lost due to inactivity.",
        "|-message|ash forfeited.",
        "|-message|All players are inactive.",
    ],
)
def test_terminal_message_forms_abort_before_future_send(payload: str) -> None:
    policy = _RecordingPolicy()
    result, connection = _run(
        [_line(payload), *_metadata(), _line(_request("move.json", 5))],
        policy=policy,
    )

    _assert_primary_error(result, TimerOrForfeit, "timer_or_forfeit")
    assert policy.selections == []
    assert connection.sent_room == []
