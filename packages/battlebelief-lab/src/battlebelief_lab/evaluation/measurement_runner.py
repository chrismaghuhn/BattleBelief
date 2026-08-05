"""Immutable measurement-run results and their cross-artifact checks."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from battlebelief_core.canonicalization import manifest_digest
from battlebelief_core.domain.actions.submission import ActionProvenance
from battlebelief_core.domain.records.decision_record import (
    DecisionRecord,
    DecisionRecordErrorCode,
    DecisionRecordStatus,
    MeasurementRunContext,
)
from battlebelief_core.domain.records.public_projection import (
    observed_state_digest,
    project_observed_state,
)
from battlebelief_core.errors import TraceSinkFailure
from battlebelief_lab.evaluation.schedule import ScheduleRow
from battlebelief_runtime.testing import MeasurementSession, RecordingTraceSink

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MAX_SAFE_INTEGER = 9_007_199_254_740_991
_ALLOWED_ERROR_CODES = frozenset(
    {code.value for code in DecisionRecordErrorCode}
    | {"trace_sink_failure", "decision_record_construction_failure", "runtime_error"}
)


class RunStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
    TRACE_FAILED = "trace_failed"
    NO_REQUEST = "no_request"
    INCOMPLETE = "incomplete"


class BattleOutcome(StrEnum):
    OUR_WIN = "our_win"
    OPPONENT_WIN = "opponent_win"
    TIE = "tie"
    VOID = "void"
    INCOMPLETE = "incomplete"


class TraceStatus(StrEnum):
    EMITTED = "emitted"
    NO_RECORDS = "no_records"
    SINK_FAILED = "sink_failed"
    NOT_ATTEMPTED = "not_attempted"


@dataclass(frozen=True, slots=True)
class MeasurementRunResult:
    schema_version: int
    run_context_digest: str
    run_status: RunStatus
    battle_outcome: BattleOutcome
    primary_error_class: str | None
    decision_record_digests: tuple[str, ...]
    explicit_submission_count: int
    default_submission_count: int
    room_control_or_chat_count: int
    ignored_display_count: int
    final_observed_state_digest: str
    trace_status: TraceStatus

    def __init__(
        self,
        *,
        run_context_digest: str,
        run_status: RunStatus,
        battle_outcome: BattleOutcome,
        primary_error_class: str | None,
        decision_record_digests: tuple[str, ...],
        explicit_submission_count: int,
        default_submission_count: int,
        room_control_or_chat_count: int,
        ignored_display_count: int,
        final_observed_state_digest: str,
        trace_status: TraceStatus,
        schema_version: int = 1,
    ) -> None:
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "run_context_digest", run_context_digest)
        object.__setattr__(self, "run_status", run_status)
        object.__setattr__(self, "battle_outcome", battle_outcome)
        object.__setattr__(self, "primary_error_class", primary_error_class)
        object.__setattr__(self, "decision_record_digests", decision_record_digests)
        object.__setattr__(self, "explicit_submission_count", explicit_submission_count)
        object.__setattr__(self, "default_submission_count", default_submission_count)
        object.__setattr__(self, "room_control_or_chat_count", room_control_or_chat_count)
        object.__setattr__(self, "ignored_display_count", ignored_display_count)
        object.__setattr__(self, "final_observed_state_digest", final_observed_state_digest)
        object.__setattr__(self, "trace_status", trace_status)
        self.__post_init__()

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("unsupported measurement-run-result schema version")
        for name in ("run_context_digest", "final_observed_state_digest"):
            if type(getattr(self, name)) is not str or not _DIGEST_RE.fullmatch(
                getattr(self, name)
            ):
                raise ValueError(f"{name} must be a sha256 digest")
        for name in (
            "run_status",
            "battle_outcome",
            "trace_status",
        ):
            expected_type = {
                "run_status": RunStatus,
                "battle_outcome": BattleOutcome,
                "trace_status": TraceStatus,
            }[name]
            if type(getattr(self, name)) is not expected_type:
                raise ValueError(f"{name} must use its public enum")
        if self.primary_error_class is not None and (
            type(self.primary_error_class) is not str
            or not _CODE_RE.fullmatch(self.primary_error_class)
            or self.primary_error_class not in _ALLOWED_ERROR_CODES
        ):
            raise ValueError("primary_error_class must be an allowed stable code or null")
        if type(self.decision_record_digests) is not tuple or any(
            type(digest) is not str or not _DIGEST_RE.fullmatch(digest)
            for digest in self.decision_record_digests
        ):
            raise ValueError("decision_record_digests must be a tuple of digests")
        if len(set(self.decision_record_digests)) != len(self.decision_record_digests):
            raise ValueError("decision_record_digests must be unique")
        for name in (
            "explicit_submission_count",
            "default_submission_count",
            "room_control_or_chat_count",
            "ignored_display_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= _MAX_SAFE_INTEGER:
                raise ValueError(f"{name} must be a JCS-safe non-negative integer")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_context_digest": self.run_context_digest,
            "run_status": self.run_status.value,
            "battle_outcome": self.battle_outcome.value,
            "primary_error_class": self.primary_error_class,
            "decision_record_digests": list(self.decision_record_digests),
            "explicit_submission_count": self.explicit_submission_count,
            "default_submission_count": self.default_submission_count,
            "room_control_or_chat_count": self.room_control_or_chat_count,
            "ignored_display_count": self.ignored_display_count,
            "final_observed_state_digest": self.final_observed_state_digest,
            "trace_status": self.trace_status.value,
        }

    @property
    def digest(self) -> str:
        return manifest_digest(self.to_dict())


def validate_measurement_run_result(
    result: MeasurementRunResult,
    *,
    decision_records: tuple[DecisionRecord, ...] = (),
    session_result: Any | None = None,
    final_state: Any | None = None,
) -> list[str]:
    """Validate result counters and bind it to finalized records/state when supplied."""

    errors: list[str] = []
    if not isinstance(result, MeasurementRunResult):
        return ["measurement-run-result has the wrong type"]
    if decision_records:
        if (
            tuple(record.record_digest for record in decision_records)
            != result.decision_record_digests
        ):
            errors.append("decision record digests are not in decision order")
        indices = [record.decision_index for record in decision_records]
        if indices != sorted(indices) or len(set(indices)) != len(indices):
            errors.append("decision records have invalid decision_index order")
        if any(
            record.run_context_digest != result.run_context_digest for record in decision_records
        ):
            errors.append("decision records do not share the run context")
        submitted_records = (
            record
            for record in decision_records
            if record.record_status is DecisionRecordStatus.SUBMITTED
        )
        explicit = sum(
            record.submission_provenance is ActionProvenance.EXPLICIT_REQUEST
            for record in submitted_records
        )
        submitted_records = (
            record
            for record in decision_records
            if record.record_status is DecisionRecordStatus.SUBMITTED
        )
        default = sum(
            record.submission_provenance is ActionProvenance.SERVER_DEFAULT
            for record in submitted_records
        )
        partial_trace = result.trace_status is TraceStatus.SINK_FAILED and (
            result.primary_error_class == "trace_sink_failure"
            or any(
                record.record_status is DecisionRecordStatus.SUBMITTED
                for record in decision_records
            )
        )
        if partial_trace:
            if result.explicit_submission_count < explicit:
                errors.append("explicit submission count is below accepted records")
            if result.default_submission_count < default:
                errors.append("default submission count is below accepted records")
        else:
            if result.explicit_submission_count != explicit:
                errors.append("explicit submission count does not match records")
            if result.default_submission_count != default:
                errors.append("default submission count does not match records")
    elif result.decision_record_digests:
        errors.append("decision record digests have no corresponding records")
    if (
        result.decision_record_digests
        and result.trace_status is not TraceStatus.EMITTED
        and result.trace_status is not TraceStatus.SINK_FAILED
    ):
        errors.append("record digests require an emitted trace or sink failure")
    if not result.decision_record_digests and result.trace_status is TraceStatus.EMITTED:
        errors.append("an emitted trace requires at least one record")
    errors.extend(_validate_status_matrix(result))
    if session_result is not None:
        if result.room_control_or_chat_count != session_result.room_control_or_chat_count:
            errors.append("room-control count does not match session result")
        if result.explicit_submission_count != session_result.explicit_request_submissions:
            errors.append("explicit count does not match session result")
        if result.default_submission_count != session_result.default_submissions:
            errors.append("default count does not match session result")
        expected_primary = _stable_error_code(session_result.primary_error)
        if (
            expected_primary is None
            and result.primary_error_class == "trace_sink_failure"
            and result.trace_status is TraceStatus.SINK_FAILED
        ):
            expected_primary = "trace_sink_failure"
        if result.primary_error_class != expected_primary:
            errors.append("primary error class does not match session result")
        if (
            session_result.trace_error is not None
            and result.trace_status is not TraceStatus.SINK_FAILED
        ):
            errors.append("trace status does not match session trace error")
        if session_result.record_error is not None and result.trace_status is TraceStatus.EMITTED:
            errors.append("record construction failure cannot emit a complete trace")
    if final_state is not None:
        if result.final_observed_state_digest != observed_state_digest(final_state):
            errors.append("final observed-state digest does not match state")
        if result.ignored_display_count != final_state.ignored_display_count:
            errors.append("ignored-display count does not match state")
        winner = project_observed_state(final_state).get("winner")
        expected_outcome = (
            {
                "our_side": BattleOutcome.OUR_WIN,
                "opponent_side": BattleOutcome.OPPONENT_WIN,
                "tie": BattleOutcome.TIE,
            }.get(winner)
            if isinstance(winner, str)
            else None
        )
        if expected_outcome is not None and result.battle_outcome is not expected_outcome:
            errors.append("battle outcome does not match final state")
        if expected_outcome is None and result.battle_outcome in {
            BattleOutcome.OUR_WIN,
            BattleOutcome.OPPONENT_WIN,
            BattleOutcome.TIE,
        }:
            errors.append("winner outcome cannot be proven from final state")
    return errors


def _validate_status_matrix(result: MeasurementRunResult) -> list[str]:
    errors: list[str] = []
    has_records = bool(result.decision_record_digests)
    if result.run_status is RunStatus.COMPLETED:
        if result.primary_error_class is not None:
            errors.append("completed result must not have a primary error")
        if not has_records or result.trace_status is not TraceStatus.EMITTED:
            errors.append("completed result requires an emitted decision record")
    elif result.run_status is RunStatus.NO_REQUEST:
        if result.primary_error_class is not None:
            errors.append("no_request result must not have a primary error")
        if has_records or result.trace_status not in {
            TraceStatus.NO_RECORDS,
            TraceStatus.NOT_ATTEMPTED,
        }:
            errors.append("no_request result must not contain decision records")
        if result.explicit_submission_count or result.default_submission_count:
            errors.append("no_request result must have zero submission counters")
    elif result.run_status is RunStatus.TRACE_FAILED:
        if result.primary_error_class != "trace_sink_failure":
            errors.append("trace_failed result requires trace_sink_failure")
        if result.trace_status is not TraceStatus.SINK_FAILED:
            errors.append("trace_failed result requires sink_failed trace status")
    elif result.run_status in {RunStatus.FAILED, RunStatus.ABORTED}:
        if result.primary_error_class is None:
            errors.append("failed result requires a primary error")
    elif result.run_status is RunStatus.INCOMPLETE:
        if result.primary_error_class is not None:
            errors.append("incomplete result must not have a primary error")
        if result.battle_outcome is not BattleOutcome.INCOMPLETE:
            errors.append("incomplete result requires incomplete battle outcome")
    if result.trace_status in {TraceStatus.NO_RECORDS, TraceStatus.NOT_ATTEMPTED} and has_records:
        errors.append("record digests contradict an empty trace status")
    if result.trace_status is TraceStatus.EMITTED and not has_records:
        errors.append("emitted trace status requires record digests")
    return errors


def validate_measurement_run_result_document(
    document: Mapping[str, Any],
    *,
    decision_records: tuple[DecisionRecord, ...] = (),
) -> list[str]:
    """Validate the semantic shape of a schema-valid result document."""

    try:
        result = MeasurementRunResult(
            schema_version=document["schema_version"],
            run_context_digest=document["run_context_digest"],
            run_status=RunStatus(document["run_status"]),
            battle_outcome=BattleOutcome(document["battle_outcome"]),
            primary_error_class=document["primary_error_class"],
            decision_record_digests=tuple(document["decision_record_digests"]),
            explicit_submission_count=document["explicit_submission_count"],
            default_submission_count=document["default_submission_count"],
            room_control_or_chat_count=document["room_control_or_chat_count"],
            ignored_display_count=document["ignored_display_count"],
            final_observed_state_digest=document["final_observed_state_digest"],
            trace_status=TraceStatus(document["trace_status"]),
        )
    except KeyError as error:
        return [f"measurement-run-result is missing field {error.args[0]}"]
    except (TypeError, ValueError) as error:
        return [f"measurement-run-result semantic validation failed: {error}"]
    return validate_measurement_run_result(result, decision_records=decision_records)


class MeasurementRunner:
    """Own one approved Runtime measurement session and its sink lifecycle."""

    def __init__(
        self,
        *,
        session: MeasurementSession,
        trace_sink: RecordingTraceSink,
        run_context: MeasurementRunContext,
        schedule_row: ScheduleRow,
    ) -> None:
        if getattr(session, "trace_sink", None) is not trace_sink:
            raise ValueError("measurement runner and session must share one trace sink")
        if not all(
            hasattr(trace_sink, name)
            for name in ("records", "accepted_record_count", "accepted_record_digests")
        ):
            raise ValueError("measurement runner requires an accepted-record ledger")
        if not callable(getattr(session, "failure_result", None)):
            raise ValueError("measurement session must provide a sanitized failure result")
        self._session = session
        self._trace_sink = trace_sink
        self._run_context = run_context
        if run_context.run_scope.schedule_row_id != schedule_row.row_id:
            raise ValueError("measurement session row does not match run context")
        if run_context.run_scope.seed_family_digest != schedule_row.seed_family.digest:
            raise ValueError("measurement session seed family does not match run context")

    async def run(self) -> MeasurementRunResult:
        """Run, flush, and close one session without exposing raw exceptions."""

        session_result: Any | None = None
        lifecycle_failed = False
        try:
            try:
                session_result = await self._session.run()
            except Exception as exc:
                try:
                    session_result = self._session.failure_result(exc)
                except Exception as failure_error:
                    raise ValueError(
                        "measurement session failure result unavailable"
                    ) from failure_error
        finally:
            for method_name in ("flush_trace", "close_trace"):
                try:
                    getattr(self._session, method_name)()
                except Exception:
                    lifecycle_failed = True
        records = tuple(self._trace_sink.records)
        accepted_digests = tuple(self._trace_sink.accepted_record_digests)
        if self._trace_sink.accepted_record_count != len(accepted_digests):
            raise ValueError("accepted record ledger count is inconsistent")
        if accepted_digests != tuple(record.record_digest for record in records):
            raise ValueError("accepted record ledger does not match retained records")
        trace_error = session_result.trace_error is not None or lifecycle_failed
        trace_status = (
            TraceStatus.SINK_FAILED
            if trace_error
            else (
                TraceStatus.EMITTED
                if records
                else TraceStatus.NOT_ATTEMPTED
                if session_result.record_error is not None
                else TraceStatus.NO_RECORDS
            )
        )
        state_projection = project_observed_state(session_result.state)
        winner = state_projection.get("winner")
        outcome_by_winner: dict[str, BattleOutcome] = {
            "our_side": BattleOutcome.OUR_WIN,
            "opponent_side": BattleOutcome.OPPONENT_WIN,
            "tie": BattleOutcome.TIE,
        }
        outcome = outcome_by_winner.get(winner) if isinstance(winner, str) else None
        battle_outcome = outcome or (
            BattleOutcome.VOID
            if session_result.primary_error is not None
            else BattleOutcome.INCOMPLETE
        )
        primary_error = session_result.primary_error
        if lifecycle_failed and primary_error is None:
            primary_error = TraceSinkFailure()
        primary_error_class = (
            _stable_error_code(primary_error) if primary_error is not None else None
        )
        trace_only_failure = trace_error and (
            session_result.primary_error is None
            or _stable_error_code(session_result.primary_error) == "trace_sink_failure"
        )
        if trace_only_failure:
            primary_error_class = "trace_sink_failure"
        run_status = (
            RunStatus.TRACE_FAILED
            if trace_only_failure
            else RunStatus.FAILED
            if primary_error is not None
            else RunStatus.NO_REQUEST
            if not records
            else RunStatus.COMPLETED
        )
        result = MeasurementRunResult(
            run_context_digest=self._run_context.run_context_digest,
            run_status=run_status,
            battle_outcome=battle_outcome,
            primary_error_class=primary_error_class,
            decision_record_digests=tuple(record.record_digest for record in records),
            explicit_submission_count=session_result.explicit_request_submissions,
            default_submission_count=session_result.default_submissions,
            room_control_or_chat_count=session_result.room_control_or_chat_count,
            ignored_display_count=session_result.state.ignored_display_count,
            final_observed_state_digest=observed_state_digest(session_result.state),
            trace_status=trace_status,
        )
        errors = validate_measurement_run_result(
            result,
            decision_records=records,
            session_result=session_result,
            final_state=session_result.state,
        )
        if errors:
            raise ValueError("invalid measurement-run result: " + "; ".join(errors))
        return result


def _stable_error_code(error: BaseException | None) -> str | None:
    if error is None:
        return None
    value = getattr(error, "code", None)
    if isinstance(value, str) and value in _ALLOWED_ERROR_CODES:
        return value
    name = type(error).__name__
    snake_name = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    code = re.sub(r"[^a-z0-9_]+", "_", snake_name).strip("_")
    return code[:64] if code in _ALLOWED_ERROR_CODES else "runtime_error"


__all__ = [
    "BattleOutcome",
    "MeasurementRunResult",
    "MeasurementRunner",
    "RunStatus",
    "TraceStatus",
    "validate_measurement_run_result",
    "validate_measurement_run_result_document",
]
