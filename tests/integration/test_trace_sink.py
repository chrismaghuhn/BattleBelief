from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path

import pytest

import battlebelief_runtime.composition.battle_session as battle_session_module
from battlebelief_core.domain.actions.submission import (
    ActionKind,
    ActionProvenance,
    BattleSubmission,
)
from battlebelief_core.domain.records.decision_record import (
    MeasurementRunContext,
    ResolvedDecisionRecordBinding,
    RunScopePayload,
    RuntimeAndContractDigests,
)
from battlebelief_core.errors import NoLegalActionError, TraceSinkFailure
from battlebelief_runtime.adapters.showdown_protocol.frame_decoder import RoomLine
from battlebelief_runtime.adapters.telemetry.jsonl_decision_trace import (
    JsonlDecisionTrace,
)
from battlebelief_runtime.composition.battle_session import BattleSession
from battlebelief_runtime.errors.protocol import (
    Disconnect,
    MalformedProtocolMessage,
    ReducerInvariantFailure,
    TimerOrForfeit,
    TransportTimeout,
    UnknownProtocolEvent,
)
from battlebelief_runtime.testing.fake_connection import FakeConnection
from battlebelief_runtime.testing.in_memory_trace_sink import InMemoryTraceSink
from battlebelief_runtime.testing.measurement_session import MeasurementSession

_ROOT = Path(__file__).resolve().parents[2]
_REQUESTS = _ROOT / "tests" / "fixtures" / "requests"
_ROOM = "battle-gen9ou-1"
_DIGEST = "sha256:" + "a" * 64


def _line(payload: str) -> RoomLine:
    return RoomLine(room_id=_ROOM, payload=payload)


def _request(rqid: int = 5) -> str:
    data = json.loads((_REQUESTS / "move.json").read_text(encoding="utf-8"))
    data["rqid"] = rqid
    return "|request|" + json.dumps(data, separators=(",", ":"))


def _pending_request(rqid: int = 6) -> str:
    data = json.loads((_REQUESTS / "move.json").read_text(encoding="utf-8"))
    data["rqid"] = rqid
    for pokemon in data["side"]["pokemon"]:
        pokemon["active"] = False
    return "|request|" + json.dumps(data, separators=(",", ":"))


def _metadata(*, active: bool = True) -> list[RoomLine]:
    lines = [
        _line("|init|battle"),
        _line("|gametype|singles"),
        _line("|gen|9"),
        _line("|tier|[Gen 9] OU"),
        _line("|player|p1|ash|1|"),
        _line("|player|p2|misty|1|"),
        _line("|start|"),
    ]
    if active:
        lines.append(_line("|switch|p1a: Garchomp|Garchomp, L50, M|183/183"))
    return lines


def _run_context() -> MeasurementRunContext:
    binding = ResolvedDecisionRecordBinding(
        evaluation_run_binding_digest=_DIGEST,
        registration_digest=_DIGEST,
        arm_binding_digest=_DIGEST,
        schedule_digest=_DIGEST,
        budget_profile_digest=_DIGEST,
        seed_family_digest=_DIGEST,
        arm_id="heuristic_v0",
        runtime_and_contract_digests=RuntimeAndContractDigests(
            runtime_digest=_DIGEST,
            contract_set_digest=_DIGEST,
            policy_digest=_DIGEST,
            fallback_and_safety_digest=_DIGEST,
        ),
    )
    return MeasurementRunContext.create(
        resolved_binding=binding,
        run_scope=RunScopePayload(
            registration_digest=_DIGEST,
            arm_binding_digest=_DIGEST,
            schedule_digest=_DIGEST,
            schedule_row_id="row-0",
            budget_profile_digest=_DIGEST,
            seed_family_digest=_DIGEST,
            runtime_digest=_DIGEST,
            contract_set_digest=_DIGEST,
        ),
        battle_ordinal=0,
    )


