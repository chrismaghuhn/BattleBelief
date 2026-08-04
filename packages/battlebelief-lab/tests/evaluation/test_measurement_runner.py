from __future__ import annotations

from battlebelief_lab.evaluation.measurement_runner import (
    BattleOutcome,
    MeasurementRunResult,
    RunStatus,
    TraceStatus,
    validate_measurement_run_result,
)


def test_measurement_run_result_is_schema_shaped_and_valid_without_decisions() -> None:
    result = MeasurementRunResult(
        run_context_digest="sha256:" + "a" * 64,
        run_status=RunStatus.COMPLETED,
        battle_outcome=BattleOutcome.INCOMPLETE,
        primary_error_class=None,
        decision_record_digests=(),
        explicit_submission_count=0,
        default_submission_count=0,
        room_control_or_chat_count=0,
        ignored_display_count=0,
        final_observed_state_digest="sha256:" + "b" * 64,
        trace_status=TraceStatus.NO_RECORDS,
    )

    assert validate_measurement_run_result(result) == []
    assert result.to_dict()["battle_outcome"] == "incomplete"
    assert result.digest.startswith("sha256:")
