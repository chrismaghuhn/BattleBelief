from __future__ import annotations

import asyncio
import dataclasses
import json
from collections.abc import Callable
from copy import deepcopy
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
from battlebelief_runtime.adapters.showdown_protocol.frame_decoder import RoomLine
from battlebelief_runtime.composition.battle_session import (
    BattleSession,
    BattleSessionResult,
)
from battlebelief_runtime.errors.actions import ServerInvalidChoice, ServerUnavailableChoice
from battlebelief_runtime.testing.fake_connection import FakeConnection

_ROOT = Path(__file__).resolve().parents[2]
_REQUESTS = _ROOT / "tests" / "fixtures" / "requests"
_ROOM = "battle-gen9ou-action-contract"


def _line(payload: str) -> RoomLine:
    return RoomLine(room_id=_ROOM, payload=payload)


def _request(name: str, rqid: int, **changes: Any) -> str:
    data = json.loads((_REQUESTS / name).read_text(encoding="utf-8"))
    data["rqid"] = rqid
    data.update(changes)
    return "|request|" + json.dumps(data, separators=(",", ":"))


def _metadata(*, active: bool = True) -> list[RoomLine]:
    payloads = [
        "|init|battle",
        "|gametype|singles",
        "|gen|9",
        "|tier|[Gen 9] OU",
        "|player|p1|ash|1|",
        "|player|p2|misty|1|",
        "|start|",
    ]
    if active:
        payloads.append("|switch|p1a: Garchomp|Garchomp, L50, M|183/183")
    return [_line(payload) for payload in payloads]


def _first_submission(request: DecisionRequest) -> BattleSubmission:
    return request.safe_submissions.submissions[0]


class _CapturingPolicy:
    def __init__(
        self,
        selector: Callable[[DecisionRequest], BattleSubmission] = _first_submission,
    ) -> None:
        self._selector = selector
        self.requests: list[DecisionRequest] = []
        self.request_snapshots: list[DecisionRequest] = []
        self.candidates: list[BattleSubmission] = []

    def select(self, request: DecisionRequest) -> BattleSubmission:
        self.request_snapshots.append(deepcopy(request))
        self.requests.append(request)
        candidate = self._selector(request)
        self.candidates.append(candidate)
        return candidate


def _run(
    lines: list[RoomLine | BaseException],
    policy: _CapturingPolicy,
) -> tuple[BattleSessionResult, FakeConnection]:
    connection = FakeConnection(lines)
    session = BattleSession(
        connection=connection,
        room_id=_ROOM,
        our_user_id="ash",
        policy=policy,
    )
    return asyncio.run(session.run()), connection


def _assert_send_was_authorized(
    connection: FakeConnection,
    policy: _CapturingPolicy,
    expected_commands: list[str],
) -> None:
    assert connection.sent_room == [(_ROOM, command) for command in expected_commands]
    assert len(connection.sent_room) == len(policy.candidates)

    for (room_id, command), request, candidate in zip(
        connection.sent_room,
        policy.requests,
        policy.candidates,
        strict=True,
    ):
        assert room_id == request.identity.room_id == _ROOM
        assert request.safe_submissions.request_identity == request.identity
        assert request.safe_submissions.contains(candidate)
        assert command.endswith(f"|{request.identity.rqid}")


def test_equal_value_candidate_is_authorized_without_mutating_gate_inputs() -> None:
    def equal_copy(request: DecisionRequest) -> BattleSubmission:
        return dataclasses.replace(request.safe_submissions.submissions[0])

    policy = _CapturingPolicy(equal_copy)
    result, connection = _run(
        [*_metadata(), _line(_request("move.json", 31))],
        policy,
    )

    request = policy.requests[0]
    offered = request.safe_submissions.submissions[0]
    candidate = policy.candidates[0]
    snapshot = policy.request_snapshots[0]
    assert result.primary_error is None
    assert candidate is not offered
    assert candidate == offered
    assert request == snapshot
    assert request is not snapshot
    assert request.identity is not snapshot.identity
    assert request.safe_submissions is not snapshot.safe_submissions
    assert candidate.provenance == ActionProvenance.EXPLICIT_REQUEST
    assert result.explicit_request_submissions == 1
    assert result.default_submissions == 0
    _assert_send_was_authorized(connection, policy, ["/choose move 1|31"])


