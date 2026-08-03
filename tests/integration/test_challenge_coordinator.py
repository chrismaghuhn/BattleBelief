from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from collections.abc import AsyncIterator, Iterable
from pathlib import Path

import pytest

from battlebelief_core.domain.teams.sealed_team import SealedTeam
from battlebelief_runtime.adapters.showdown_client.connection import ShowdownConnection
from battlebelief_runtime.adapters.showdown_protocol.frame_decoder import RoomLine
from battlebelief_runtime.adapters.team_files.packed_team import PackedTeam
from battlebelief_runtime.composition.battle_coordinator import BattleCoordinator
from battlebelief_runtime.errors.protocol import (
    Disconnect,
    MalformedProtocolMessage,
    TransportTimeout,
    UnknownProtocolEvent,
)
from battlebelief_runtime.errors.setup import ChallengeSetupError, TeamValidationError

_ROOT = Path(__file__).resolve().parents[2]
_REQUESTS = _ROOT / "tests" / "fixtures" / "requests"
_OUR_USER_ID = "Ash"
_OPPONENT_DISPLAY = "@Misty"
_TARGET_ROOM = "battle-unpredictable-room-name"


def _team() -> PackedTeam:
    return PackedTeam(
        sealed=SealedTeam(digest="team-digest", member_count=1),
        packed="packed-team-secret",
    )


def _request(name: str, rqid: int) -> str:
    payload = json.loads((_REQUESTS / name).read_text(encoding="utf-8"))
    payload["rqid"] = rqid
    return "|request|" + json.dumps(payload, separators=(",", ":"))


def _target_lines(room_id: str = _TARGET_ROOM) -> list[RoomLine]:
    return [
        RoomLine(room_id, "|init|battle"),
        RoomLine(room_id, "|title|Ash vs. Misty"),
        RoomLine(room_id, "|player|p2|Misty|1|"),
        RoomLine(room_id, "|player|p1|Ash|1|"),
        RoomLine(room_id, "|gametype|singles"),
        RoomLine(room_id, "|gen|9"),
        RoomLine(room_id, "|teampreview"),
        RoomLine(room_id, _request("team-preview.json", 7)),
        RoomLine(room_id, "|tier|[Gen 9] OU"),
        RoomLine(room_id, "|win|Ash"),
        RoomLine(room_id, "|title|Battle finished"),
    ]


def _room_setup_lines(
    room_id: str = _TARGET_ROOM,
    *,
    p1_display: str = "Ash",
    p2_display: str = "Misty",
) -> list[RoomLine]:
    return [
        RoomLine(room_id, "|init|battle"),
        RoomLine(room_id, f"|player|p2|{p2_display}|1|"),
        RoomLine(room_id, f"|player|p1|{p1_display}|1|"),
        RoomLine(room_id, "|gametype|singles"),
        RoomLine(room_id, "|gen|9"),
        RoomLine(room_id, "|tier|[Gen 9] OU"),
    ]


def _pending_state() -> RoomLine:
    return RoomLine(
        None,
        '|updatechallenges|{"challengeTo":{"to":"Misty","format":"gen9ou"}}',
    )


def _not_pending_state() -> RoomLine:
    return RoomLine(None, '|updatechallenges|{"challengeTo":null}')


class _RecordingConnection:
    def __init__(self, incoming: Iterable[RoomLine | BaseException]) -> None:
        self._incoming = tuple(incoming)
        self.events: list[tuple[str, str | None]] = []
        self.lines_calls = 0
        self.connect_calls = 0
        self.close_calls = 0
        self.sent_global: list[str] = []
        self.sent_room: list[tuple[str, str]] = []

    async def connect(self) -> None:
        self.connect_calls += 1
        self.events.append(("connect", None))

    def lines(self) -> AsyncIterator[RoomLine]:
        self.lines_calls += 1
        return self._line_stream()

    async def _line_stream(self) -> AsyncIterator[RoomLine]:
        for item in self._incoming:
            if isinstance(item, BaseException):
                raise item
            yield item

    async def send_global(self, command: str) -> None:
        self.sent_global.append(command)
        self.events.append(("global", command))

    async def send_room(self, room_id: str, command: str) -> None:
        self.sent_room.append((room_id, command))
        self.events.append(("room", f"{room_id}|{command}"))

    async def close(self) -> None:
        self.close_calls += 1
        self.events.append(("close", None))


