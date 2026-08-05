"""Strict loading and semantic validation for M1.5 registrations."""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import unicodedata
from collections.abc import Mapping
from itertools import pairwise
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from battlebelief_core.canonicalization import manifest_digest
from battlebelief_lab.evaluation.budget_profiles import BudgetMode, BudgetProfile, BudgetView
from battlebelief_lab.evaluation.matchup_blocks import BaseMatchupKey
from battlebelief_lab.evaluation.measurement_runner import (
    validate_measurement_run_result_document,
)
from battlebelief_lab.evaluation.schedule import Schedule, ScheduleRow, SideAssignment
from battlebelief_lab.evaluation.seed_families import SeedFamily


class RegistrationValidationError(ValueError):
    """Raised when a registration violates the strict M1.5 contract."""


_REQUIRED_CONTRACT_REFERENCES = frozenset(
    {
        "contract-manifest-schemas",
        "contract-determinism",
        "contract-provenance",
        "experiment-registration",
        "evaluation-target-population",
        "evaluation-pool-separation",
    }
)
_TASK21_SOURCE_COMMIT = "ebbc648fc62908a0227e8d90ab03b3692f583aca"
_MAX_SAFE_INTEGER = 9_007_199_254_740_991
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def schema_issue_summary(issue: Any) -> str:
    """Return a diagnostic that cannot echo an invalid instance value."""

    validator = issue.validator if isinstance(issue.validator, str) else "unknown"
    return f"schema violation ({validator}) at {issue.json_path}"


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RegistrationValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> Any:
    del value
    raise RegistrationValidationError("non-finite JSON number")


def _validate_value(value: Any) -> None:
    if isinstance(value, str):
        if unicodedata.normalize("NFC", value) != value:
            raise RegistrationValidationError("JSON strings must be NFC-normalized")
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise RegistrationValidationError("JSON numbers must be finite")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _validate_value(key)
            _validate_value(child)
    elif isinstance(value, list):
        for child in value:
            _validate_value(child)


def load_json_strict(path: Path) -> Any:
    """Load JSON with duplicate-key, finite-number, and NFC guarantees."""

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
    except RegistrationValidationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegistrationValidationError(
            f"cannot load strict JSON {path.name}: {type(exc).__name__}"
        ) from exc
    _validate_value(value)
    return value


