from __future__ import annotations

import pytest

from battlebelief_lab.evaluation.budget_profiles import (
    BudgetMode,
    BudgetView,
    create_budget_profile,
    create_calibration_specification,
)


def test_budget_profile_keeps_deployment_and_mechanism_views_distinct() -> None:
    profile = create_budget_profile(
        profile_id="m15-fixed-v1",
        mode=BudgetMode.FIXED,
        deployment=BudgetView(
            wall_time_budget_ms=2_000,
            cpu_time_budget_ms=2_000,
            work_value=256,
            work_unit="transitions",
        ),
        mechanism=BudgetView(
            wall_time_budget_ms=None,
            cpu_time_budget_ms=None,
            work_value=256,
            work_unit="transitions",
        ),
    )

    assert profile.deployment.wall_time_budget_ms == 2_000
    assert profile.mechanism.work_value == 256
    assert profile.digest.startswith("sha256:")


def test_calibration_spec_is_outcome_blind_and_stable() -> None:
    spec = create_calibration_specification(
        spec_id="m15-calibration-v1",
        reference_environment_specification={"python": "3.12", "platform": "windows"},
        calibration_state_construction_rule="synthetic-state-grid-v1",
        ordered_work_grid=(64, 128, 256),
        measurement_profile_id="m15-runtime-profile-v1",
        selection_measurement_id="wall_time_ms",
        required_measurement_ids=("wall_time_ms", "cpu_time_ms"),
        runtime_limit_ms=2_000.0,
        allowed_runtime_measurements=("wall_time_ms", "cpu_time_ms"),
        forbidden_quality_measurements=("wins", "regret", "holdout_rows"),
    )
    assert spec.selection_rule_id == "largest-value-under-runtime-limit-v1"
    assert (
        spec.digest
        == create_calibration_specification(
            spec_id="m15-calibration-v1",
            reference_environment_specification={"python": "3.12", "platform": "windows"},
            calibration_state_construction_rule="synthetic-state-grid-v1",
            ordered_work_grid=(64, 128, 256),
            measurement_profile_id="m15-runtime-profile-v1",
            selection_measurement_id="wall_time_ms",
            required_measurement_ids=("wall_time_ms", "cpu_time_ms"),
            runtime_limit_ms=2_000.0,
            allowed_runtime_measurements=("wall_time_ms", "cpu_time_ms"),
            forbidden_quality_measurements=("wins", "regret", "holdout_rows"),
        ).digest
    )


def test_calibration_spec_rejects_quality_measurement_overlap() -> None:
    with pytest.raises(ValueError, match="quality"):
        create_calibration_specification(
            spec_id="m15-calibration-v1",
            reference_environment_specification={"python": "3.12"},
            calibration_state_construction_rule="states-v1",
            ordered_work_grid=(1, 2),
            measurement_profile_id="profile-v1",
            selection_measurement_id="wall_time_ms",
            required_measurement_ids=("wall_time_ms",),
            runtime_limit_ms=5.0,
            allowed_runtime_measurements=("wall_time_ms", "wins"),
            forbidden_quality_measurements=("wins",),
        )