def test_fresh_request_emits_once_and_duplicate_is_suppressed() -> None:
    sink = InMemoryTraceSink()
    connection = FakeConnection(
        [
            *_metadata(),
            _line(_request()),
            _line(_request()),
        ]
    )
    result = asyncio.run(
        BattleSession(
            connection=connection,
            room_id=_ROOM,
            our_user_id="ash",
            trace_sink=sink,
            decision_record_context=_run_context(),
        ).run()
    )

    assert result.primary_error is None
    assert connection.sent_room == [(_ROOM, "/choose move 1|5")]
    assert len(sink.records) == 1
    record = sink.records[0]
    assert record.record_status.value == "submitted"
    assert record.request_identity.rqid == 5
    assert "battle-gen9ou-1" not in repr(record)


def test_measurement_session_exposes_the_narrow_testing_seam() -> None:
    sink = InMemoryTraceSink()
    result = asyncio.run(
        MeasurementSession(
            connection=FakeConnection([*_metadata(), _line(_request())]),
            room_id=_ROOM,
            our_user_id="ash",
            trace_sink=sink,
            decision_record_context=_run_context(),
        ).run()
    )

    assert result.primary_error is None
    assert len(sink.records) == 1


def test_identical_measurement_runs_produce_identical_trace_bytes() -> None:
    def run_once() -> tuple[list[tuple[str, str]], bytes, str]:
        stream = io.BytesIO()
        sink = JsonlDecisionTrace(stream)
        connection = FakeConnection([*_metadata(), _line(_request())])
        result = asyncio.run(
            BattleSession(
                connection=connection,
                room_id=_ROOM,
                our_user_id="ash",
                trace_sink=sink,
                decision_record_context=_run_context(),
            ).run()
        )
        assert result.primary_error is None
        assert len(sink.records) == 1
        return connection.sent_room, stream.getvalue(), sink.records[0].record_digest

    first = run_once()
    second = run_once()
    assert first == second


def test_measurement_seam_classifies_flush_and_close_failures() -> None:
    class FailingLifecycleSink(InMemoryTraceSink):
        def flush(self) -> None:
            raise OSError("private file path")

        def close(self) -> None:
            raise OSError("private file path")

    session = MeasurementSession(
        connection=FakeConnection([]),
        room_id=_ROOM,
        our_user_id="ash",
        trace_sink=FailingLifecycleSink(),
        decision_record_context=_run_context(),
    )

    with pytest.raises(TraceSinkFailure):
        session.flush_trace()
    with pytest.raises(TraceSinkFailure):
        session.close_trace()


def test_jsonl_trace_is_exact_utf8_record_bytes_plus_lf() -> None:
    stream = io.BytesIO()
    sink = JsonlDecisionTrace(stream)
    connection = FakeConnection([*_metadata(), _line(_request())])
    result = asyncio.run(
        BattleSession(
            connection=connection,
            room_id=_ROOM,
            our_user_id="ash",
            trace_sink=sink,
            decision_record_context=_run_context(),
        ).run()
    )

    assert result.primary_error is None
    assert len(sink.records) == 1
    assert stream.getvalue() == sink.records[0].canonical_envelope_bytes() + b"\n"
    for forbidden in (
        b"battle-gen9ou-1",
        b"password",
        b"assertion",
        b"packed-team-secret",
        b"/private/path",
        b"internal.example.com",
    ):
        assert forbidden not in stream.getvalue()


def test_trace_sink_failure_is_a_stable_primary_error() -> None:
    class FailingSink(InMemoryTraceSink):
        def emit(self, record: object) -> None:
            raise RuntimeError("secret /private/path")

    result = asyncio.run(
        BattleSession(
            connection=FakeConnection([*_metadata(), _line(_request())]),
            room_id=_ROOM,
            our_user_id="ash",
            trace_sink=FailingSink(),
            decision_record_context=_run_context(),
        ).run()
    )

    assert result.primary_error is not None
    assert getattr(result.primary_error, "code", None) == "trace_sink_failure"
    assert "secret" not in str(result.primary_error)
    assert "/private/path" not in str(result.primary_error)


class _RejectingPolicy:
    def select(self, request: object) -> BattleSubmission:
        raise NoLegalActionError("must not be serialized")


class _UnsafePolicy:
    def select(self, request: object) -> BattleSubmission:
        return BattleSubmission(
            kind=ActionKind.MOVE,
            provenance=ActionProvenance.EXPLICIT_REQUEST,
            slot=2,
            move_id="tackle",
        )