def _run(
    connection: _RecordingConnection,
    *,
    setup_timeout: float = 0.1,
    opponent_display: str = _OPPONENT_DISPLAY,
):
    coordinator = BattleCoordinator(
        connection,
        _OUR_USER_ID,
        opponent_display,
        _team(),
        setup_timeout=setup_timeout,
    )
    return asyncio.run(coordinator.run())


def test_coordinator_sends_exact_commands_discovers_unpredictable_room_and_closes() -> None:
    foreign_room = "battle-gen9ou-deceptive"
    incoming = [
        RoomLine(foreign_room, "|title|Ash vs. Misty"),
        RoomLine(foreign_room, "|init|battle"),
        RoomLine(foreign_room, "|player|p1|Ash|1|"),
        *_target_lines()[:4],
        RoomLine(foreign_room, "|player|p2|Brock|1|"),
        *_target_lines()[4:],
    ]
    connection = _RecordingConnection(incoming)

    result = _run(connection)

    assert result.primary_error is None
    assert connection.sent_global == [
        "|/utm packed-team-secret",
        "|/challenge @Misty, gen9ou",
    ]
    assert connection.sent_room == [(_TARGET_ROOM, "/choose team 123456|7")]
    assert connection.lines_calls == 1
    assert connection.connect_calls == 1
    assert connection.close_calls == 1
    assert connection.events == [
        ("connect", None),
        ("global", "|/utm packed-team-secret"),
        ("global", "|/challenge @Misty, gen9ou"),
        ("room", "battle-unpredictable-room-name|/choose team 123456|7"),
        ("close", None),
    ]
    sent_commands = [*connection.sent_global, *(command for _, command in connection.sent_room)]
    assert not any(
        forbidden in command
        for command in sent_commands
        for forbidden in ("/search", "/cancelsearch", "/cancelchallenge", "/accept", "/reject")
    )


class _FakeSocket:
    def __init__(self, frames: Iterable[str]) -> None:
        self.frames = deque(frames)
        self.sent: list[str] = []
        self.closed = False
        self.recv_calls = 0

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def recv(self) -> str:
        self.recv_calls += 1
        if not self.frames:
            raise StopAsyncIteration
        return self.frames.popleft()

    async def close(self) -> None:
        self.closed = True


class _AssertionProvider:
    async def assertion(self, username: str, password: str, challstr: str) -> str:
        assert (username, password, challstr) == ("Ash", "password", "4|abc")
        return "assertion-token"


class _CountingShowdownConnection(ShowdownConnection):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.lines_calls = 0

    def lines(self) -> AsyncIterator[RoomLine]:
        self.lines_calls += 1
        return super().lines()


def test_actual_connection_preserves_same_frame_lines_through_single_reader_handoff() -> None:
    room_lines = [
        RoomLine(_TARGET_ROOM, "|init|battle"),
        RoomLine(_TARGET_ROOM, "|title|Ash vs. Misty"),
        RoomLine(_TARGET_ROOM, "|player|p2|Misty|1|"),
        RoomLine(_TARGET_ROOM, "|player|p1|Ash|1|"),
        RoomLine(_TARGET_ROOM, "|gametype|singles"),
        RoomLine(_TARGET_ROOM, "|gen|9"),
        RoomLine(_TARGET_ROOM, "|teampreview"),
        RoomLine(_TARGET_ROOM, "|tier|[Gen 9] OU"),
        RoomLine(_TARGET_ROOM, _request("team-preview.json", 7)),
        RoomLine(_TARGET_ROOM, "|win|Ash"),
        RoomLine(_TARGET_ROOM, "|title|Battle finished"),
    ]
    auth_frame = "\n".join(
        [
            "|challstr|4|abc",
            "|updateuser| Ash|1|0|{}",
        ]
    )
    battle_frame = "\n".join(
        [
            f">{_TARGET_ROOM}",
            *(line.payload for line in room_lines),
        ]
    )
    socket = _FakeSocket([auth_frame, battle_frame])

    async def connector(*_args: object, **_kwargs: object) -> _FakeSocket:
        return socket

    connection = _CountingShowdownConnection(
        url="wss://example.invalid/showdown/websocket",
        username="Ash",
        password="password",
        assertion_provider=_AssertionProvider(),
        socket_connector=connector,
    )

    result = asyncio.run(
        BattleCoordinator(
            connection,
            _OUR_USER_ID,
            _OPPONENT_DISPLAY,
            _team(),
            setup_timeout=0.1,
        ).run()
    )

    assert result.primary_error is None
    assert result.explicit_request_submissions == 1
    assert connection.lines_calls == 1
    assert socket.recv_calls == 2
    assert socket.sent == [
        "|/trn Ash,0,assertion-token",
        "|/utm packed-team-secret",
        "|/challenge @Misty, gen9ou",
        "battle-unpredictable-room-name|/choose team 123456|7",
    ]
    assert socket.closed