def _reject_placeholders(value: Any, *, path: str = "$") -> None:
    if isinstance(value, str) and value.strip().casefold() in {
        "todo",
        "tbd",
        "fixme",
        "placeholder",
    }:
        raise RegistrationValidationError(f"placeholder value at {path}")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _reject_placeholders(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_placeholders(child, path=f"{path}[{index}]")


def validate_calibration_spec(spec: Mapping[str, Any]) -> None:
    """Validate calibration rules that are independent of measured evidence."""

    _reject_placeholders(spec)
    if spec.get("budget_mode") != "calibrated_grid":
        raise RegistrationValidationError(
            "calibration budget mode is unsupported; only calibrated_grid is implemented"
        )
    if spec.get("selection_rule_id") != "largest-value-under-runtime-limit-v1":
        raise RegistrationValidationError(
            f"unknown selection_rule_id: {spec.get('selection_rule_id')}"
        )
    if spec.get("schema_version") == 3:
        if spec.get("calibrated_parameter") != "per_world_work":
            raise RegistrationValidationError("calibration parameter must be per_world_work")
        if spec.get("world_sampling_count") != 16:
            raise RegistrationValidationError("calibration world count must be 16")
        if spec.get("total_work_formula") != "world_sampling_count_times_per_world_work":
            raise RegistrationValidationError("calibration total-work formula is invalid")
        if spec.get("calibration_state_rule_id") != "m15-synthetic-calibration-state-v1":
            raise RegistrationValidationError("unknown calibration state construction rule")
        limits = spec.get("runtime_limits_ms")
        if (
            not isinstance(limits, Mapping)
            or limits.get("wall_time_ms") != 2000
            or limits.get("cpu_time_ms") != 2000
        ):
            raise RegistrationValidationError(
                "M1.5 calibration wall and CPU limits must be 2000 ms"
            )
        if not _DIGEST_RE.fullmatch(str(spec.get("calibration_state_manifest_digest", ""))):
            raise RegistrationValidationError("calibration state manifest digest is invalid")
    grid = spec.get("ordered_work_grid")
    if not isinstance(grid, list) or any(
        not isinstance(value, int) or isinstance(value, bool) for value in grid
    ):
        raise RegistrationValidationError("calibration work grid must contain integers")
    if any(left >= right for left, right in pairwise(grid)):
        raise RegistrationValidationError("calibration work grid must be strictly increasing")
    required = spec.get("required_measurement_ids")
    allowed = spec.get("allowed_runtime_measurements")
    forbidden = spec.get("forbidden_quality_measurements")
    if (
        not isinstance(required, list)
        or not isinstance(allowed, list)
        or not isinstance(forbidden, list)
    ):
        raise RegistrationValidationError("calibration measurement lists are invalid")
    if spec.get("selection_measurement_id") not in required:
        raise RegistrationValidationError("selection_measurement_id is not required")
    if not set(required).issubset(allowed):
        raise RegistrationValidationError("required calibration measurements are not allowed")
    overlap = set(allowed).intersection(forbidden)
    if overlap:
        raise RegistrationValidationError("runtime and quality measurement sets overlap")


def validate_calibration_evidence(evidence: Mapping[str, Any], spec: Mapping[str, Any]) -> None:
    """Validate measured calibration rows against their frozen specification."""

    validate_calibration_spec(spec)
    shared_fields = ("measurement_profile_id", "selection_measurement_id")
    for field in shared_fields:
        if evidence.get(field) != spec.get(field):
            raise RegistrationValidationError(f"calibration {field} mismatch")
    if spec.get("schema_version") == 3:
        if evidence.get("runtime_limits_ms") != spec.get("runtime_limits_ms"):
            raise RegistrationValidationError("calibration runtime limits mismatch")
    elif evidence.get("runtime_limit_ms") != spec.get("runtime_limit_ms"):
        raise RegistrationValidationError("calibration runtime_limit_ms mismatch")
    grid = spec.get("ordered_work_grid")
    rows = evidence.get("runtime_measurements")
    required = spec.get("required_measurement_ids")
    allowed = spec.get("allowed_runtime_measurements")
    forbidden = spec.get("forbidden_quality_measurements")
    selection_id = spec.get("selection_measurement_id")
    limits = spec.get("runtime_limits_ms")
    if spec.get("schema_version") == 3:
        if not isinstance(limits, Mapping):
            raise RegistrationValidationError("calibration runtime limits are invalid")
        wall_limit = limits.get("wall_time_ms")
        cpu_limit = limits.get("cpu_time_ms")
    else:
        wall_limit = spec.get("runtime_limit_ms")
        cpu_limit = wall_limit
    if not isinstance(grid, list) or not isinstance(rows, list):
        raise RegistrationValidationError("calibration measurements are invalid")
    if not all(isinstance(value, Mapping) for value in rows):
        raise RegistrationValidationError("calibration measurement rows are invalid")
    work_values = [row.get("work_value") for row in rows]
    if work_values != grid:
        raise RegistrationValidationError("calibration measurements do not cover the work grid")
    if not isinstance(required, list) or not isinstance(allowed, list):
        raise RegistrationValidationError("calibration measurement lists are invalid")
    if (
        not isinstance(wall_limit, (int, float))
        or isinstance(wall_limit, bool)
        or not isinstance(cpu_limit, (int, float))
        or isinstance(cpu_limit, bool)
    ):
        raise RegistrationValidationError("calibration runtime limits are invalid")
    forbidden_set = set(forbidden) if isinstance(forbidden, list) else set()
    eligible: list[int] = []
    for row in rows:
        measurements = row.get("measurements")
        status = row.get("status")
        if not isinstance(measurements, Mapping):
            raise RegistrationValidationError("calibration measurements must be an object")
        unknown = set(measurements).difference(allowed)
        if unknown:
            raise RegistrationValidationError("calibration has an unknown runtime measurement")
        if set(measurements).intersection(forbidden_set):
            raise RegistrationValidationError(
                "calibration contains a forbidden quality measurement"
            )
        if status in {"completed", "over_limit"}:
            if not set(required).issubset(measurements):
                raise RegistrationValidationError("calibration row lacks required measurements")
            selected = measurements.get(selection_id)
            if not isinstance(selected, (int, float)) or isinstance(selected, bool):
                raise RegistrationValidationError("selection measurement is not numeric")
            cpu_time = measurements.get("cpu_time_ms")
            if not isinstance(cpu_time, (int, float)) or isinstance(cpu_time, bool):
                raise RegistrationValidationError("CPU measurement is not numeric")
            if status == "completed" and (selected > wall_limit or cpu_time > cpu_limit):
                raise RegistrationValidationError("completed calibration row is over_limit")
            if status == "over_limit" and (selected <= wall_limit and cpu_time <= cpu_limit):
                raise RegistrationValidationError(
                    "over_limit calibration row is below runtime limit"
                )
            if status == "completed":
                eligible.append(row["work_value"])
        elif status in {"failed", "unsupported"}:
            if measurements or not isinstance(row.get("error_class"), str):
                raise RegistrationValidationError(
                    "failed calibration row has inconsistent evidence"
                )
        else:
            raise RegistrationValidationError("unknown calibration row status")
    expected = max(eligible) if eligible else None
    if evidence.get("selected_work_value") != expected:
        raise RegistrationValidationError("selected calibration work value is not reproducible")


def validate_registration_semantics(
    registration: Mapping[str, Any], root: Path | None = None
) -> None:
    """Validate cross-field invariants not expressible in JSON Schema."""

    _reject_placeholders(registration)

    def require_unique_reference_ids(value: Any, field: str, label: str) -> None:
        if not isinstance(value, list):
            return
        seen: set[str] = set()
        for reference in value:
            if not isinstance(reference, Mapping):
                continue
            identifier = reference.get(field)
            if not isinstance(identifier, str):
                continue
            if identifier in seen:
                raise RegistrationValidationError(f"duplicate {label}: {identifier}")
            seen.add(identifier)

    require_unique_reference_ids(
        registration.get("contract_references"), "document_id", "contract reference"
    )
    require_unique_reference_ids(registration.get("metric_references"), "metric_id", "metric_id")
    require_unique_reference_ids(
        registration.get("estimand_references"), "estimand_id", "estimand_id"
    )
    require_unique_reference_ids(
        registration.get("analysis_procedure_references"),
        "analysis_procedure_id",
        "analysis_procedure_id",
    )
    if root is not None:
        owner_rules = (
            ("metric_references", "evaluation-metrics"),
            ("estimand_references", "evaluation-statistical-analysis"),
            ("analysis_procedure_references", "evaluation-statistical-analysis"),
        )
        for field, expected_owner in owner_rules:
            references = registration.get(field)
            if not isinstance(references, list):
                continue
            for reference in references:
                if (
                    isinstance(reference, Mapping)
                    and reference.get("document_id") != expected_owner
                ):
                    raise RegistrationValidationError(f"{field} must reference {expected_owner}")
    forbidden_unsealed_fields = {
        "policy_digest",
        "implementation_digest",
        "team_pool_digest",
        "opponent_policy_pool_digest",
        "schedule_digest",
        "calibration_evidence_digest",
    }
    if forbidden_unsealed_fields.intersection(registration):
        raise RegistrationValidationError("implementation digest in unsealed registration")
    arms = registration.get("arms")
    if not isinstance(arms, list):
        raise RegistrationValidationError("arms must be a list")
    arm_ids: set[str] = set()
    for arm in arms:
        if not isinstance(arm, Mapping):
            raise RegistrationValidationError("arm must be an object")
        arm_id = arm.get("arm_id")
        if not isinstance(arm_id, str):
            raise RegistrationValidationError("arm_id must be a string")
        if arm_id in arm_ids:
            raise RegistrationValidationError(f"duplicate arm_id: {arm_id}")
        arm_ids.add(arm_id)
        if (
            arm_id.startswith("information_set_duct_")
            and arm.get("search_algorithm_id") != "information_set_duct_v0"
        ):
            raise RegistrationValidationError(
                f"information_set_duct arm {arm_id} requires search_algorithm_id "
                "information_set_duct_v0"
            )

    comparisons = registration.get("comparisons")
    if not isinstance(comparisons, list):
        raise RegistrationValidationError("comparisons must be a list")
    comparison_ids: set[str] = set()

    def declared_ids(value: Any, field: str) -> set[str]:
        if not isinstance(value, list):
            return set()
        return {
            reference[field]
            for reference in value
            if isinstance(reference, Mapping) and isinstance(reference.get(field), str)
        }

    metric_ids = declared_ids(registration.get("metric_references"), "metric_id")
    estimand_ids = declared_ids(registration.get("estimand_references"), "estimand_id")
    analysis_procedure_ids = declared_ids(
        registration.get("analysis_procedure_references"), "analysis_procedure_id"
    )
    rule_registry: dict[str, set[str]] = {}
    metric_roles: dict[str, set[str]] = {}
    metric_directions: dict[str, str] = {}
    statistical_registry: dict[str, set[str]] = {}
    if root is not None:
        documents = _document_index(root)
        contract_references = registration.get("contract_references")
        if not isinstance(contract_references, list):
            raise RegistrationValidationError("contract_references must be a list")
        contract_ids = {
            reference.get("document_id")
            for reference in contract_references
            if isinstance(reference, Mapping)
        }
        missing_contracts = sorted(_REQUIRED_CONTRACT_REFERENCES.difference(contract_ids))
        if missing_contracts:
            raise RegistrationValidationError(
                f"missing required contract reference: {missing_contracts[0]}"
            )
        rule_registry = _registration_rule_registry_from_references(contract_references, documents)
        metric_registry = _metric_registry_from_references(
            registration.get("metric_references"), documents
        )
        statistical_registry = _statistical_registry_from_references(
            registration.get("estimand_references"),
            registration.get("analysis_procedure_references"),
            documents,
        )
        metric_references = registration.get("metric_references")
        for reference in metric_references if isinstance(metric_references, list) else []:
            if isinstance(reference, Mapping) and isinstance(reference.get("metric_id"), str):
                metric_id = reference["metric_id"]
                if metric_id in metric_registry:
                    role = str(reference.get("role"))
                    if role not in set(metric_registry[metric_id]["roles"].split(", ")):
                        raise RegistrationValidationError(
                            f"metric {metric_id} cannot be used with role {role}"
                        )
                    metric_roles.setdefault(metric_id, set()).add(role)
                    metric_directions[metric_id] = metric_registry[metric_id]["direction"]
    for comparison in comparisons:
        if not isinstance(comparison, Mapping):
            raise RegistrationValidationError("comparison must be an object")
        comparison_id = comparison.get("comparison_id")
        if not isinstance(comparison_id, str):
            raise RegistrationValidationError("comparison_id must be a string")
        if comparison_id in comparison_ids:
            raise RegistrationValidationError(f"duplicate comparison_id: {comparison_id}")
        comparison_ids.add(comparison_id)
        for field in ("left_arm_id", "right_arm_id"):
            arm_id = comparison.get(field)
            if arm_id not in arm_ids:
                raise RegistrationValidationError(f"unknown arm referenced by {field}: {arm_id}")
        if comparison.get("primary_metric_id") not in metric_ids:
            raise RegistrationValidationError(
                f"comparison {comparison_id} references undeclared primary_metric_id"
            )
        if comparison.get("left_arm_id") == comparison.get("right_arm_id"):
            raise RegistrationValidationError(
                f"comparison {comparison_id} compares an arm to itself"
            )
        left_arm = next(
            arm
            for arm in arms
            if isinstance(arm, Mapping) and arm.get("arm_id") == comparison.get("left_arm_id")
        )
        right_arm = next(
            arm
            for arm in arms
            if isinstance(arm, Mapping) and arm.get("arm_id") == comparison.get("right_arm_id")
        )
        if left_arm.get("lifecycle") != "active" or right_arm.get("lifecycle") != "active":
            raise RegistrationValidationError(
                f"comparison {comparison_id} references a non-active arm"
            )
        primary_metric_id = comparison.get("primary_metric_id")
        primary_metric_key = primary_metric_id if isinstance(primary_metric_id, str) else ""
        if root is not None:
            if "primary" not in metric_roles.get(primary_metric_key, set()):
                raise RegistrationValidationError(
                    f"comparison {comparison_id} primary metric is not registered as primary"
                )
            expected_direction = metric_directions.get(primary_metric_key)
            if expected_direction is not None and comparison.get("direction") != expected_direction:
                raise RegistrationValidationError(
                    f"comparison {comparison_id} direction disagrees with primary metric"
                )
        if comparison.get("estimand_id") not in estimand_ids:
            raise RegistrationValidationError(
                f"comparison {comparison_id} references undeclared estimand_id"
            )
        if comparison.get("analysis_procedure_id") not in analysis_procedure_ids:
            raise RegistrationValidationError(
                f"comparison {comparison_id} references undeclared analysis_procedure_id"
            )
        if comparison.get("technical_outcome_treatment_id") not in analysis_procedure_ids:
            raise RegistrationValidationError(
                f"comparison {comparison_id} references undeclared technical outcome treatment"
            )
        if root is not None:
            if comparison.get("estimand_id") not in statistical_registry.get("estimand_id", set()):
                raise RegistrationValidationError(
                    f"comparison {comparison_id} references unknown estimand_id"
                )
            if comparison.get("analysis_procedure_id") not in statistical_registry.get(
                "analysis_procedure_id", set()
            ):
                raise RegistrationValidationError(
                    f"comparison {comparison_id} references unknown analysis_procedure_id"
                )
            if comparison.get("technical_outcome_treatment_id") not in statistical_registry.get(
                "technical_outcome_treatment_id", set()
            ):
                raise RegistrationValidationError(
                    f"comparison {comparison_id} references invalid technical outcome treatment"
                )
            rule_fields = () if registration.get("schema_version") == 4 else ("tie_break_rule_id",)
            for field in rule_fields:
                if comparison.get(field) not in rule_registry.get(field, set()):
                    raise RegistrationValidationError(f"unknown {field}: {comparison.get(field)}")
            if registration.get("schema_version") == 4 and (
                comparison.get("tie_break_metric_id") != "end_to_end_latency_ms_v1"
                or comparison.get("tie_break_direction") != "lower_is_better"
            ):
                raise RegistrationValidationError(
                    f"comparison {comparison_id} has an invalid tie-break metric"
                )
            if registration.get("schema_version") == 4:
                tie_break_id = comparison.get("tie_break_metric_id")
                if tie_break_id not in metric_ids or tie_break_id not in metric_roles:
                    raise RegistrationValidationError(
                        f"comparison {comparison_id} tie-break metric is not registered"
                    )
                if metric_directions.get(tie_break_id) != "lower_is_better":
                    raise RegistrationValidationError(
                        f"comparison {comparison_id} tie-break direction is invalid"
                    )

    budget_profiles = registration.get("budget_profiles")
    if isinstance(budget_profiles, Mapping):
        for profile_name, profile in budget_profiles.items():
            if not isinstance(profile, Mapping):
                raise RegistrationValidationError(
                    f"budget profile {profile_name} must be an object"
                )
            mode = profile.get("budget_mode", profile.get("mode"))
            if registration.get("schema_version") == 4:
                if profile.get("calibrated_parameter") != "per_world_work":
                    raise RegistrationValidationError(
                        f"budget profile {profile_name} must calibrate per_world_work"
                    )
                if profile.get("ordered_work_grid") != [64, 128, 256, 512]:
                    raise RegistrationValidationError(
                        f"budget profile {profile_name} has an invalid work grid"
                    )
                if profile.get("total_work_formula") != (
                    "world_sampling_count_times_per_world_work"
                ):
                    raise RegistrationValidationError(
                        f"budget profile {profile_name} has an invalid total-work formula"
                    )
                deployment = profile.get("deployment")
                mechanism = profile.get("mechanism")
                if (
                    not isinstance(deployment, Mapping)
                    or deployment.get("wall_time_budget_ms") != 2000
                    or deployment.get("cpu_time_budget_ms") != 2000
                    or deployment.get("work_value") is not None
                    or not isinstance(mechanism, Mapping)
                    or mechanism.get("work_value") is not None
                ):
                    raise RegistrationValidationError(
                        f"budget profile {profile_name} must bind limits without a selected work value"
                    )
                continue
            selected = profile.get("selected_work_value")
            calibration = profile.get("calibration_spec_digest")
            benchmark = profile.get("benchmark_spec_digest")
            if mode == "fixed" and (
                not isinstance(selected, int)
                or selected < 1
                or calibration is not None
                or benchmark is not None
            ):
                raise RegistrationValidationError(f"fixed budget {profile_name} is inconsistent")
            if mode == "calibrated_grid" and (
                selected is not None or not isinstance(calibration, str) or benchmark is not None
            ):
                raise RegistrationValidationError(
                    f"calibrated budget {profile_name} is inconsistent"
                )
            if mode == "hardware_normalized":
                raise RegistrationValidationError(
                    f"hardware-normalized budget {profile_name} is unsupported"
                )
    if root is not None:
        pool_rules = registration.get("pool_rules")
        if isinstance(pool_rules, Mapping):
            for field in (
                "construction_rule_id",
                "near_duplicate_rule_id",
                "side_assignment_rule_id",
                "schedule_rule_id",
            ):
                if pool_rules.get(field) not in rule_registry.get(field, set()):
                    raise RegistrationValidationError(f"unknown {field}: {pool_rules.get(field)}")
        for gate in registration.get("decision_gates", []):
            if isinstance(gate, Mapping):
                gate_rule_fields = ["stop_rule_id", "pivot_rule_id"]
                if registration.get("schema_version") == 4:
                    gate_rule_fields.append("go_rule_id")
                for field in gate_rule_fields:
                    if gate.get(field) not in rule_registry.get(field, set()):
                        raise RegistrationValidationError(f"unknown {field}: {gate.get(field)}")
        if registration.get("schema_version") == 4:
            comparisons_by_id = {
                comparison.get("comparison_id"): comparison
                for comparison in registration.get("comparisons", [])
                if isinstance(comparison, Mapping)
            }
            gates = registration.get("decision_gates")
            if not isinstance(gates, list) or set(comparisons_by_id) != {
                gate.get("comparison_id") for gate in gates if isinstance(gate, Mapping)
            }:
                raise RegistrationValidationError(
                    "decision gates must bind exactly one gate to each comparison"
                )
            for gate in gates:
                if not isinstance(gate, Mapping):
                    continue
                comparison = comparisons_by_id.get(gate.get("comparison_id"))
                if not isinstance(comparison, Mapping):
                    continue
                for field in (
                    "primary_metric_id",
                    "estimand_id",
                    "analysis_procedure_id",
                    "minimum_effect",
                    "confidence_level",
                    "confidence_sidedness",
                    "tie_break_metric_id",
                    "tie_break_direction",
                ):
                    if gate.get(field) != comparison.get(field):
                        raise RegistrationValidationError(
                            f"decision gate does not match comparison {comparison.get('comparison_id')}"
                        )


_SCHEMA_BY_KIND = {
    "implementation": "evaluation-arm-binding.schema.json",
    "run": "evaluation-run-binding.schema.json",
    "synthetic_acceptance": "synthetic-fixture-manifest.schema.json",
}


def _schema_for_artifact(
    path: Path, value: Mapping[str, Any], repository_root: Path
) -> tuple[Path, str] | None:
    if path.name == "measurement-run-result.example.json" or {
        "run_status",
        "battle_outcome",
        "trace_status",
    }.issubset(value):
        return (
            repository_root / "schemas/records/measurement-run-result.schema.json",
            "measurement_run_result",
        )
    if path.name == "registration.json" or "registration_status" in value:
        schema_name = (
            "experiment-registration-v4.schema.json"
            if value.get("schema_version") == 4
            else "experiment-registration.schema.json"
        )
        return (
            repository_root / "schemas/manifests" / schema_name,
            "registration",
        )
    if value.get("rule_id") == "m15-synthetic-calibration-state-v1":
        return (
            repository_root / "schemas/manifests/calibration-state-manifest-v1.schema.json",
            "calibration_state_manifest",
        )
    kind = value.get("binding_kind")
    if isinstance(kind, str) and kind in _SCHEMA_BY_KIND:
        version = value.get("schema_version")
        versioned_names = {
            ("implementation", 3): "evaluation-arm-binding-v3.schema.json",
            ("run", 3): "evaluation-run-binding-v3.schema.json",
        }
        version_key = version if type(version) is int else -1
        schema_name = versioned_names.get((kind, version_key), _SCHEMA_BY_KIND[kind])
        return (
            repository_root / "schemas/manifests" / schema_name,
            kind,
        )
    if value.get("purpose") == "synthetic_acceptance":
        schema_name = (
            "synthetic-fixture-manifest-v3.schema.json"
            if value.get("schema_version") == 3
            else "synthetic-fixture-manifest.schema.json"
        )
        return (
            repository_root / "schemas/manifests" / schema_name,
            "synthetic_acceptance",
        )
    if "evidence_id" in value:
        schema_name = (
            "budget-calibration-evidence-v3.schema.json"
            if value.get("schema_version") == 3
            else "budget-calibration-evidence.schema.json"
        )
        return (
            repository_root / "schemas/manifests" / schema_name,
            "calibration_evidence",
        )
    if "reference_environment_specification" in value:
        schema_name = (
            "budget-calibration-spec-v3.schema.json"
            if value.get("schema_version") == 3
            else "budget-calibration-spec.schema.json"
        )
        return (
            repository_root / "schemas/manifests" / schema_name,
            "calibration_spec",
        )
    if {"spec_id", "world_sampling", "lookahead"}.issubset(value):
        schema_name = (
            "search-execution-spec-v3.schema.json"
            if value.get("schema_version") == 3
            else "search-execution-spec.schema.json"
        )
        return (
            repository_root / "schemas/manifests" / schema_name,
            "search_execution",
        )
    return None


def _document_index(root: Path) -> dict[tuple[str, int], list[dict[str, object]]]:
    result: dict[tuple[str, int], list[dict[str, object]]] = {}
    docs_root = root / "docs"
    for path in sorted(docs_root.rglob("*.md")):
        if "archive" in path.relative_to(docs_root).parts:
            continue
        text = path.read_text(encoding="utf-8")
        frontmatter = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        if frontmatter is None:
            continue
        document_id = re.search(r"^document_id:\s*(\S+)\s*$", frontmatter.group(1), re.MULTILINE)
        version = re.search(r"^version:\s*(\d+)\s*$", frontmatter.group(1), re.MULTILINE)
        status = re.search(r"^status:\s*(\S+)\s*$", frontmatter.group(1), re.MULTILINE)
        normative = re.search(r"^normative:\s*(true|false)\s*$", frontmatter.group(1), re.MULTILINE)
        document_type = re.search(
            r"^document_type:\s*(\S+)\s*$", frontmatter.group(1), re.MULTILINE
        )
        if document_id is not None and version is not None:
            record = {
                "version": int(version.group(1)),
                "status": status.group(1) if status is not None else None,
                "normative": normative is not None and normative.group(1) == "true",
                "document_type": document_type.group(1) if document_type is not None else None,
                "text": text,
                "path": path,
                "document_digest": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            result.setdefault((document_id.group(1), int(version.group(1))), []).append(record)

    snapshot_root = docs_root / "archive/document-snapshots"
    metadata_schema_path = root / "schemas/documents/document-snapshot-metadata.schema.json"
    if not snapshot_root.exists():
        return result
    try:
        metadata_schema = load_json_strict(metadata_schema_path)
        Draft202012Validator.check_schema(metadata_schema)
        metadata_validator = Draft202012Validator(metadata_schema, format_checker=FormatChecker())
    except Exception as exc:
        raise RegistrationValidationError(
            f"cannot load document snapshot metadata schema: {type(exc).__name__}"
        ) from exc

    for metadata_path in sorted(snapshot_root.rglob("*.metadata.json")):
        try:
            metadata = load_json_strict(metadata_path)
        except RegistrationValidationError as exc:
            raise RegistrationValidationError(
                f"invalid document snapshot metadata {metadata_path.name}"
            ) from exc
        schema_errors = list(metadata_validator.iter_errors(metadata))
        if schema_errors:
            raise RegistrationValidationError(
                f"invalid document snapshot metadata {metadata_path.name}: "
                f"{schema_issue_summary(schema_errors[0])}"
            )
        if not isinstance(metadata, Mapping):
            raise RegistrationValidationError(
                f"invalid document snapshot metadata {metadata_path.name}"
            )
        snapshot_path_text = metadata["snapshot_path"]
        if not isinstance(snapshot_path_text, str):
            raise RegistrationValidationError("contract snapshot path is invalid")
        normalized = snapshot_path_text.replace("\\", "/")
        parts = normalized.split("/")
        if (
            not normalized.startswith("docs/archive/document-snapshots/")
            or any(part in {"", ".", ".."} for part in parts)
            or re.match(r"^[A-Za-z]:", normalized)
        ):
            raise RegistrationValidationError("contract snapshot path is invalid")
        snapshot_path = root / Path(*parts)
        try:
            resolved_snapshot = snapshot_path.resolve()
            resolved_snapshot.relative_to(snapshot_root.resolve())
        except ValueError as exc:
            raise RegistrationValidationError(
                "document snapshot path escapes archive root"
            ) from exc
        if resolved_snapshot != snapshot_path:
            raise RegistrationValidationError("document snapshot path is not stable")
        expected_snapshot_path = metadata_path.with_name(
            metadata_path.name.removesuffix(".metadata.json") + ".md"
        )
        if snapshot_path != expected_snapshot_path:
            raise RegistrationValidationError("document snapshot path does not match metadata")
        if not snapshot_path.is_file():
            raise RegistrationValidationError("document snapshot file is missing")
        actual_digest = "sha256:" + hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
        if metadata["snapshot_digest"] != actual_digest:
            raise RegistrationValidationError("document snapshot digest mismatch")
        if metadata["source_digest"] != metadata["snapshot_digest"]:
            raise RegistrationValidationError("document snapshot source digest mismatch")
        try:
            text = snapshot_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise RegistrationValidationError("document snapshot is not valid UTF-8") from exc
        identity = (metadata["document_id"], metadata["document_version"])
        existing = result.get(identity, [])
        if any(
            candidate.get("document_digest") == actual_digest
            and "document-snapshots" in str(candidate.get("path")).replace("\\", "/")
            for candidate in existing
        ):
            raise RegistrationValidationError(
                f"duplicate document snapshot: {metadata['document_id']} "
                f"v{metadata['document_version']}"
            )
        record = {
            "version": metadata["document_version"],
            "status": metadata["status"],
            "normative": metadata["normative"],
            "document_type": metadata["document_type"],
            "text": text,
            "path": snapshot_path,
            "document_digest": actual_digest,
        }
        result.setdefault(identity, []).append(record)
    return result


def _latest_document(
    documents: Mapping[tuple[str, int], list[dict[str, object]]], document_id: str
) -> dict[str, object] | None:
    candidates = [
        record
        for (candidate_id, _), records in documents.items()
        if candidate_id == document_id
        for record in records
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda record: (
            record["version"] if isinstance(record["version"], int) else -1,
            "document-snapshots" not in str(record["path"]).replace("\\", "/"),
        ),
        reverse=True,
    )
    return candidates[0]


def _metric_registry(root: Path) -> dict[str, dict[str, str]]:
    """Read metric direction and roles from the normative metrics table."""

    document = _latest_document(_document_index(root), "evaluation-metrics")
    text = document.get("text") if document is not None else None
    result: dict[str, dict[str, str]] = {}
    if not isinstance(text, str):
        return result
    for line in text.splitlines():
        columns = [column.strip() for column in line.strip().strip("|").split("|")]
        if len(columns) != 4 or not columns[0].startswith("`"):
            continue
        metric_id = columns[0].strip("`")
        direction = {
            "niedriger ist besser": "lower_is_better",
            "höher ist besser": "higher_is_better",
        }.get(columns[2])
        if direction is None:
            continue
        result[metric_id] = {"direction": direction, "roles": columns[3]}
    if not result:
        raise RegistrationValidationError("evaluation-metrics registry could not be parsed")
    return result


def _registration_rule_registry(root: Path) -> dict[str, set[str]]:
    document = _latest_document(_document_index(root), "experiment-registration")
    text = document.get("text") if document is not None else None
    result: dict[str, set[str]] = {}
    if isinstance(text, str):
        for line in text.splitlines():
            columns = [column.strip().strip("`") for column in line.strip().strip("|").split("|")]
            if len(columns) == 2 and columns[0].endswith("_id") and columns[1]:
                result.setdefault(columns[0], set()).add(columns[1])
    if not result:
        raise RegistrationValidationError(
            "experiment-registration rule registry could not be parsed"
        )
    return result


def _statistical_registry(root: Path) -> dict[str, set[str]]:
    document = _latest_document(_document_index(root), "evaluation-statistical-analysis")
    text = document.get("text") if document is not None else None
    result: dict[str, set[str]] = {}
    if isinstance(text, str):
        for line in text.splitlines():
            columns = [column.strip().strip("`") for column in line.strip().strip("|").split("|")]
            if len(columns) == 3 and columns[0] in {
                "estimand_id",
                "analysis_procedure_id",
                "technical_outcome_treatment_id",
            }:
                result.setdefault(columns[0], set()).add(columns[1])
    if not result:
        raise RegistrationValidationError(
            "evaluation-statistical-analysis registry could not be parsed"
        )
    return result


def _resolve_bound_document(
    reference: Mapping[str, Any],
    documents: Mapping[tuple[str, int], list[dict[str, object]]],
) -> dict[str, object]:
    """Resolve exactly the document identity and digest carried by a reference."""

    document_id = reference.get("document_id")
    document_version = reference.get("document_version")
    document_digest = reference.get("document_digest")
    if not isinstance(document_id, str) or not isinstance(document_version, int):
        raise RegistrationValidationError("bound document reference has invalid identity")
    if isinstance(document_version, bool) or not isinstance(document_digest, str):
        raise RegistrationValidationError(f"bound document reference is incomplete: {document_id}")
    document = next(
        (
            candidate
            for candidate in documents.get((document_id, document_version), [])
            if candidate.get("document_digest") == document_digest
        ),
        None,
    )
    if document is None:
        raise RegistrationValidationError(
            f"bound document reference cannot be resolved: {document_id} v{document_version}"
        )
    return document


def _metric_registry_from_references(
    references: Any,
    documents: Mapping[tuple[str, int], list[dict[str, object]]],
) -> dict[str, dict[str, str]]:
    """Read metric semantics only from documents bound by the registration."""

    if not isinstance(references, list):
        raise RegistrationValidationError("metric_references must be a list")
    result: dict[str, dict[str, str]] = {}
    for reference in references:
        if not isinstance(reference, Mapping) or not isinstance(reference.get("metric_id"), str):
            continue
        document = _resolve_bound_document(reference, documents)
        text = document.get("text")
        if not isinstance(text, str):
            raise RegistrationValidationError("evaluation-metrics registry has no text")
        parsed: dict[str, dict[str, str]] = {}
        for line in text.splitlines():
            columns = [column.strip() for column in line.strip().strip("|").split("|")]
            if len(columns) != 4 or not columns[0].startswith("`"):
                continue
            metric_id = columns[0].strip("`")
            direction_text = columns[2].replace("\ufffd", "ö").replace("Ã¶", "ö")
            direction = {
                "niedriger ist besser": "lower_is_better",
                "höher ist besser": "higher_is_better",
            }.get(direction_text)
            if direction is not None:
                parsed[metric_id] = {"direction": direction, "roles": columns[3]}
        metric_id = reference["metric_id"]
        if metric_id not in parsed:
            raise RegistrationValidationError(f"unknown metric_id: {metric_id}")
        result[metric_id] = parsed[metric_id]
    if not result:
        raise RegistrationValidationError("evaluation-metrics registry could not be parsed")
    return result


def _registration_rule_registry_from_references(
    references: Any,
    documents: Mapping[tuple[str, int], list[dict[str, object]]],
) -> dict[str, set[str]]:
    """Read rule IDs from the exact bound registration contract."""

    if not isinstance(references, list):
        raise RegistrationValidationError("contract_references must be a list")
    reference = next(
        (
            candidate
            for candidate in references
            if isinstance(candidate, Mapping)
            and candidate.get("document_id") == "experiment-registration"
        ),
        None,
    )
    if reference is None:
        raise RegistrationValidationError("experiment-registration contract reference is missing")
    document = _resolve_bound_document(reference, documents)
    text = document.get("text")
    result: dict[str, set[str]] = {}
    if isinstance(text, str):
        for line in text.splitlines():
            columns = [column.strip().strip("`") for column in line.strip().strip("|").split("|")]
            if len(columns) >= 2 and columns[0].endswith("_id") and columns[1]:
                result.setdefault(columns[0], set()).add(columns[1])
    if not result:
        raise RegistrationValidationError(
            "experiment-registration rule registry could not be parsed"
        )
    return result


def _statistical_registry_from_references(
    estimand_references: Any,
    analysis_references: Any,
    documents: Mapping[tuple[str, int], list[dict[str, object]]],
) -> dict[str, set[str]]:
    """Read statistical IDs only from exactly referenced analysis documents."""

    if not isinstance(estimand_references, list) or not isinstance(analysis_references, list):
        raise RegistrationValidationError("statistical references must be lists")
    result: dict[str, set[str]] = {}
    seen_documents: set[tuple[str, int, str]] = set()
    for reference in [*estimand_references, *analysis_references]:
        if not isinstance(reference, Mapping):
            continue
        document = _resolve_bound_document(reference, documents)
        document_version = reference.get("document_version")
        if not isinstance(document_version, int) or isinstance(document_version, bool):
            raise RegistrationValidationError("bound document reference has invalid version")
        key = (
            str(reference.get("document_id")),
            document_version,
            str(reference.get("document_digest")),
        )
        if key in seen_documents:
            continue
        seen_documents.add(key)
        text = document.get("text")
        if not isinstance(text, str):
            continue
        for line in text.splitlines():
            columns = [column.strip().strip("`") for column in line.strip().strip("|").split("|")]
            if len(columns) == 3 and columns[0] in {
                "estimand_id",
                "analysis_procedure_id",
                "technical_outcome_treatment_id",
            }:
                result.setdefault(columns[0], set()).add(columns[1])
    if not result:
        raise RegistrationValidationError(
            "evaluation-statistical-analysis registry could not be parsed"
        )
    return result


def _validate_document_reference(
    reference: Mapping[str, Any],
    documents: Mapping[tuple[str, int], list[dict[str, object]]],
    errors: list[str],
    *,
    expected_document_type: str,
    expected_normative: bool,
    identifier_field: str | None = None,
) -> None:
    document_id = reference.get("document_id")
    document_version = reference.get("document_version")
    if not isinstance(document_id, str):
        errors.append("document reference has invalid document_id")
        return
    if not isinstance(document_version, int) or isinstance(document_version, bool):
        errors.append(f"document reference has invalid document_version: {document_id}")
        return
    candidates = documents.get((document_id, document_version), [])
    if not candidates:
        if any(candidate_id == document_id for candidate_id, _ in documents):
            errors.append(f"document version mismatch: {document_id}")
        else:
            errors.append(f"unknown document reference: {document_id}")
        return
    document_digest = reference.get("document_digest")
    if not isinstance(document_digest, str):
        errors.append(f"document reference has no document digest: {document_id}")
        return
    document = next(
        (
            candidate
            for candidate in candidates
            if candidate.get("document_digest") == document_digest
        ),
        None,
    )
    if document is None:
        errors.append(f"document digest mismatch: {document_id}")
        return
    if document["status"] != "accepted":
        errors.append(f"document is not accepted: {document_id}")
    if document["normative"] is not expected_normative:
        if expected_normative:
            errors.append(f"document is not normative: {document_id}")
        else:
            errors.append(f"document must be non-normative: {document_id}")
    if document["document_type"] != expected_document_type:
        errors.append(f"document type mismatch: {document_id}")
    if identifier_field is not None:
        identifier = reference.get(identifier_field)
        document_text = document.get("text")
        if not isinstance(identifier, str) or not re.search(
            rf"(?<![\w-]){re.escape(identifier)}(?![\w-])",
            document_text if isinstance(document_text, str) else "",
        ):
            errors.append(f"unknown {identifier_field}: {identifier}")


def _validate_registration_references(registration: Mapping[str, Any], root: Path) -> list[str]:
    errors: list[str] = []
    documents = _document_index(root)

    def report_unique_references(value: Any, field: str, label: str) -> None:
        if not isinstance(value, list):
            return
        seen: set[str] = set()
        for reference in value:
            if not isinstance(reference, Mapping):
                continue
            identifier = reference.get(field)
            if not isinstance(identifier, str):
                continue
            if identifier in seen:
                errors.append(f"duplicate {label}: {identifier}")
            seen.add(identifier)

    report_unique_references(
        registration.get("contract_references"), "document_id", "contract reference"
    )
    report_unique_references(registration.get("metric_references"), "metric_id", "metric_id")
    report_unique_references(registration.get("estimand_references"), "estimand_id", "estimand_id")
    report_unique_references(
        registration.get("analysis_procedure_references"),
        "analysis_procedure_id",
        "analysis_procedure_id",
    )

    for reference in (
        registration.get("contract_references", [])
        if isinstance(registration.get("contract_references"), list)
        else []
    ):
        if isinstance(reference, Mapping):
            _validate_document_reference(
                reference,
                documents,
                errors,
                expected_document_type="contract",
                expected_normative=True,
            )
    for reference in (
        registration.get("metric_references", [])
        if isinstance(registration.get("metric_references"), list)
        else []
    ):
        if isinstance(reference, Mapping):
            if reference.get("document_id") != "evaluation-metrics":
                errors.append("metric_references must reference evaluation-metrics")
            _validate_document_reference(
                reference,
                documents,
                errors,
                expected_document_type="contract",
                expected_normative=True,
                identifier_field="metric_id",
            )
    for reference in (
        registration.get("estimand_references", [])
        if isinstance(registration.get("estimand_references"), list)
        else []
    ):
        if isinstance(reference, Mapping):
            if reference.get("document_id") != "evaluation-statistical-analysis":
                errors.append("estimand_references must reference evaluation-statistical-analysis")
            _validate_document_reference(
                reference,
                documents,
                errors,
                expected_document_type="contract",
                expected_normative=True,
                identifier_field="estimand_id",
            )
    for reference in (
        registration.get("analysis_procedure_references", [])
        if isinstance(registration.get("analysis_procedure_references"), list)
        else []
    ):
        if isinstance(reference, Mapping):
            if reference.get("document_id") != "evaluation-statistical-analysis":
                errors.append(
                    "analysis_procedure_references must reference evaluation-statistical-analysis"
                )
            _validate_document_reference(
                reference,
                documents,
                errors,
                expected_document_type="contract",
                expected_normative=True,
                identifier_field="analysis_procedure_id",
            )
    return errors


def _validate_search_execution_references(
    specification: Mapping[str, Any], root: Path
) -> list[str]:
    errors: list[str] = []
    documents = _document_index(root)
    reference = specification.get("research_reference")
    if isinstance(reference, Mapping):
        if reference.get("document_id") != "roadmap-research-strategy-and-experiments":
            errors.append(
                "research_reference must reference roadmap-research-strategy-and-experiments"
            )
        _validate_document_reference(
            reference,
            documents,
            errors,
            expected_document_type="roadmap",
            expected_normative=False,
        )
    return errors


def _resolve_fixture_path(root: Path, value: Any, expected_root: str) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise RegistrationValidationError("fixture repository path is invalid")
    normalized = value.replace("\\", "/")
    parts = normalized.split("/")
    if (
        normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized)
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise RegistrationValidationError("fixture repository path is invalid")
    candidate = (root / Path(*parts)).resolve()
    allowed_root = (root / expected_root).resolve()
    try:
        candidate.relative_to(allowed_root)
    except ValueError as exc:
        raise RegistrationValidationError(
            "fixture repository path escapes its fixture root"
        ) from exc
    if not candidate.is_file():
        raise RegistrationValidationError(f"fixture repository path does not exist: {normalized}")
    return candidate


def _validate_fixture_file(
    root: Path, entry: Mapping[str, Any], expected_root: str, label: str
) -> None:
    fixture_path = _resolve_fixture_path(root, entry.get("repository_path"), expected_root)
    expected_digest = entry.get("content_digest")
    actual_digest = "sha256:" + hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    if expected_digest != actual_digest:
        raise RegistrationValidationError(f"{label} content digest mismatch")


def _git_blob_bytes(root: Path, source_commit: str, repository_path: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "show", f"{source_commit}:{repository_path}"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RegistrationValidationError(
            f"source commit does not contain {repository_path}"
        ) from exc
    return result.stdout


def _validate_repository_file_manifest(
    root: Path,
    entries: Any,
    label: str,
    *,
    source_commit: str | None = None,
) -> str:
    if not isinstance(entries, list) or not entries:
        raise RegistrationValidationError(f"{label} source manifest is invalid")
    seen: set[str] = set()
    normalized_entries: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise RegistrationValidationError(f"{label} source manifest entry is invalid")
        repository_path = entry.get("repository_path")
        content_digest = entry.get("content_digest")
        if (
            not isinstance(repository_path, str)
            or not repository_path
            or repository_path in seen
            or not isinstance(content_digest, str)
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", content_digest)
        ):
            raise RegistrationValidationError(f"{label} source manifest entry is invalid")
        seen.add(repository_path)
        normalized = repository_path.replace("\\", "/")
        parts = normalized.split("/")
        if (
            normalized.startswith("/")
            or re.match(r"^[A-Za-z]:", normalized)
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise RegistrationValidationError(f"{label} source manifest path is invalid")
        path = (root / Path(*parts)).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError as exc:
            raise RegistrationValidationError(
                f"{label} source manifest path escapes repository"
            ) from exc
        if source_commit is None:
            if not path.is_file():
                raise RegistrationValidationError(
                    f"{label} source manifest file does not exist: {repository_path}"
                )
            content = path.read_bytes()
        else:
            content = _git_blob_bytes(root, source_commit, normalized)
        actual = "sha256:" + hashlib.sha256(content).hexdigest()
        if actual != content_digest:
            raise RegistrationValidationError(f"{label} source digest mismatch")
        normalized_entries.append({"repository_path": normalized, "content_digest": content_digest})
    if normalized_entries != sorted(normalized_entries, key=lambda entry: entry["repository_path"]):
        raise RegistrationValidationError(f"{label} source manifest is not canonical")
    return manifest_digest(normalized_entries)


def _validate_implementation_provenance(value: Mapping[str, Any], root: Path) -> None:
    source_commit = value.get("source_commit")
    if source_commit != _TASK21_SOURCE_COMMIT:
        raise RegistrationValidationError(
            "implementation source_commit is not the validated Task-20 commit"
        )
    if not isinstance(source_commit, str):
        raise RegistrationValidationError("implementation source_commit is invalid")
    _validate_repository_file_manifest(
        root, value.get("source_manifest"), "implementation", source_commit=source_commit
    )
    components = value.get("components")
    if not isinstance(components, Mapping):
        raise RegistrationValidationError("implementation components are invalid")
    policy = components.get("policy")
    safety = components.get("fallback_and_safety")
    if not isinstance(policy, Mapping) or not isinstance(safety, Mapping):
        raise RegistrationValidationError("implementation component bindings are invalid")
    policy_entries = policy.get("source_manifest")
    safety_entries = safety.get("source_manifest")
    policy_digest = _validate_repository_file_manifest(
        root, policy_entries, "policy", source_commit=source_commit
    )
    safety_digest = _validate_repository_file_manifest(
        root, safety_entries, "fallback and safety", source_commit=source_commit
    )
    component_entries = [policy_entries, safety_entries]
    flattened = [
        entry for entries in component_entries if isinstance(entries, list) for entry in entries
    ]
    if value.get("source_manifest") != sorted(
        flattened, key=lambda entry: entry["repository_path"]
    ):
        raise RegistrationValidationError(
            "implementation source manifest does not match bound component manifests"
        )
    if policy_digest != policy.get("digest"):
        raise RegistrationValidationError("policy digest does not match its source manifest")
    if safety_digest != safety.get("digest"):
        raise RegistrationValidationError(
            "fallback and safety digest does not match its source manifest"
        )
    package_digest = _validate_repository_file_manifest(
        root,
        value.get("package_or_wheel_source_manifest"),
        "package",
        source_commit=source_commit,
    )
    if package_digest != value.get("package_or_wheel_digest"):
        raise RegistrationValidationError("package digest does not match its source manifest")
    for field, repository_path in (
        ("decision_record_schema_digest", "schemas/records/decision-record-v2.schema.json"),
        (
            "canonicalizer_digest",
            "packages/battlebelief-core/src/battlebelief_core/canonicalization.py",
        ),
    ):
        actual = (
            "sha256:"
            + hashlib.sha256(_git_blob_bytes(root, source_commit, repository_path)).hexdigest()
        )
        if value.get(field) != actual:
            raise RegistrationValidationError(f"{field} does not match the repository artifact")
    contract_set = value.get("contract_set")
    if not isinstance(contract_set, list) or not contract_set:
        raise RegistrationValidationError("contract_set is invalid")
    document_ids = [
        entry["document_id"]
        for entry in contract_set
        if isinstance(entry, Mapping) and isinstance(entry.get("document_id"), str)
    ]
    if len(set(document_ids)) != len(document_ids) or document_ids != sorted(document_ids):
        raise RegistrationValidationError("contract_set must be sorted and unique")
    contract_digest = manifest_digest(contract_set)
    if contract_digest != value.get("contract_set_digest"):
        raise RegistrationValidationError("contract_set digest mismatch")
    reference_errors = _validate_registration_references(
        {
            "contract_references": contract_set,
            "metric_references": [],
            "estimand_references": [],
            "analysis_procedure_references": [],
        },
        root,
    )
    if reference_errors:
        raise RegistrationValidationError(reference_errors[0])


def _validate_base_matchups(fixture: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    team_fixture_ids = {
        entry.get("fixture_id")
        for entry in fixture.get("team_fixtures", [])
        if isinstance(entry, Mapping)
    }
    policy_fixture_ids = {
        entry.get("fixture_id")
        for entry in fixture.get("opponent_policy_fixtures", [])
        if isinstance(entry, Mapping)
    }
    base_matchups = fixture.get("base_matchups")
    if not isinstance(base_matchups, list) or not base_matchups:
        raise RegistrationValidationError("base matchups are invalid")
    base_matchup_by_id: dict[str, Mapping[str, Any]] = {}
    for base_matchup in base_matchups:
        if not isinstance(base_matchup, Mapping):
            raise RegistrationValidationError("base matchup definition is invalid")
        base_id = base_matchup.get("base_matchup_id")
        hero_team = base_matchup.get("hero_team_fixture_id")
        opponent_team = base_matchup.get("opponent_team_fixture_id")
        opponent_archetype = base_matchup.get("opponent_archetype")
        opponent_policy = base_matchup.get("opponent_policy_fixture_id")
        schedule_block = base_matchup.get("schedule_block")
        if (
            not isinstance(base_id, str)
            or not isinstance(hero_team, str)
            or not isinstance(opponent_team, str)
            or not isinstance(opponent_archetype, str)
            or not isinstance(opponent_policy, str)
            or not isinstance(schedule_block, str)
            or hero_team not in team_fixture_ids
            or opponent_team not in team_fixture_ids
            or opponent_policy not in policy_fixture_ids
        ):
            raise RegistrationValidationError("base matchup references an unknown fixture")
        try:
            expected_base_id = BaseMatchupKey(
                hero_team=hero_team,
                opponent_team=opponent_team,
                opponent_archetype=opponent_archetype,
                opponent_policy_checkpoint=opponent_policy,
                schedule_block=schedule_block,
            ).base_matchup_id
        except (KeyError, TypeError, ValueError) as exc:
            raise RegistrationValidationError("base matchup definition is invalid") from exc
        if base_id != expected_base_id or base_id in base_matchup_by_id:
            raise RegistrationValidationError("base matchup identity is not canonical")
        base_matchup_by_id[base_id] = base_matchup
    return base_matchup_by_id


def validate_synthetic_fixture_manifest(fixture: Mapping[str, Any], root: Path) -> None:
    """Validate fixture identities and content without opening evaluation pools."""

    fixture_ids: set[str] = set()
    for field, expected_root, label in (
        ("team_fixtures", "tests/fixtures/teams", "team fixture"),
        ("opponent_policy_fixtures", "tests/fixtures/policies", "policy fixture"),
    ):
        entries = fixture.get(field)
        if not isinstance(entries, list):
            raise RegistrationValidationError(f"{label} list is invalid")
        for entry in entries:
            if not isinstance(entry, Mapping) or not isinstance(entry.get("fixture_id"), str):
                raise RegistrationValidationError(f"{label} identity is invalid")
            fixture_id = entry["fixture_id"]
            if fixture_id in fixture_ids:
                raise RegistrationValidationError(f"duplicate fixture_id: {fixture_id}")
            fixture_ids.add(fixture_id)
            _validate_fixture_file(root, entry, expected_root, label)
            if label == "policy fixture":
                policy = load_json_strict(
                    _resolve_fixture_path(root, entry.get("repository_path"), expected_root)
                )
                if not isinstance(policy, Mapping):
                    raise RegistrationValidationError("policy fixture must contain an object")

    base_matchup_by_id = (
        _validate_base_matchups(fixture) if fixture.get("schema_version") == 3 else {}
    )

    ruleset = fixture.get("ruleset_snapshot")
    if not isinstance(ruleset, Mapping):
        raise RegistrationValidationError("ruleset snapshot is invalid")
    ruleset_path = _resolve_fixture_path(
        root, ruleset.get("repository_path"), "tests/fixtures/rulesets"
    )
    actual_digest = "sha256:" + hashlib.sha256(ruleset_path.read_bytes()).hexdigest()
    if ruleset.get("content_digest") != actual_digest:
        raise RegistrationValidationError("ruleset snapshot content digest mismatch")
    ruleset_value = load_json_strict(ruleset_path)
    if not isinstance(ruleset_value, Mapping):
        raise RegistrationValidationError("ruleset snapshot artifact must contain an object")
    if ruleset_value.get("format_id") != ruleset.get("format_id") or ruleset_value.get(
        "ruleset_digest"
    ) != ruleset.get("ruleset_digest"):
        raise RegistrationValidationError("ruleset snapshot identity mismatch")
    if fixture.get("schema_version") == 3:
        identity = {
            "format_id": ruleset.get("format_id"),
            "ruleset_id": ruleset.get("ruleset_id"),
            "ruleset_version": ruleset.get("ruleset_version"),
        }
        if ruleset_value.get("ruleset_id") != ruleset.get("ruleset_id") or ruleset_value.get(
            "ruleset_version"
        ) != ruleset.get("ruleset_version"):
            raise RegistrationValidationError("ruleset snapshot versioned identity mismatch")
        if ruleset.get("ruleset_digest") != manifest_digest(identity):
            raise RegistrationValidationError("ruleset snapshot inner digest mismatch")
        rows = fixture.get("schedule_rows")
        if not isinstance(rows, list):
            raise RegistrationValidationError("schedule rows are invalid")
        try:
            if not all(isinstance(row, Mapping) for row in rows):
                raise RegistrationValidationError("schedule row is not an object")
            for row in rows:
                base_matchup = base_matchup_by_id.get(row.get("base_matchup_id"))
                if base_matchup is None or row.get("schedule_block") != base_matchup.get(
                    "schedule_block"
                ):
                    raise RegistrationValidationError(
                        "schedule row references an unknown base matchup"
                    )
            typed_rows = tuple(
                ScheduleRow(
                    row_id=row["row_id"],
                    base_matchup_id=row["base_matchup_id"],
                    side_assignment=SideAssignment(row["side_assignment"]),
                    schedule_block=row["schedule_block"],
                    seed_family=SeedFamily(**row["seed_family"]),
                    repetition_index=row["repetition_index"],
                )
                for row in rows
            )
            Schedule(
                rows=typed_rows,
                digest=manifest_digest([row.to_dict() for row in typed_rows]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RegistrationValidationError(f"schedule row is not canonical: {exc}") from exc
        if fixture.get("seed_family") is not None:
            raise RegistrationValidationError("v3 fixture must bind SeedFamily per schedule row")
        budget = fixture.get("budget_profile")
        if not isinstance(budget, Mapping):
            raise RegistrationValidationError("budget profile is not canonical")
        try:
            BudgetProfile(
                profile_id=budget["profile_id"],
                mode=BudgetMode(budget["mode"]),
                deployment=BudgetView(**budget["deployment"]),
                mechanism=BudgetView(**budget["mechanism"]),
                calibration_spec_digest=budget["calibration_spec_digest"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RegistrationValidationError(f"budget profile is not canonical: {exc}") from exc


def validate_calibration_state_manifest(value: Mapping[str, Any]) -> None:
    """Validate the public, outcome-blind M1.5 calibration state definition."""

    construction = value.get("construction")
    if construction != {
        "algorithm_id": "public-observation-grid-v1",
        "field_order": ["turn_index", "active_slot_count", "request_kind", "weather_class"],
        "enumeration_order": "lexicographic_over_declared_domains",
        "public_fields_only": True,
        "declared_domains": {
            "turn_index": [0, 1, 2],
            "active_slot_count": [1, 2],
            "request_kind": ["move", "switch"],
            "weather_class": ["none", "sun"],
        },
        "state_set": "explicit_public_states_v1",
    }:
        raise RegistrationValidationError("calibration state construction is not frozen")
    states = value.get("states")
    if not isinstance(states, list) or not states:
        raise RegistrationValidationError("calibration state list is invalid")
    seen: set[str] = set()
    for state in states:
        if not isinstance(state, Mapping):
            raise RegistrationValidationError("calibration state is invalid")
        state_id = state.get("state_id")
        public_state = state.get("public_state")
        if (
            not isinstance(state_id, str)
            or state_id in seen
            or not isinstance(public_state, Mapping)
            or state_id != manifest_digest(dict(public_state))
        ):
            raise RegistrationValidationError("calibration state identity is not canonical")
        seen.add(state_id)


def validate_repository_artifacts(root: Path | None = None) -> list[str]:
    """Validate present registration artifacts; absent future directories are no-op."""

    repository_root = root or Path(__file__).resolve().parents[4]
    registrations = repository_root / "registrations"
    if not registrations.exists():
        return []

    errors: list[str] = []
    artifacts: list[tuple[Path, Mapping[str, Any], str]] = []
    by_digest: dict[str, tuple[Path, Mapping[str, Any], str]] = {}
    for path in sorted(registrations.rglob("*.json")):
        relative = path.relative_to(repository_root)
        try:
            value = load_json_strict(path)
            if not isinstance(value, Mapping):
                raise RegistrationValidationError("artifact root must be an object")
            schema_info = _schema_for_artifact(path, value, repository_root)
            if schema_info is None or not schema_info[0].exists():
                raise RegistrationValidationError("artifact kind has no known schema")
            schema_path, kind = schema_info
            schema = load_json_strict(schema_path)
            schema_errors = list(
                Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value)
            )
            errors.extend(f"{relative}: {schema_issue_summary(issue)}" for issue in schema_errors)
            if schema_errors:
                continue
            if kind == "registration":
                validate_registration_semantics(value, repository_root)
            elif kind == "calibration_state_manifest":
                validate_calibration_state_manifest(value)
            elif kind == "calibration_spec":
                validate_calibration_spec(value)
            elif kind == "search_execution":
                errors.extend(
                    f"{relative}: {error}"
                    for error in _validate_search_execution_references(value, repository_root)
                )
            elif kind == "synthetic_acceptance":
                validate_synthetic_fixture_manifest(value, repository_root)
            elif kind == "measurement_run_result":
                errors.extend(
                    f"{relative}: {error}"
                    for error in validate_measurement_run_result_document(value)
                )
            artifacts.append((path, value, kind))
            by_digest[manifest_digest(dict(value))] = (path, value, kind)
        except RegistrationValidationError as exc:
            errors.append(f"{relative}: {exc}")

    registrations_by_id: dict[str, list[tuple[Path, Mapping[str, Any], str]]] = {}
    binding_ids: dict[tuple[str, str, int], Path] = {}
    for path, value, kind in artifacts:
        if kind in {"implementation", "run"} and isinstance(value.get("binding_id"), str):
            binding_id = value["binding_id"]
            version = value.get("artifact_version")
            key = (kind, binding_id, version) if isinstance(version, int) else None
            if key is None:
                continue
            if key in binding_ids:
                errors.append(
                    f"{path.relative_to(repository_root)}: duplicate binding_id identity: "
                    f"{kind}/{binding_id}/v{version}"
                )
            else:
                binding_ids[key] = path
        if kind != "registration" or not isinstance(value.get("registration_id"), str):
            continue
        registration_id = value["registration_id"]
        candidates = registrations_by_id.setdefault(registration_id, [])
        version = value.get("artifact_version")
        if any(candidate[1].get("artifact_version") == version for candidate in candidates):
            errors.append(
                f"{path.relative_to(repository_root)}: duplicate registration_id: {registration_id}"
            )
            continue
        candidates.append((path, value, kind))

    def artifact_identity(value: Mapping[str, Any], kind: str) -> str | None:
        field_by_kind = {
            "registration": "registration_id",
            "implementation": "binding_id",
            "run": "binding_id",
            "calibration_spec": "spec_id",
            "calibration_evidence": "evidence_id",
            "search_execution": "spec_id",
            "synthetic_acceptance": "manifest_id",
            "calibration_state_manifest": "manifest_id",
        }
        field = field_by_kind.get(kind)
        identifier = value.get(field) if field is not None else None
        return identifier if isinstance(identifier, str) else None

    supersession: dict[str, str] = {}
    supersession_children: dict[str, list[str]] = {}
    for path, value, kind in artifacts:
        digest = manifest_digest(dict(value))
        version = value.get("artifact_version")
        predecessor = value.get("supersedes_digest")
        if not isinstance(version, int) or not isinstance(predecessor, (str, type(None))):
            continue
        if predecessor is None:
            if version != 1:
                errors.append(
                    f"{path.relative_to(repository_root)}: first artifact version must be 1"
                )
            continue
        if predecessor == digest:
            errors.append(f"{path.relative_to(repository_root)}: artifact supersedes itself")
            continue
        previous = by_digest.get(predecessor)
        if previous is None:
            errors.append(f"{path.relative_to(repository_root)}: superseded artifact is unresolved")
            continue
        if previous[2] != kind or artifact_identity(previous[1], previous[2]) != artifact_identity(
            value, kind
        ):
            errors.append(
                f"{path.relative_to(repository_root)}: superseded artifact identity mismatch"
            )
        previous_version = previous[1].get("artifact_version")
        if not isinstance(previous_version, int) or previous_version >= version:
            errors.append(f"{path.relative_to(repository_root)}: artifact version does not advance")
        supersession[digest] = predecessor
        children = supersession_children.setdefault(predecessor, [])
        children.append(digest)
        if len(children) > 1:
            errors.append(
                f"{path.relative_to(repository_root)}: superseded artifact has multiple successors"
            )
    settled: set[str] = set()
    for digest in supersession:
        visited: set[str] = set()
        current: str | None = digest
        while current is not None and current in supersession and current not in settled:
            if current in visited:
                cycle_path = by_digest.get(current)
                location = (
                    cycle_path[0].relative_to(repository_root)
                    if cycle_path is not None
                    else current
                )
                errors.append(f"{location}: artifact supersession cycle detected")
                break
            visited.add(current)
            current = supersession[current]
        settled.update(visited)

    for path, value, kind in artifacts:
        relative = path.relative_to(repository_root)
        if kind == "registration":
            for arm in value.get("arms", []):
                if not isinstance(arm, Mapping):
                    continue
                execution_digest = arm.get("execution_spec_digest")
                if execution_digest is None:
                    continue
                execution = (
                    by_digest.get(execution_digest) if isinstance(execution_digest, str) else None
                )
                if execution is None or execution[2] != "search_execution":
                    errors.append(f"{relative}: execution specification digest is unresolved")
                elif execution[1].get("arm_id") != arm.get("arm_id"):
                    errors.append(f"{relative}: execution specification arm mismatch")
                elif execution[1].get("schema_version") == 3:
                    parameter = execution[1].get("budget_parameter")
                    calibration_digest = (
                        parameter.get("calibration_spec_digest")
                        if isinstance(parameter, Mapping)
                        else None
                    )
                    calibration = (
                        by_digest.get(calibration_digest)
                        if isinstance(calibration_digest, str)
                        else None
                    )
                    if calibration is None or calibration[2] != "calibration_spec":
                        errors.append(
                            f"{relative}: execution specification calibration digest is unresolved"
                        )
            budget_profiles = value.get("budget_profiles", {})
            if isinstance(budget_profiles, Mapping):
                for profile_name, profile in budget_profiles.items():
                    if not isinstance(profile, Mapping):
                        continue
                    calibration_digest = profile.get("calibration_spec_digest")
                    if calibration_digest is None:
                        continue
                    calibration = (
                        by_digest.get(calibration_digest)
                        if isinstance(calibration_digest, str)
                        else None
                    )
                    if calibration is None or calibration[2] != "calibration_spec":
                        errors.append(
                            f"{relative}: budget profile {profile_name} calibration digest is unresolved"
                        )
            errors.extend(
                f"{relative}: {error}"
                for error in _validate_registration_references(value, repository_root)
            )
            continue
        if kind == "calibration_spec" and value.get("schema_version") == 3:
            state_digest = value.get("calibration_state_manifest_digest")
            state_entry = by_digest.get(state_digest) if isinstance(state_digest, str) else None
            if (
                state_entry is None
                or state_entry[2] != "calibration_state_manifest"
                or state_entry[1].get("rule_id") != value.get("calibration_state_rule_id")
            ):
                errors.append(f"{relative}: calibration state manifest digest is unresolved")
        if kind not in {"implementation", "run"}:
            if kind != "calibration_evidence":
                continue
            spec_digest = value.get("calibration_spec_digest")
            spec = by_digest.get(spec_digest) if isinstance(spec_digest, str) else None
            if spec is None or spec[2] != "calibration_spec":
                errors.append(f"{relative}: calibration specification digest is unresolved")
                continue
            specification = spec[1]
            try:
                validate_calibration_evidence(value, specification)
            except RegistrationValidationError as exc:
                errors.append(f"{relative}: {exc}")
            continue
        registration_id = value.get("registration_id")
        registration_digest = value.get("registration_digest")
        registration_candidates = (
            registrations_by_id.get(registration_id, []) if isinstance(registration_id, str) else []
        )
        if not registration_candidates:
            errors.append(f"{relative}: binding references unknown registration")
            continue
        registration_entry = next(
            (
                candidate
                for candidate in registration_candidates
                if isinstance(registration_digest, str)
                and manifest_digest(dict(candidate[1])) == registration_digest
            ),
            None,
        )
        if registration_entry is None:
            errors.append(f"{relative}: registration digest mismatch")
            typed_candidates = [
                candidate
                for candidate in registration_candidates
                if isinstance(candidate[1].get("artifact_version"), int)
            ]
            if not typed_candidates:
                errors.append(f"{relative}: no valid registration fallback available")
                continue
            registration_entry = max(
                typed_candidates,
                key=lambda candidate: candidate[1]["artifact_version"],
            )
        _, registration, _ = registration_entry
        if kind == "implementation":
            if value.get("schema_version") == 3:
                try:
                    _validate_implementation_provenance(value, repository_root)
                except RegistrationValidationError as exc:
                    errors.append(f"{relative}: {exc}")
            arm_ids = {
                arm.get("arm_id")
                for arm in registration.get("arms", [])
                if isinstance(arm, Mapping)
            }
            if value.get("arm_id") not in arm_ids:
                errors.append(f"{relative}: binding references unknown arm")
            arm = next(
                (
                    candidate
                    for candidate in registration.get("arms", [])
                    if isinstance(candidate, Mapping)
                    and candidate.get("arm_id") == value.get("arm_id")
                ),
                None,
            )
            components = value.get("components")
            if isinstance(arm, Mapping) and isinstance(components, Mapping):
                search_component = components.get("search_algorithm")
                search_state = (
                    search_component.get("state") if isinstance(search_component, Mapping) else None
                )
                has_search = arm.get("search_algorithm_id") is not None
                if has_search and search_state == "not_applicable":
                    errors.append(
                        f"{relative}: search arm cannot mark search_algorithm not_applicable"
                    )
                if not has_search and search_state != "not_applicable":
                    errors.append(f"{relative}: heuristic arm cannot bind search_algorithm")
                if arm.get("policy_kind") == "heuristic":
                    for component_name in ("policy", "fallback_and_safety"):
                        component = components.get(component_name)
                        if not isinstance(component, Mapping) or component.get("state") != "bound":
                            errors.append(
                                f"{relative}: heuristic arm requires bound {component_name}"
                            )
                    for component_name in ("engine", "prior", "belief", "model"):
                        component = components.get(component_name)
                        if (
                            isinstance(component, Mapping)
                            and component.get("state") != "not_applicable"
                        ):
                            errors.append(f"{relative}: heuristic arm cannot bind {component_name}")
        else:
            if value.get("run_purpose") == "evaluation":
                errors.append(
                    f"{relative}: evaluation run bindings are not enabled until pool artifacts exist"
                )
                continue
            implementation_digest = value.get("implementation_binding_digest")
            implementation = (
                by_digest.get(implementation_digest)
                if isinstance(implementation_digest, str)
                else None
            )
            if implementation is None or implementation[2] != "implementation":
                errors.append(f"{relative}: implementation binding digest is unresolved")
            elif (
                implementation[1].get("registration_id") != registration_id
                or implementation[1].get("registration_digest") != registration_digest
            ):
                errors.append(f"{relative}: implementation binding belongs to another registration")
            calibration_evidence_digest = value.get("calibration_evidence_digest")
            if calibration_evidence_digest is not None:
                calibration_evidence = (
                    by_digest.get(calibration_evidence_digest)
                    if isinstance(calibration_evidence_digest, str)
                    else None
                )
                if (
                    calibration_evidence is None
                    or calibration_evidence[2] != "calibration_evidence"
                ):
                    errors.append(f"{relative}: calibration evidence digest is unresolved")
            fixture_digest = value.get("synthetic_fixture_manifest_digest")
            if value.get("run_purpose") == "synthetic_acceptance":
                fixture_entry = (
                    by_digest.get(fixture_digest) if isinstance(fixture_digest, str) else None
                )
                if fixture_entry is None:
                    errors.append(f"{relative}: synthetic fixture digest is unresolved")
                else:
                    _, fixture_value, fixture_kind = fixture_entry
                    if fixture_kind != "synthetic_acceptance":
                        errors.append(f"{relative}: synthetic fixture digest is unresolved")
                        continue
                    rows = fixture_value.get("schedule_rows")
                    seed_component = (
                        [row.get("seed_family") for row in rows]
                        if fixture_value.get("schema_version") == 3 and isinstance(rows, list)
                        else fixture_value.get("seed_family")
                    )
                    expected_fixture_fields = {
                        "schedule_digest": rows,
                        "seed_family_digest": seed_component,
                        "budget_profile_digest": fixture_value.get("budget_profile"),
                        "runtime_environment_digest": fixture_value.get("runtime_environment"),
                        "ruleset_digest": fixture_value.get("ruleset_snapshot"),
                    }
                    for field, fixture_component in expected_fixture_fields.items():
                        if value.get(field) != manifest_digest(fixture_component):
                            errors.append(f"{relative}: synthetic fixture {field} mismatch")
    return sorted(errors)


def artifact_digest(value: Mapping[str, Any]) -> str:
    """Expose the shared digest operation for later binding validators."""

    return manifest_digest(dict(value))