class _DisconnectingConnection(FakeConnection):
    async def send_room(self, room_id: str, command: str) -> None:
        raise Disconnect("private transport detail")


def test_trace_sink_keeps_submitted_record_after_battle_terminal() -> None:
    lines = [*_metadata(), _line(_request()), _line("|win|misty")]
    sink = InMemoryTraceSink()
    result = asyncio.run(
        BattleSession(
            connection=FakeConnection(lines),
            room_id=_ROOM,
            our_user_id="ash",
            trace_sink=sink,
            decision_record_context=_run_context(),
        ).run()
    )

    assert result.primary_error is None
    assert [record.record_status.value for record in sink.records] == ["submitted"]


def test_pending_request_discarded_by_battle_terminal_is_recorded() -> None:
    sink = InMemoryTraceSink()
    result = asyncio.run(
        BattleSession(
            connection=FakeConnection(
                [*_metadata(active=False), _line(_pending_request()), _line("|win|misty")]
            ),
            room_id=_ROOM,
            our_user_id="ash",
            trace_sink=sink,
            decision_record_context=_run_context(),
        ).run()
    )

    assert result.primary_error is None
    assert [record.record_status.value for record in sink.records] == ["terminally_discarded"]


@pytest.mark.parametrize(
    "error",
    [
        Disconnect("disconnect"),
        TransportTimeout("timeout"),
        TimerOrForfeit("timer"),
        UnknownProtocolEvent("unknown"),
        MalformedProtocolMessage("malformed"),
        ReducerInvariantFailure("reducer"),
    ],
)
def test_pending_request_abort_classes_are_recorded(
    error: BaseException,
) -> None:
    sink = InMemoryTraceSink()
    result = asyncio.run(
        BattleSession(
            connection=FakeConnection([*_metadata(active=False), _line(_pending_request()), error]),
            room_id=_ROOM,
            our_user_id="ash",
            trace_sink=sink,
            decision_record_context=_run_context(),
        ).run()
    )

    assert result.primary_error is error
    assert len(sink.records) == 1
    assert sink.records[0].record_status.value == "session_aborted"
    assert sink.records[0].fallback_or_error_class == error.code


def test_pending_request_replaced_by_newer_request_is_superseded() -> None:
    sink = InMemoryTraceSink()
    result = asyncio.run(
        BattleSession(
            connection=FakeConnection(
                [
                    *_metadata(active=False),
                    _line(_pending_request(5)),
                    _line(_pending_request(6)),
                    Disconnect("ended"),
                ]
            ),
            room_id=_ROOM,
            our_user_id="ash",
            trace_sink=sink,
            decision_record_context=_run_context(),
        ).run()
    )

    assert isinstance(result.primary_error, Disconnect)
    assert [record.record_status.value for record in sink.records] == [
        "superseded_before_selection",
        "session_aborted",
    ]


def test_wait_request_emits_wait_noop_without_submission() -> None:
    data = json.loads((_REQUESTS / "wait.json").read_text(encoding="utf-8"))
    data["rqid"] = 2
    sink = InMemoryTraceSink()
    result = asyncio.run(
        BattleSession(
            connection=FakeConnection([*_metadata(), _line("|request|" + json.dumps(data))]),
            room_id=_ROOM,
            our_user_id="ash",
            trace_sink=sink,
            decision_record_context=_run_context(),
        ).run()
    )

    assert result.primary_error is None
    connection_records = sink.records
    assert connection_records
    assert connection_records[0].record_status.value == "wait_noop"
    assert connection_records[0].selected_submission is None
    assert connection_records[0].fallback_or_error_class is None


def test_policy_rejection_has_no_selection_and_a_stable_code() -> None:
    sink = InMemoryTraceSink()
    result = asyncio.run(
        BattleSession(
            connection=FakeConnection([*_metadata(), _line(_request())]),
            room_id=_ROOM,
            our_user_id="ash",
            policy=_RejectingPolicy(),
            trace_sink=sink,
            decision_record_context=_run_context(),
        ).run()
    )

    assert isinstance(result.primary_error, NoLegalActionError)
    assert len(sink.records) == 1
    assert sink.records[0].record_status.value == "policy_rejected"
    assert sink.records[0].fallback_or_error_class == "no_legal_action_available"
    assert sink.records[0].selected_submission is None