def test_actual_connection_reports_conflicting_metadata_after_handoff_from_same_frame() -> None:
    auth_frame = "\n".join(("|challstr|4|abc", "|updateuser| Ash|1|0|{}"))
    battle_frame = "\n".join(
        (
            f">{_TARGET_ROOM}",
            "|init|battle",
            "|player|p1|Ash|1|",
            "|player|p2|Misty|1|",
            "|gametype|singles",
            "|gen|9",
            "|tier|[Gen 9] OU",
            _request("team-preview.json", 7),
            "|gen|8",
            "|win|Ash",
        )
    )
    socket = _FakeSocket([auth_frame, battle_frame])

    async def connector(*_args: object, **_kwargs: object) -> _FakeSocket:
        return socket

    connection = _CountingShowdownConnection(
        url="wss://example.invalid/showdown/websocket",
        username="Ash",
        password="password",
        assertion_provider=_AssertionProvider(),
        socket_connector=connector,
    )

    result = asyncio.run(
        BattleCoordinator(
            connection,
            _OUR_USER_ID,
            _OPPONENT_DISPLAY,
            _team(),
            setup_timeout=0.1,
        ).run()
    )

    assert isinstance(result.primary_error, MalformedProtocolMessage)
    assert connection.lines_calls == 1
    assert socket.recv_calls == 2
    assert socket.sent == [
        "|/trn Ash,0,assertion-token",
        "|/utm packed-team-secret",
        "|/challenge @Misty, gen9ou",
        "battle-unpredictable-room-name|/choose team 123456|7",
    ]
    assert socket.closed


@pytest.mark.parametrize(
    "wire_message",
    (
        "Your team was rejected for the following reason:||||- A variable validation reason.",
        "Your team was rejected for the following reasons:||||- First reason.||- Second reason.",
    ),
)
def test_team_validation_popup_has_priority_for_singular_and_plural_reasons(
    wire_message: str,
) -> None:
    connection = _RecordingConnection([RoomLine(None, f"|popup|{wire_message}")])

    with pytest.raises(TeamValidationError):
        _run(connection, setup_timeout=0.001)

    assert connection.close_calls == 1


_EXPLICIT_REJECTION_MESSAGES = (
    "The user '@Misty' was not found.",
    "You can't battle yourself. The best you can do is open PS in Private Browsing (or another browser) and log into a different username, and battle that username.",
    "You are already challenging someone. Cancel that challenge before challenging someone else.",
    "The user '%Misty' is not accepting challenges right now.",
    "You challenged less than 10 seconds after your last challenge! It's cancelled in case it's a misclick.",
    "This user already has 3 pending challenges.||You must be autoconfirmed to challenge them.",
    "You are locked and cannot challenge unlocked users. If this user is your friend, ask them to challenge you instead.",
    "You are banned from battling and cannot challenge users.",
    "You must choose a username before you challenge someone.",
    "There's already a challenge (gen9ou) between you and @Misty!",
    "The server is restarting. Battles will be available again in a few minutes.",
    "The server is under attack. Battles cannot be started at this time.",
)


@pytest.mark.parametrize("carrier", ("|popup|", "|error|"))
@pytest.mark.parametrize("wire_message", _EXPLICIT_REJECTION_MESSAGES)
def test_each_allowlisted_global_message_is_a_fully_matched_explicit_rejection(
    carrier: str,
    wire_message: str,
) -> None:
    connection = _RecordingConnection([RoomLine(None, f"{carrier}{wire_message}")])

    with pytest.raises(ChallengeSetupError) as caught:
        _run(connection, setup_timeout=0.001)

    assert caught.value.subcode == "challenge_command_rejected_explicit"
    assert connection.close_calls == 1


