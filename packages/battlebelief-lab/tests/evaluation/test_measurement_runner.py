from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from types import SimpleNamespace

import pytest

from battlebelief_core.domain.actions.submission import ActionProvenance
from battlebelief_core.domain.records.decision_record import DecisionRecordStatus
from battlebelief_core.domain.records.public_projection import observed_state_digest
from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_core.errors import TraceSinkFailure
from battlebelief_lab.evaluation.matchup_blocks import BaseMatchupKey
from battlebelief_lab.evaluation.measurement_runner import (
    BattleOutcome,
    MeasurementRunner,
    MeasurementRunResult,
    RunStatus,
    TraceStatus,
    validate_measurement_run_result,
)
from battlebelief_lab.evaluation.schedule import build_schedule

_RUN_DIGEST = "sha256:" + "a" * 64
_STATE_DIGEST = "sha256:" + "b" * 64


def _result(**changes: object) -> MeasurementRunResult:
    values: dict[str, object] = {
        "run_context_digest": _RUN_DIGEST,
        "run_status": RunStatus.NO_REQUEST,
        "battle_outcome": BattleOutcome.INCOMPLETE,
        "primary_error_class": None,
        "decision_record_digests": (),
        "explicit_submission_count": 0,
        "default_submission_count": 0,
        "room_control_or_chat_count": 0,
        "ignored_display_count": 0,
        "final_observed_state_digest": _STATE_DIGEST,
        "trace_status": TraceStatus.NO_RECORDS,
    }
    values.update(changes)
    return MeasurementRunResult(**values)


def test_measurement_run_result_is_schema_shaped_and_valid_without_decisions() -> None:
    result = _result()

    assert validate_measurement_run_result(result) == []
    assert result.to_dict()["battle_outcome"] == "incomplete"
    assert result.digest.startswith("sha256:")


def test_measurement_run_result_requires_field_specific_enum_types() -> None:
    with pytest.raises(ValueError, match="run_status"):
        _result(run_status=TraceStatus.EMITTED)
    with pytest.raises(ValueError, match="battle_outcome"):
        _result(battle_outcome=RunStatus.FAILED)
    with pytest.raises(ValueError, match="trace_status"):
        _result(trace_status=BattleOutcome.TIE)


def test_measurement_run_result_error_taxonomy_and_status_matrix_are_closed() -> None:
    with pytest.raises(ValueError, match="allowed stable code"):
        _result(primary_error_class="banana")

    completed_without_records = _result(
        run_status=RunStatus.COMPLETED,
        trace_status=TraceStatus.NO_RECORDS,
    )
    assert (
        "completed result requires an emitted decision record"
        in validate_measurement_run_result(completed_without_records)
    )

    trace_failed_without_trace = _result(
        run_status=RunStatus.TRACE_FAILED,
        primary_error_class=None,
        trace_status=TraceStatus.EMITTED,
    )
    assert validate_measurement_run_result(trace_failed_without_trace)

    failed_without_error = _result(run_status=RunStatus.FAILED)
    assert "failed result requires a primary error" in validate_measurement_run_result(
        failed_without_error
    )

    no_request_with_submission = _result(explicit_submission_count=1)
    assert (
        "no_request result must have zero submission counters"
        in validate_measurement_run_result(no_request_with_submission)
    )


def test_measurement_run_result_counter_boundaries_match_jcs_schema() -> None:
    maximum = 9_007_199_254_740_991
    accepted = _result(explicit_submission_count=maximum)
    assert accepted.explicit_submission_count == maximum
    with pytest.raises(ValueError, match="JCS-safe"):
        _result(explicit_submission_count=maximum + 1)


def test_measurement_run_result_binds_known_final_outcome() -> None:
    state = replace(ObservedState.initial("ash"), winner="Ash")
    result = _result(
        run_status=RunStatus.FAILED,
        primary_error_class="runtime_error",
        battle_outcome=BattleOutcome.OPPONENT_WIN,
        final_observed_state_digest=observed_state_digest(state),
    )
    assert "battle outcome does not match final state" in validate_measurement_run_result(
        result, final_state=state
    )


@dataclass(frozen=True)
class _Record:
    record_digest: str
    decision_index: int
    run_context_digest: str
    record_status: DecisionRecordStatus
    submission_provenance: ActionProvenance | None