def test_action_gate_rejection_has_candidate_but_no_send() -> None:
    sink = InMemoryTraceSink()
    connection = FakeConnection([*_metadata(), _line(_request())])
    result = asyncio.run(
        BattleSession(
            connection=connection,
            room_id=_ROOM,
            our_user_id="ash",
            policy=_UnsafePolicy(),
            trace_sink=sink,
            decision_record_context=_run_context(),
        ).run()
    )

    assert getattr(result.primary_error, "code", None) == "local_action_gate_rejection"
    assert connection.sent_room == []
    assert len(sink.records) == 1
    assert sink.records[0].record_status.value == "action_gate_rejected"
    assert sink.records[0].selected_submission is not None


def test_command_encoding_failure_has_no_send_or_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    sink = InMemoryTraceSink()
    connection = FakeConnection([*_metadata(), _line(_request())])

    def fail_encoding(submission: BattleSubmission) -> str:
        raise ValueError("private encoder detail")

    monkeypatch.setattr(battle_session_module, "encode_submission", fail_encoding)
    result = asyncio.run(
        BattleSession(
            connection=connection,
            room_id=_ROOM,
            our_user_id="ash",
            trace_sink=sink,
            decision_record_context=_run_context(),
        ).run()
    )

    assert isinstance(result.primary_error, ValueError)
    assert connection.sent_room == []
    assert result.explicit_request_submissions == 0
    assert len(sink.records) == 1
    assert sink.records[0].record_status.value == "command_encoding_failed"
    assert sink.records[0].fallback_or_error_class == "command_encoding_failed"


def test_send_failure_is_recorded_without_claiming_dispatch() -> None:
    sink = InMemoryTraceSink()
    result = asyncio.run(
        BattleSession(
            connection=_DisconnectingConnection([*_metadata(), _line(_request())]),
            room_id=_ROOM,
            our_user_id="ash",
            trace_sink=sink,
            decision_record_context=_run_context(),
        ).run()
    )

    assert isinstance(result.primary_error, Disconnect)
    assert len(sink.records) == 1
    assert sink.records[0].record_status.value == "send_failed"
    assert sink.records[0].fallback_or_error_class == "send_failed"


def test_pending_request_abort_is_recorded_and_submitted_record_is_preserved() -> None:
    sink = InMemoryTraceSink()
    connection = FakeConnection(
        [
            *_metadata(active=False),
            _line(_pending_request()),
            Disconnect("stream ended"),
        ]
    )
    result = asyncio.run(
        BattleSession(
            connection=connection,
            room_id=_ROOM,
            our_user_id="ash",
            trace_sink=sink,
            decision_record_context=_run_context(),
        ).run()
    )

    assert isinstance(result.primary_error, Disconnect)
    assert [record.record_status.value for record in sink.records] == ["session_aborted"]
    assert sink.records[0].fallback_or_error_class == "disconnect"


def test_submitted_record_survives_a_later_disconnect() -> None:
    sink = InMemoryTraceSink()
    result = asyncio.run(
        BattleSession(
            connection=FakeConnection([*_metadata(), _line(_request()), Disconnect("ended")]),
            room_id=_ROOM,
            our_user_id="ash",
            trace_sink=sink,
            decision_record_context=_run_context(),
        ).run()
    )

    assert isinstance(result.primary_error, Disconnect)
    assert [record.record_status.value for record in sink.records] == ["submitted"]


def test_trace_failure_does_not_replace_a_primary_send_error() -> None:
    class FailingSink(InMemoryTraceSink):
        def emit(self, record: object) -> None:
            raise RuntimeError("secret")

    result = asyncio.run(
        BattleSession(
            connection=_DisconnectingConnection([*_metadata(), _line(_request())]),
            room_id=_ROOM,
            our_user_id="ash",
            trace_sink=FailingSink(),
            decision_record_context=_run_context(),
        ).run()
    )

    assert isinstance(result.primary_error, Disconnect)
    assert getattr(result.primary_error, "code", None) == "disconnect"