def test_policy_result_outside_current_safe_set_is_classified_and_never_sent() -> None:
    foreign = BattleSubmission(
        kind=ActionKind.MOVE,
        provenance=ActionProvenance.EXPLICIT_REQUEST,
        slot=4,
        move_id="moonblast",
    )
    policy = _CapturingPolicy(lambda request: foreign)
    result, connection = _run(
        [
            *_metadata(),
            _line(_request("move.json", 31)),
            _line(_request("move.json", 32)),
        ],
        policy,
    )

    assert type(result.primary_error) is LocalActionGateRejection
    assert getattr(result.primary_error, "code", None) == "local_action_gate_rejection"
    assert not policy.requests[0].safe_submissions.contains(foreign)
    assert connection.sent_room == []
    assert result.explicit_request_submissions == 0
    assert result.default_submissions == 0


def test_newest_pending_request_replaces_older_request_and_safe_set() -> None:
    def select_tera(request: DecisionRequest) -> BattleSubmission:
        return next(sub for sub in request.safe_submissions.submissions if sub.terastallize)

    policy = _CapturingPolicy(select_tera)
    result, connection = _run(
        [
            *_metadata(active=False),
            _line(_request("maybe-trapped.json", 30)),
            _line(_request("move-tera.json", 31)),
            _line("|switch|p1a: Garchomp|Garchomp, L50, M|183/183"),
        ],
        policy,
    )

    assert result.primary_error is None
    assert [request.identity.rqid for request in policy.requests] == [31]
    assert policy.candidates[0].terastallize is True
    _assert_send_was_authorized(
        connection,
        policy,
        ["/choose move 1 terastallize|31"],
    )


def test_stale_rqid_keeps_one_visible_error_and_no_post_error_submission() -> None:
    policy = _CapturingPolicy()
    result, connection = _run(
        [
            *_metadata(),
            _line(_request("move.json", 31)),
            _line(_request("wait.json", 30)),
            _line(_request("move.json", 32)),
        ],
        policy,
    )

    assert type(result.primary_error) is StaleRequestIdentity
    assert getattr(result.primary_error, "code", None) == "stale_rqid"
    assert [request.identity.rqid for request in policy.requests] == [31]
    _assert_send_was_authorized(connection, policy, ["/choose move 1|31"])


def test_server_default_is_deterministic_and_keeps_server_provenance() -> None:
    default_only_active = [
        {
            "moves": [{"move": "Earthquake", "id": "earthquake"}],
            "canTerastallize": "",
            "maybeLocked": True,
        }
    ]
    lines = [
        *_metadata(),
        _line(_request("move.json", 31, active=default_only_active)),
    ]
    first_policy = _CapturingPolicy()
    second_policy = _CapturingPolicy()

    first_result, first_connection = _run(lines, first_policy)
    second_result, second_connection = _run(lines, second_policy)

    for result, connection, policy in (
        (first_result, first_connection, first_policy),
        (second_result, second_connection, second_policy),
    ):
        assert result.primary_error is None
        assert policy.candidates[0].kind == ActionKind.DEFAULT
        assert policy.candidates[0].provenance == ActionProvenance.SERVER_DEFAULT
        assert result.explicit_request_submissions == 0
        assert result.default_submissions == 1
        assert policy.requests[0] == policy.request_snapshots[0]
        assert policy.requests[0] is not policy.request_snapshots[0]
        _assert_send_was_authorized(connection, policy, ["/choose default|31"])

    assert first_connection.sent_room == second_connection.sent_room
    assert first_policy.candidates == second_policy.candidates


@pytest.mark.parametrize(
    ("payload", "error_type", "code"),
    [
        (
            "|error|[Invalid choice] rejected",
            ServerInvalidChoice,
            "server_invalid_choice",
        ),
        (
            "|error|[Unavailable choice] rejected",
            ServerUnavailableChoice,
            "server_unavailable_choice",
        ),
    ],
)
def test_server_rejection_is_primary_and_stops_later_requests(
    payload: str,
    error_type: type[BaseException],
    code: str,
) -> None:
    policy = _CapturingPolicy()
    result, connection = _run(
        [
            *_metadata(),
            _line(_request("move.json", 31)),
            _line(payload),
            _line(_request("move.json", 32)),
        ],
        policy,
    )

    assert isinstance(result.primary_error, error_type)
    assert getattr(result.primary_error, "code", None) == code
    assert [request.identity.rqid for request in policy.requests] == [31]
    _assert_send_was_authorized(connection, policy, ["/choose move 1|31"])