_PREFIX_AND_SUFFIX_NEAR_MISSES = tuple(
    f"prefix {message}" for message in _EXPLICIT_REJECTION_MESSAGES
) + tuple(f"{message} suffix" for message in _EXPLICIT_REJECTION_MESSAGES)


@pytest.mark.parametrize("carrier", ("|popup|", "|error|"))
@pytest.mark.parametrize("wire_message", _PREFIX_AND_SUFFIX_NEAR_MISSES)
def test_each_allowlisted_global_message_rejects_prefix_and_suffix_near_misses(
    carrier: str,
    wire_message: str,
) -> None:
    connection = _RecordingConnection([RoomLine(None, f"{carrier}{wire_message}")])

    with pytest.raises(UnknownProtocolEvent):
        _run(connection, setup_timeout=0.001)


_PARAMETERIZED_TEMPLATE_NEAR_MISSES = (
    (
        "The user 'Misty' was not found.",
        "The user '@misty' was not found.",
        "The user '%Misty' was not found.",
    ),
    (
        "The user 'Brock' was not found.",
        "The user 'Brock' is not accepting challenges right now.",
    ),
    (
        "There's already a challenge (gen8ou) between you and @Misty!",
        "There's already a challenge (gen9ou) between you and Brock!",
    ),
)


@pytest.mark.parametrize("carrier", ("|popup|", "|error|"))
@pytest.mark.parametrize(
    "wire_message",
    tuple(
        message
        for template_near_misses in _PARAMETERIZED_TEMPLATE_NEAR_MISSES
        for message in template_near_misses
    ),
)
def test_parameterized_template_near_misses_fail_closed(
    carrier: str,
    wire_message: str,
) -> None:
    connection = _RecordingConnection([RoomLine(None, f"{carrier}{wire_message}")])

    with pytest.raises(UnknownProtocolEvent):
        _run(connection, setup_timeout=0.001)


@pytest.mark.parametrize("carrier", ("|popup|", "|error|"))
def test_unknown_global_error_carrier_fails_closed(carrier: str) -> None:
    connection = _RecordingConnection([RoomLine(None, f"{carrier}A new server message")])

    with pytest.raises(UnknownProtocolEvent):
        _run(connection, setup_timeout=0.001)


def test_matching_room_succeeds_without_prior_pending_challenge_state() -> None:
    connection = _RecordingConnection(_room_setup_lines())

    result = _run(connection)

    assert result.primary_error is None


@pytest.mark.parametrize(
    "challenge_states",
    (
        [_not_pending_state()],
        [_pending_state(), _not_pending_state()],
    ),
)
def test_initial_or_later_not_pending_does_not_prevent_matching_room(
    challenge_states: list[RoomLine],
) -> None:
    connection = _RecordingConnection([*challenge_states, *_room_setup_lines()])

    result = _run(connection)

    assert result.primary_error is None


@pytest.mark.parametrize(
    ("challenge_states", "subcode"),
    (
        ([_pending_state(), _not_pending_state()], "challenge_not_pending"),
        ([_pending_state()], "challenge_setup_timeout"),
        ([_pending_state(), _not_pending_state(), _pending_state()], "challenge_setup_timeout"),
    ),
)
def test_setup_deadline_classifies_only_the_observed_challenge_state(
    challenge_states: list[RoomLine],
    subcode: str,
) -> None:
    connection = _RecordingConnection(challenge_states)

    with pytest.raises(ChallengeSetupError) as caught:
        _run(connection, setup_timeout=0.001)

    assert caught.value.subcode == subcode
    assert connection.close_calls == 1


def test_initial_not_pending_without_a_room_is_a_setup_timeout() -> None:
    connection = _RecordingConnection([_not_pending_state()])

    with pytest.raises(ChallengeSetupError) as caught:
        _run(connection, setup_timeout=0.001)

    assert caught.value.subcode == "challenge_setup_timeout"


