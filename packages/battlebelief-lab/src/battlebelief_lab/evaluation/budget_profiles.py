"""Outcome-blind budget identities and calibration specifications."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from battlebelief_core.canonicalization import manifest_digest

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class BudgetMode(StrEnum):
    FIXED = "fixed"
    CALIBRATED_GRID = "calibrated_grid"
    HARDWARE_NORMALIZED = "hardware_normalized"


@dataclass(frozen=True, slots=True)
class BudgetView:
    wall_time_budget_ms: int | None
    cpu_time_budget_ms: int | None
    work_value: int
    work_unit: str

    def __post_init__(self) -> None:
        for name in ("wall_time_budget_ms", "cpu_time_budget_ms"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a non-negative integer or null")
        if type(self.work_value) is not int or self.work_value < 1:
            raise ValueError("work_value must be a positive integer")
        if type(self.work_unit) is not str or not self.work_unit:
            raise ValueError("budget work must be positive and named")

    def to_dict(self) -> dict[str, object]:
        return {
            "wall_time_budget_ms": self.wall_time_budget_ms,
            "cpu_time_budget_ms": self.cpu_time_budget_ms,
            "work_value": self.work_value,
            "work_unit": self.work_unit,
        }


@dataclass(frozen=True, slots=True)
class CalibrationSpecification:
    schema_version: int
    spec_id: str
    budget_mode: BudgetMode
    reference_environment_specification: tuple[tuple[str, str], ...]
    calibration_state_construction_rule: str
    ordered_work_grid: tuple[int, ...]
    selection_rule_id: str
    measurement_profile_id: str
    selection_measurement_id: str
    required_measurement_ids: tuple[str, ...]
    runtime_limit_ms: float
    allowed_runtime_measurements: tuple[str, ...]
    forbidden_quality_measurements: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 2:
            raise ValueError("unsupported calibration specification schema version")
        if type(self.spec_id) is not str or not self.spec_id:
            raise ValueError("spec_id must be a non-empty string")
        if not self.reference_environment_specification:
            raise ValueError("calibration specification identities must be non-empty")
        if self.budget_mode is not BudgetMode.CALIBRATED_GRID:
            raise ValueError("M1.5 calibration specification supports calibrated_grid only")
        if self.selection_rule_id != "largest-value-under-runtime-limit-v1":
            raise ValueError("unknown calibration selection rule")
        for name in (
            "measurement_profile_id",
            "selection_measurement_id",
            "calibration_state_construction_rule",
        ):
            if type(getattr(self, name)) is not str or not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if (
            type(self.runtime_limit_ms) not in (int, float)
            or not math.isfinite(self.runtime_limit_ms)
            or self.runtime_limit_ms <= 0
        ):
            raise ValueError("runtime_limit_ms must be positive")
        if not self.required_measurement_ids:
            raise ValueError("required_measurement_ids must not be empty")
        for name in (
            "required_measurement_ids",
            "allowed_runtime_measurements",
            "forbidden_quality_measurements",
        ):
            values = getattr(self, name)
            if type(values) is not tuple or any(
                type(value) is not str or not value for value in values
            ):
                raise ValueError(f"{name} must contain non-empty string IDs")
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must not contain duplicates")
        if self.selection_measurement_id not in self.required_measurement_ids:
            raise ValueError("selection measurement must be required")
        if not set(self.required_measurement_ids).issubset(self.allowed_runtime_measurements):
            raise ValueError("required measurements must be allowed runtime measurements")
        if not self.ordered_work_grid or any(
            type(value) is not int or value < 1 for value in self.ordered_work_grid
        ):
            raise ValueError("ordered work grid must contain positive integers")
        if any(
            left >= right
            for left, right in zip(self.ordered_work_grid, self.ordered_work_grid[1:], strict=False)
        ):
            raise ValueError("ordered work grid must be strictly increasing")
        if set(self.allowed_runtime_measurements) & set(self.forbidden_quality_measurements):
            raise ValueError("runtime and quality measurements must be disjoint")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "spec_id": self.spec_id,
            "budget_mode": self.budget_mode.value,
            "reference_environment_specification": dict(self.reference_environment_specification),
            "calibration_state_construction_rule": self.calibration_state_construction_rule,
            "ordered_work_grid": list(self.ordered_work_grid),
            "selection_rule_id": self.selection_rule_id,
            "measurement_profile_id": self.measurement_profile_id,
            "selection_measurement_id": self.selection_measurement_id,
            "required_measurement_ids": list(self.required_measurement_ids),
            "runtime_limit_ms": self.runtime_limit_ms,
            "allowed_runtime_measurements": list(self.allowed_runtime_measurements),
            "forbidden_quality_measurements": list(self.forbidden_quality_measurements),
        }

    @property
    def digest(self) -> str:
        return manifest_digest(self.to_dict())


@dataclass(frozen=True, slots=True)
class BudgetProfile:
    profile_id: str
    mode: BudgetMode
    deployment: BudgetView
    mechanism: BudgetView
    calibration_spec_digest: str | None = None

    def __post_init__(self) -> None:
        if type(self.profile_id) is not str or not self.profile_id:
            raise ValueError("profile_id must not be empty")
        if not isinstance(self.mode, BudgetMode):
            raise ValueError("mode must be a BudgetMode")
        if not isinstance(self.deployment, BudgetView) or not isinstance(
            self.mechanism, BudgetView
        ):
            raise ValueError("budget views must be BudgetView values")
        if self.calibration_spec_digest is not None and (
            type(self.calibration_spec_digest) is not str
            or not _DIGEST_RE.fullmatch(self.calibration_spec_digest)
        ):
            raise ValueError("calibration_spec_digest must be a sha256 digest or null")
        if self.mode is BudgetMode.CALIBRATED_GRID and self.calibration_spec_digest is None:
            raise ValueError("calibrated_grid requires a calibration specification")
        if self.mode is BudgetMode.FIXED and self.calibration_spec_digest is not None:
            raise ValueError("fixed budgets do not carry calibration evidence")
        if self.mode is BudgetMode.HARDWARE_NORMALIZED:
            raise ValueError("hardware_normalized budgets are not supported in M1.5")

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "mode": self.mode.value,
            "deployment": self.deployment.to_dict(),
            "mechanism": self.mechanism.to_dict(),
            "calibration_spec_digest": self.calibration_spec_digest,
        }

    @property
    def digest(self) -> str:
        return manifest_digest(self.to_dict())


def create_calibration_specification(
    *,
    spec_id: str,
    reference_environment_specification: Mapping[str, str],
    calibration_state_construction_rule: str,
    ordered_work_grid: Iterable[int],
    measurement_profile_id: str,
    selection_measurement_id: str,
    required_measurement_ids: Iterable[str],
    runtime_limit_ms: float,
    allowed_runtime_measurements: Iterable[str],
    forbidden_quality_measurements: Iterable[str],
) -> CalibrationSpecification:
    return CalibrationSpecification(
        schema_version=2,
        spec_id=spec_id,
        budget_mode=BudgetMode.CALIBRATED_GRID,
        reference_environment_specification=tuple(
            sorted(reference_environment_specification.items())
        ),
        calibration_state_construction_rule=calibration_state_construction_rule,
        ordered_work_grid=tuple(ordered_work_grid),
        selection_rule_id="largest-value-under-runtime-limit-v1",
        measurement_profile_id=measurement_profile_id,
        selection_measurement_id=selection_measurement_id,
        required_measurement_ids=tuple(required_measurement_ids),
        runtime_limit_ms=runtime_limit_ms,
        allowed_runtime_measurements=tuple(allowed_runtime_measurements),
        forbidden_quality_measurements=tuple(forbidden_quality_measurements),
    )


def create_budget_profile(
    *,
    profile_id: str,
    mode: BudgetMode,
    deployment: BudgetView,
    mechanism: BudgetView,
    calibration_spec: CalibrationSpecification | None = None,
) -> BudgetProfile:
    return BudgetProfile(
        profile_id=profile_id,
        mode=mode,
        deployment=deployment,
        mechanism=mechanism,
        calibration_spec_digest=None if calibration_spec is None else calibration_spec.digest,
    )


__all__ = [
    "BudgetMode",
    "BudgetProfile",
    "BudgetView",
    "CalibrationSpecification",
    "create_budget_profile",
    "create_calibration_specification",
]
