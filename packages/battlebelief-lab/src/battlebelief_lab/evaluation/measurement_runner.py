"""Immutable measurement-run results and their cross-artifact checks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from battlebelief_core.canonicalization import manifest_digest
from battlebelief_core.domain.actions.submission import ActionProvenance
from battlebelief_core.domain.records.decision_record import DecisionRecord
from battlebelief_core.domain.records.public_projection import (
    observed_state_digest,
    project_observed_state,
)
from battlebelief_lab.evaluation.schedule import ScheduleRow

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


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
            if not isinstance(getattr(self, name), (RunStatus, BattleOutcome, TraceStatus)):
                raise ValueError(f"{name} must use its public enum")
        if self.primary_error_class is not None and (
            type(self.primary_error_class) is not str
            or not _CODE_RE.fullmatch(self.primary_error_class)
        ):
            raise ValueError("primary_error_class must be a stable code or null")
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
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")

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
        explicit = sum(
            record.submission_provenance is ActionProvenance.EXPLICIT_REQUEST
            for record in decision_records
        )
        default = sum(
            record.submission_provenance is ActionProvenance.SERVER_DEFAULT
            for record in decision_records
        )
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
    if session_result is not None:
        if result.room_control_or_chat_count != session_result.room_control_or_chat_count:
            errors.append("room-control count does not match session result")
        if result.explicit_submission_count != session_result.explicit_request_submissions:
            errors.append("explicit count does not match session result")
        if result.default_submission_count != session_result.default_submissions:
            errors.append("default count does not match session result")
    if final_state is not None:
        if result.final_observed_state_digest != observed_state_digest(final_state):
            errors.append("final observed-state digest does not match state")
        if result.ignored_display_count != final_state.ignored_display_count:
            errors.append("ignored-display count does not match state")
    return errors


def validate_measurement_run_result_document(document: dict[str, Any]) -> list[str]:
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
    except (KeyError, TypeError, ValueError):
        return ["measurement-run-result semantic validation failed"]
    return validate_measurement_run_result(result)


class MeasurementRunner:
    """Own one approved Runtime measurement session and its sink lifecycle."""

    def __init__(
        self,
        *,
        session: Any,
        trace_sink: Any,
        run_context: Any,
        schedule_row: ScheduleRow | None = None,
    ) -> None:
        self._session = session
        self._trace_sink = trace_sink
        self._run_context = run_context
        if schedule_row is not None and (
            run_context.run_scope.schedule_row_id != schedule_row.row_id
        ):
            raise ValueError("measurement session row does not match run context")

    async def run(self) -> MeasurementRunResult:
        """Run, flush, and close one session without exposing raw exceptions."""

        session_result = await self._session.run()
        lifecycle_failed = False
        for method_name in ("flush_trace", "close_trace"):
            try:
                getattr(self._session, method_name)()
            except Exception:
                lifecycle_failed = True
        records = getattr(self._trace_sink, "records", ())
        if not isinstance(records, tuple):
            records = tuple(records)
        trace_error = session_result.trace_error is not None or lifecycle_failed
        trace_status = (
            TraceStatus.SINK_FAILED
            if trace_error
            else (TraceStatus.EMITTED if records else TraceStatus.NO_RECORDS)
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
        primary_error_class = _stable_error_code(primary_error) if primary_error else None
        run_status = (
            RunStatus.TRACE_FAILED
            if trace_error and primary_error is None
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


def _stable_error_code(error: BaseException) -> str:
    value = getattr(error, "code", None)
    if isinstance(value, str) and _CODE_RE.fullmatch(value):
        return value
    name = type(error).__name__.casefold()
    code = re.sub(r"[^a-z0-9_]+", "_", name).strip("_")
    return code[:64] or "runtime_error"


__all__ = [
    "BattleOutcome",
    "MeasurementRunResult",
    "MeasurementRunner",
    "RunStatus",
    "TraceStatus",
    "validate_measurement_run_result",
    "validate_measurement_run_result_document",
]