@pytest.mark.parametrize(
    ("p1_display", "p2_display"),
    (
        ("Ash", "Misty"),
        ("Misty", "Ash"),
    ),
)
def test_both_valid_player_side_orientations_prove_the_target_room(
    p1_display: str,
    p2_display: str,
) -> None:
    connection = _RecordingConnection(
        _room_setup_lines(p1_display=p1_display, p2_display=p2_display)
    )

    result = _run(connection)

    assert result.primary_error is None


def test_identical_duplicate_p1_does_not_substitute_for_missing_p2() -> None:
    connection = _RecordingConnection(
        [
            RoomLine(_TARGET_ROOM, "|init|battle"),
            RoomLine(_TARGET_ROOM, "|player|p1|Ash|1|"),
            RoomLine(_TARGET_ROOM, "|player|p1|Ash|1|"),
            RoomLine(_TARGET_ROOM, "|gametype|singles"),
            RoomLine(_TARGET_ROOM, "|gen|9"),
            RoomLine(_TARGET_ROOM, "|tier|[Gen 9] OU"),
        ]
    )

    with pytest.raises(ChallengeSetupError) as caught:
        _run(connection, setup_timeout=0.001)

    assert caught.value.subcode == "challenge_setup_timeout"


def test_conflicting_player_side_value_is_malformed_once_identity_is_proven() -> None:
    connection = _RecordingConnection(
        [
            RoomLine(_TARGET_ROOM, "|init|battle"),
            RoomLine(_TARGET_ROOM, "|player|p1|Ash|1|"),
            RoomLine(_TARGET_ROOM, "|player|p1|Misty|1|"),
            RoomLine(_TARGET_ROOM, "|player|p2|Misty|1|"),
        ]
    )

    with pytest.raises(MalformedProtocolMessage):
        _run(connection, setup_timeout=0.001)


@pytest.mark.parametrize(
    "invalid_player_line",
    (
        "|player|p3|Brock|1|",
        "|player|p1||1|",
    ),
)
def test_invalid_player_side_or_empty_identity_is_malformed_evidence(
    invalid_player_line: str,
) -> None:
    connection = _RecordingConnection(
        [
            RoomLine(_TARGET_ROOM, "|init|battle"),
            RoomLine(_TARGET_ROOM, invalid_player_line),
            RoomLine(_TARGET_ROOM, "|player|p1|Ash|1|"),
            RoomLine(_TARGET_ROOM, "|player|p2|Misty|1|"),
        ]
    )

    with pytest.raises(MalformedProtocolMessage):
        _run(connection, setup_timeout=0.001)


def test_unicode_kelvin_display_matches_ascii_k_target_identity() -> None:
    connection = _RecordingConnection(
        _room_setup_lines(p1_display="Ash", p2_display="\N{KELVIN SIGN}")
    )

    result = _run(connection, opponent_display="K")

    assert result.primary_error is None
    assert result.state.p2.display_name == "\N{KELVIN SIGN}"


def test_kelvin_in_target_display_normalizes_without_colliding_with_plain_misty() -> None:
    plain_misty_room = "battle-plain-misty"
    actual_target_room = "battle-mistyk"
    connection = _RecordingConnection(
        [
            *_room_setup_lines(plain_misty_room, p1_display="Ash", p2_display="Misty"),
            *_room_setup_lines(actual_target_room, p1_display="Ash", p2_display="MistyK"),
        ]
    )

    result = _run(connection, opponent_display="Misty\N{KELVIN SIGN}")

    assert result.primary_error is None
    assert result.state.p2.display_name == "MistyK"


@pytest.mark.parametrize(
    "metadata_lines",
    (
        ("|gametype|doubles", "|gametype|singles"),
        ("|gen|8", "|gen|9"),
        ("|tier|[Gen 8] OU", "|tier|[Gen 9] OU"),
        ("|gametype|singles", "|gametype|doubles"),
        ("|gen|9", "|gen|8"),
        ("|tier|[Gen 9] OU", "|tier|[Gen 8] OU"),
    ),
)
def test_conflicting_scope_metadata_before_player_identity_is_malformed_evidence(
    metadata_lines: tuple[str, str],
) -> None:
    connection = _RecordingConnection(
        [
            RoomLine(_TARGET_ROOM, "|init|battle"),
            *(RoomLine(_TARGET_ROOM, line) for line in metadata_lines),
            RoomLine(_TARGET_ROOM, "|player|p1|Ash|1|"),
            RoomLine(_TARGET_ROOM, "|player|p2|Misty|1|"),
            RoomLine(_TARGET_ROOM, "|gametype|singles"),
            RoomLine(_TARGET_ROOM, "|gen|9"),
            RoomLine(_TARGET_ROOM, "|tier|[Gen 9] OU"),
        ]
    )

    with pytest.raises(MalformedProtocolMessage):
        _run(connection, setup_timeout=0.001)