def test_only_successful_submitted_records_contribute_submission_counters() -> None:
    record = _Record(
        record_digest="sha256:" + "c" * 64,
        decision_index=0,
        run_context_digest=_RUN_DIGEST,
        record_status=DecisionRecordStatus.COMMAND_ENCODING_FAILED,
        submission_provenance=ActionProvenance.EXPLICIT_REQUEST,
    )
    result = _result(
        run_status=RunStatus.FAILED,
        primary_error_class="command_encoding_failed",
        decision_record_digests=(record.record_digest,),
        trace_status=TraceStatus.SINK_FAILED,
    )
    assert "explicit submission count" not in validate_measurement_run_result(
        result, decision_records=(record,)
    )
    invalid = _result(
        run_status=RunStatus.FAILED,
        primary_error_class="command_encoding_failed",
        decision_record_digests=(record.record_digest,),
        explicit_submission_count=1,
        trace_status=TraceStatus.SINK_FAILED,
    )
    assert "explicit submission count does not match records" in validate_measurement_run_result(
        invalid, decision_records=(record,)
    )


class _RaisingSession:
    def __init__(self, trace_sink: object) -> None:
        self.trace_sink = trace_sink
        self.lifecycle: list[str] = []

    async def run(self) -> object:
        raise RuntimeError("private failure text")

    def failure_result(self, error: BaseException) -> object:
        return SimpleNamespace(
            state=ObservedState.initial("ash"),
            primary_error=error,
            trace_error=None,
            record_error=None,
            room_control_or_chat_count=0,
            explicit_request_submissions=0,
            default_submissions=0,
        )

    def flush_trace(self) -> None:
        self.lifecycle.append("flush")

    def close_trace(self) -> None:
        self.lifecycle.append("close")


class _Ledger:
    records: tuple[object, ...] = ()
    accepted_record_count = 0
    accepted_record_digests: tuple[str, ...] = ()


class _TraceOnlySession:
    def __init__(self, trace_sink: object) -> None:
        self.trace_sink = trace_sink

    async def run(self) -> object:
        return SimpleNamespace(
            state=ObservedState.initial("ash"),
            primary_error=None,
            trace_error=TraceSinkFailure(),
            record_error=None,
            room_control_or_chat_count=0,
            explicit_request_submissions=0,
            default_submissions=0,
        )

    def failure_result(self, error: BaseException) -> object:
        raise AssertionError(f"unexpected session exception: {error}")

    def flush_trace(self) -> None:
        return None

    def close_trace(self) -> None:
        return None


def test_runner_finalizes_lifecycle_and_sanitizes_session_exception() -> None:
    ledger = _Ledger()
    session = _RaisingSession(ledger)
    schedule = build_schedule(
        registration_digest=_RUN_DIGEST,
        master_seed="0123456789abcdef" * 4,
        matchup_keys=[BaseMatchupKey("hero", "opponent", "balance", "policy", "block")],
        repetitions=2,
    )
    context = SimpleNamespace(
        run_context_digest=_RUN_DIGEST,
        run_scope=SimpleNamespace(schedule_row_id=schedule.rows[0].row_id),
    )
    runner = MeasurementRunner(
        session=session,
        trace_sink=ledger,
        run_context=context,
        schedule_row=schedule.rows[0],
    )

    result = asyncio.run(runner.run())

    assert result.run_status is RunStatus.FAILED
    assert result.primary_error_class == "runtime_error"
    assert session.lifecycle == ["flush", "close"]


def test_runner_classifies_trace_only_failure_with_stable_code() -> None:
    ledger = _Ledger()
    session = _TraceOnlySession(ledger)
    schedule = build_schedule(
        registration_digest=_RUN_DIGEST,
        master_seed="0123456789abcdef" * 4,
        matchup_keys=[BaseMatchupKey("hero", "opponent", "balance", "policy", "block")],
        repetitions=2,
    )
    context = SimpleNamespace(
        run_context_digest=_RUN_DIGEST,
        run_scope=SimpleNamespace(schedule_row_id=schedule.rows[0].row_id),
    )
    result = asyncio.run(
        MeasurementRunner(
            session=session,
            trace_sink=ledger,
            run_context=context,
            schedule_row=schedule.rows[0],
        ).run()
    )

    assert result.run_status is RunStatus.TRACE_FAILED
    assert result.primary_error_class == "trace_sink_failure"
    assert result.trace_status is TraceStatus.SINK_FAILED
