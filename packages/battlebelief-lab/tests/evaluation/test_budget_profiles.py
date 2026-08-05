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


def test_calibration_spec_digest_is_stable() -> None:
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
            reference_environment_specification={"platform": "windows", "python": "3.12"},
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


def test_calibration_spec_copies_mutable_inputs_and_keeps_digest_stable() -> None:
    references = [("python", "3.12"), ("platform", "windows")]
    work_grid = [64, 128]
    spec = create_calibration_specification(
        spec_id="m15-calibration-v1",
        reference_environment_specification=dict(references),
        calibration_state_construction_rule="synthetic-state-grid-v1",
        ordered_work_grid=work_grid,
        measurement_profile_id="m15-runtime-profile-v1",
        selection_measurement_id="wall_time_ms",
        required_measurement_ids=("wall_time_ms", "cpu_time_ms"),
        runtime_limit_ms=2_000.0,
        allowed_runtime_measurements=("wall_time_ms", "cpu_time_ms"),
        forbidden_quality_measurements=("wins", "regret", "holdout_rows"),
    )
    digest = spec.digest
    references.append(("new", "value"))
    work_grid.append(256)

    assert spec.digest == digest
    assert spec.ordered_work_grid == (64, 128)
    assert spec.reference_environment_specification == (("platform", "windows"), ("python", "3.12"))


def test_calibration_spec_rejects_invalid_environment_pairs() -> None:
    with pytest.raises(ValueError, match="environment"):
        create_calibration_specification(
            spec_id="m15-calibration-v1",
            reference_environment_specification={"python": 3.12},  # type: ignore[dict-item]
            calibration_state_construction_rule="states-v1",
            ordered_work_grid=(1, 2),
            measurement_profile_id="profile-v1",
            selection_measurement_id="wall_time_ms",
            required_measurement_ids=("wall_time_ms",),
            runtime_limit_ms=5.0,
            allowed_runtime_measurements=("wall_time_ms",),
            forbidden_quality_measurements=("wins",),
        )
    with pytest.raises(ValueError, match="duplicate"):
        from battlebelief_lab.evaluation.budget_profiles import CalibrationSpecification

        CalibrationSpecification(
            schema_version=2,
            spec_id="m15-calibration-v1",
            budget_mode=BudgetMode.CALIBRATED_GRID,
            reference_environment_specification=(("python", "3.12"), ("python", "3.13")),
            calibration_state_construction_rule="states-v1",
            ordered_work_grid=(1, 2),
            selection_rule_id="largest-value-under-runtime-limit-v1",
            measurement_profile_id="profile-v1",
            selection_measurement_id="wall_time_ms",
            required_measurement_ids=("wall_time_ms",),
            runtime_limit_ms=5.0,
            allowed_runtime_measurements=("wall_time_ms",),
            forbidden_quality_measurements=("wins",),
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


def test_calibration_spec_rejects_empty_or_duplicate_identity_fields() -> None:
    common = {
        "spec_id": "m15-calibration-v1",
        "reference_environment_specification": {"python": "3.12"},
        "ordered_work_grid": (1, 2),
        "measurement_profile_id": "profile-v1",
        "selection_measurement_id": "wall_time_ms",
        "required_measurement_ids": ("wall_time_ms", "wall_time_ms"),
        "runtime_limit_ms": 5.0,
        "allowed_runtime_measurements": ("wall_time_ms",),
        "forbidden_quality_measurements": ("wins",),
    }
    with pytest.raises(ValueError, match="construction"):
        create_calibration_specification(
            **common,
            calibration_state_construction_rule="",
        )
    with pytest.raises(ValueError, match="duplicates"):
        create_calibration_specification(
            **common,
            calibration_state_construction_rule="states-v1",
        )


def test_hardware_normalized_budget_mode_is_explicitly_closed_in_m15() -> None:
    view = BudgetView(1, 1, 1, "transitions")
    with pytest.raises(ValueError, match="hardware_normalized"):
        create_budget_profile(
            profile_id="m15-hardware-v1",
            mode=BudgetMode.HARDWARE_NORMALIZED,
            deployment=view,
            mechanism=view,
        )


def test_budget_view_rejects_missing_work_value_without_type_error() -> None:
    with pytest.raises(ValueError, match="work_value"):
        BudgetView(
            wall_time_budget_ms=1,
            cpu_time_budget_ms=1,
            work_value=None,  # type: ignore[arg-type]
            work_unit="transitions",
        )