def test_identical_duplicate_scope_metadata_is_idempotent() -> None:
    connection = _RecordingConnection(
        [
            RoomLine(_TARGET_ROOM, "|init|battle"),
            RoomLine(_TARGET_ROOM, "|gametype|singles"),
            RoomLine(_TARGET_ROOM, "|gametype|singles"),
            RoomLine(_TARGET_ROOM, "|gen|9"),
            RoomLine(_TARGET_ROOM, "|gen|9"),
            RoomLine(_TARGET_ROOM, "|tier|[Gen 9] OU"),
            RoomLine(_TARGET_ROOM, "|tier|[Gen 9] OU"),
            RoomLine(_TARGET_ROOM, "|player|p1|Ash|1|"),
            RoomLine(_TARGET_ROOM, "|player|p2|Misty|1|"),
        ]
    )

    result = _run(connection)

    assert result.primary_error is None


@pytest.mark.parametrize(
    "wrong_metadata",
    (
        "|gametype|doubles",
        "|gen|8",
        "|tier|[Gen 8] OU",
    ),
)
def test_exact_player_pair_with_wrong_valid_scope_metadata_fails_closed(
    wrong_metadata: str,
) -> None:
    room_id = "battle-room-with-valid-looking-id"
    connection = _RecordingConnection(
        [
            RoomLine(room_id, "|init|battle"),
            RoomLine(room_id, "|player|p1|Ash|1|"),
            RoomLine(room_id, "|player|p2|Misty|1|"),
            RoomLine(room_id, wrong_metadata),
        ]
    )

    with pytest.raises(UnknownProtocolEvent):
        _run(connection, setup_timeout=0.001)


def test_malformed_scope_metadata_for_exact_player_pair_propagates_unchanged() -> None:
    connection = _RecordingConnection(
        [
            RoomLine(_TARGET_ROOM, "|init|battle"),
            RoomLine(_TARGET_ROOM, "|player|p1|Ash|1|"),
            RoomLine(_TARGET_ROOM, "|player|p2|Misty|1|"),
            RoomLine(_TARGET_ROOM, "|gen|not-an-integer"),
        ]
    )

    with pytest.raises(MalformedProtocolMessage):
        _run(connection, setup_timeout=0.001)


def test_target_metadata_before_battle_init_is_deferred_malformed_evidence() -> None:
    connection = _RecordingConnection(
        [
            RoomLine(_TARGET_ROOM, "|gen|9"),
            *_room_setup_lines(),
        ]
    )

    with pytest.raises(MalformedProtocolMessage):
        _run(connection, setup_timeout=0.001)


def test_pre_init_metadata_in_a_foreign_room_does_not_block_a_later_target_room() -> None:
    foreign_room = "battle-foreign-pre-init"
    connection = _RecordingConnection(
        [
            RoomLine(foreign_room, "|gen|9"),
            RoomLine(foreign_room, "|init|battle"),
            RoomLine(foreign_room, "|player|p1|Brock|1|"),
            RoomLine(foreign_room, "|player|p2|Dawn|1|"),
            *_room_setup_lines(),
        ]
    )

    result = _run(connection)

    assert result.primary_error is None


def test_malformed_scope_metadata_is_deferred_for_a_conclusively_foreign_room() -> None:
    foreign_room = "battle-foreign-room"
    connection = _RecordingConnection(
        [
            RoomLine(foreign_room, "|init|battle"),
            RoomLine(foreign_room, "|gen|not-an-integer"),
            RoomLine(foreign_room, "|player|p1|Brock|1|"),
            RoomLine(foreign_room, "|player|p2|Dawn|1|"),
            *_room_setup_lines(),
        ]
    )

    result = _run(connection)

    assert result.primary_error is None


def test_known_global_status_and_ordinary_pm_text_are_ignored_without_room_hints() -> None:
    connection = _RecordingConnection(
        [
            RoomLine(None, "|formats|{}"),
            RoomLine(None, "|usercount|123"),
            RoomLine(None, "|updatesearch|{}"),
            RoomLine(None, "|pm|Brock|Ash|ordinary /challenge gen9ou text"),
            RoomLine(None, "|battle|battle-gen9ou-deceptive|Ash|Misty"),
            RoomLine(None, "|b|battle-gen9ou-deceptive"),
            *_room_setup_lines(),
        ]
    )

    result = _run(connection)

    assert result.primary_error is None


@pytest.mark.parametrize(
    "payload",
    (
        "|challstr|5|duplicate",
        "|challstr|",
        "|updateuser| Ash|0|0|{}",
        "|updateuser| Brock|1|0|{}",
        "|queryresponse|rooms|null",
    ),
)
def test_post_auth_login_controls_and_query_responses_fail_closed(payload: str) -> None:
    connection = _RecordingConnection([RoomLine(None, payload)])

    with pytest.raises(UnknownProtocolEvent):
        _run(connection, setup_timeout=0.001)


def test_unknown_global_setup_payload_fails_closed() -> None:
    connection = _RecordingConnection([RoomLine(None, "|unexpectedglobal|value")])

    with pytest.raises(UnknownProtocolEvent):
        _run(connection, setup_timeout=0.001)


class _DelayedSessionConnection(_RecordingConnection):
    def __init__(self, setup_lines: Iterable[RoomLine], delay: float) -> None:
        super().__init__(setup_lines)
        self._delay = delay

    async def _line_stream(self) -> AsyncIterator[RoomLine]:
        for item in self._incoming:
            if isinstance(item, BaseException):
                raise item
            yield item
        await asyncio.sleep(self._delay)
        yield RoomLine(_TARGET_ROOM, "|win|Ash")
        yield RoomLine(_TARGET_ROOM, "|title|Battle finished")


def test_setup_timeout_ends_before_a_deliberately_longer_battle_session() -> None:
    connection = _DelayedSessionConnection(_room_setup_lines(), delay=0.03)
    started_at = time.monotonic()

    result = _run(connection, setup_timeout=0.001)

    assert result.primary_error is None
    assert time.monotonic() - started_at >= 0.02


@pytest.mark.parametrize("failure", (TransportTimeout("read timed out"), Disconnect("closed")))
def test_setup_transport_errors_propagate_without_reclassification(
    failure: RuntimeError,
) -> None:
    connection = _RecordingConnection([failure])

    with pytest.raises(type(failure)) as caught:
        _run(connection)

    assert caught.value is failure
    assert connection.close_calls == 1


def test_inner_timeout_error_before_setup_deadline_propagates_unchanged() -> None:
    failure = TimeoutError("source raised before coordinator deadline")
    connection = _RecordingConnection([failure])

    with pytest.raises(TimeoutError) as caught:
        _run(connection)

    assert caught.value is failure
    assert connection.close_calls == 1


def test_session_transport_error_is_preserved_as_the_result_primary_error() -> None:
    failure = Disconnect("session closed")
    connection = _RecordingConnection([*_room_setup_lines(), failure])

    result = _run(connection)

    assert result.primary_error is failure
    assert connection.close_calls == 1


class _CloseFailingConnection(_RecordingConnection):
    async def close(self) -> None:
        await super().close()
        raise RuntimeError("close failed")


def test_close_error_does_not_mask_a_setup_error() -> None:
    connection = _CloseFailingConnection([RoomLine(None, "|popup|unrecognized")])

    with pytest.raises(UnknownProtocolEvent):
        _run(connection)

    assert connection.close_calls == 1


def test_close_error_does_not_mask_a_session_primary_error() -> None:
    connection = _CloseFailingConnection(
        [*_room_setup_lines(), RoomLine(_TARGET_ROOM, "|not-a-real-wire-type")]
    )

    result = _run(connection)

    assert isinstance(result.primary_error, UnknownProtocolEvent)
    assert connection.close_calls == 1


def test_close_error_propagates_when_no_primary_error_exists() -> None:
    connection = _CloseFailingConnection(_room_setup_lines())

    with pytest.raises(RuntimeError, match="close failed"):
        _run(connection)


class _BlockingConnection(_RecordingConnection):
    def __init__(self) -> None:
        super().__init__([])
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def _line_stream(self) -> AsyncIterator[RoomLine]:
        self.started.set()
        await self.release.wait()
        if False:
            yield RoomLine(None, "")


def test_cancellation_closes_the_connection_once() -> None:
    async def run_and_cancel() -> _BlockingConnection:
        connection = _BlockingConnection()
        task = asyncio.create_task(
            BattleCoordinator(
                connection,
                _OUR_USER_ID,
                _OPPONENT_DISPLAY,
                _team(),
                setup_timeout=1.0,
            ).run()
        )
        await connection.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return connection

    connection = asyncio.run(run_and_cancel())

    assert connection.connect_calls == 1
    assert connection.close_calls == 1


class _FailingSendConnection(_RecordingConnection):
    async def send_global(self, command: str) -> None:
        await super().send_global(command)
        raise Disconnect("write failed")


def test_setup_send_failure_closes_without_a_retry() -> None:
    connection = _FailingSendConnection(_room_setup_lines())

    with pytest.raises(Disconnect, match="write failed"):
        _run(connection)

    assert connection.lines_calls == 0
    assert connection.events == [
        ("connect", None),
        ("global", "|/utm packed-team-secret"),
        ("close", None),
    ]


@pytest.mark.parametrize(
    ("our_user_id", "opponent_display", "setup_timeout"),
    (
        ("!!!", "@Misty", 0.1),
        ("Ash", "!!!", 0.1),
        ("Ash", "Mi,sty", 0.1),
        ("Ash", "Mi|sty", 0.1),
        ("Ash", "Mi\rsty", 0.1),
        ("Ash", "Mi\nsty", 0.1),
        ("Ash", "Mi\x00sty", 0.1),
        ("Ash", "@Misty", 0),
        ("Ash", "@Misty", -0.1),
        ("Ash", "@Misty", float("inf")),
        ("Ash", "@Misty", float("nan")),
        ("Ash", "@Misty", True),
        ("Ash", "@Misty", "0.1"),
    ),
)
def test_constructor_rejects_invalid_local_inputs_before_connection_side_effects(
    our_user_id: str,
    opponent_display: str,
    setup_timeout: object,
) -> None:
    connection = _RecordingConnection([])

    with pytest.raises(ValueError):
        BattleCoordinator(
            connection,
            our_user_id,
            opponent_display,
            _team(),
            setup_timeout=setup_timeout,  # type: ignore[arg-type]
        )

    assert connection.events == []
    assert connection.lines_calls == 0
    assert connection.sent_global == []


@pytest.mark.parametrize("opponent_display", ("@Misty", "Misty Smith"))
def test_constructor_keeps_rank_prefixed_and_spaced_displays_permitted(
    opponent_display: str,
) -> None:
    coordinator = BattleCoordinator(
        _RecordingConnection([]),
        _OUR_USER_ID,
        opponent_display,
        _team(),
        setup_timeout=0.1,
    )

    assert coordinator is not None


def test_constructor_allows_equal_ids_and_self_challenge_popup_is_explicit_rejection() -> None:
    connection = _RecordingConnection(
        [
            RoomLine(
                None,
                "|popup|You can't battle yourself. The best you can do is open PS in Private Browsing (or another browser) and log into a different username, and battle that username.",
            )
        ]
    )
    coordinator = BattleCoordinator(
        connection,
        _OUR_USER_ID,
        _OUR_USER_ID,
        _team(),
        setup_timeout=0.1,
    )

    with pytest.raises(ChallengeSetupError, match="explicitly rejected"):
        asyncio.run(coordinator.run())


class _SecretReprConnection(_RecordingConnection):
    def __repr__(self) -> str:
        return "<connection-secret password=password-secret assertion=assertion-secret>"


def test_logs_normalized_opponent_and_team_digest_without_sensitive_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    connection = _SecretReprConnection(_room_setup_lines())

    _run(connection)

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "misty" in messages
    assert "team-digest" in messages
    assert "packed-team-secret" not in messages
    assert "password-secret" not in messages
    assert "assertion-secret" not in messages
    assert "connection-secret" not in messages
    assert repr(connection) not in messages
