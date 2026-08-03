"""Strict loading and semantic validation for M1.5 registrations."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Mapping
from itertools import pairwise
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from battlebelief_core.canonicalization import manifest_digest


class RegistrationValidationError(ValueError):
    """Raised when a registration violates the strict M1.5 contract."""


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
    for field in ("measurement_profile_id", "selection_measurement_id", "runtime_limit_ms"):
        if evidence.get(field) != spec.get(field):
            raise RegistrationValidationError(f"calibration {field} mismatch")
    grid = spec.get("ordered_work_grid")
    rows = evidence.get("runtime_measurements")
    required = spec.get("required_measurement_ids")
    allowed = spec.get("allowed_runtime_measurements")
    forbidden = spec.get("forbidden_quality_measurements")
    selection_id = spec.get("selection_measurement_id")
    limit = spec.get("runtime_limit_ms")
    if not isinstance(grid, list) or not isinstance(rows, list):
        raise RegistrationValidationError("calibration measurements are invalid")
    if not all(isinstance(value, Mapping) for value in rows):
        raise RegistrationValidationError("calibration measurement rows are invalid")
    work_values = [row.get("work_value") for row in rows]
    if work_values != grid:
        raise RegistrationValidationError("calibration measurements do not cover the work grid")
    if not isinstance(required, list) or not isinstance(allowed, list):
        raise RegistrationValidationError("calibration measurement lists are invalid")
    if not isinstance(limit, (int, float)) or isinstance(limit, bool):
        raise RegistrationValidationError("calibration runtime limit is invalid")
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
            if status == "completed" and selected > limit:
                raise RegistrationValidationError("completed calibration row is over_limit")
            if status == "over_limit" and selected <= limit:
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
    rule_registry: dict[str, set[str]] = (
        _registration_rule_registry(root) if root is not None else {}
    )
    metric_roles: dict[str, set[str]] = {}
    metric_directions: dict[str, str] = {}
    statistical_registry: dict[str, set[str]] = {}
    if root is not None:
        metric_registry = _metric_registry(root)
        statistical_registry = _statistical_registry(root)
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
            for field in ("tie_break_rule_id",):
                if comparison.get(field) not in rule_registry.get(field, set()):
                    raise RegistrationValidationError(f"unknown {field}: {comparison.get(field)}")

    budget_profiles = registration.get("budget_profiles")
    if isinstance(budget_profiles, Mapping):
        for profile_name, profile in budget_profiles.items():
            if not isinstance(profile, Mapping):
                raise RegistrationValidationError(
                    f"budget profile {profile_name} must be an object"
                )
            mode = profile.get("budget_mode")
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
                for field in ("stop_rule_id", "pivot_rule_id"):
                    if gate.get(field) not in rule_registry.get(field, set()):
                        raise RegistrationValidationError(f"unknown {field}: {gate.get(field)}")


_SCHEMA_BY_KIND = {
    "implementation": "evaluation-arm-binding.schema.json",
    "run": "evaluation-run-binding.schema.json",
    "synthetic_acceptance": "synthetic-fixture-manifest.schema.json",
}


def _schema_for_artifact(
    path: Path, value: Mapping[str, Any], repository_root: Path
) -> tuple[Path, str] | None:
    if path.name == "registration.json" or "registration_status" in value:
        return (
            repository_root / "schemas/manifests/experiment-registration.schema.json",
            "registration",
        )
    kind = value.get("binding_kind")
    if isinstance(kind, str) and kind in _SCHEMA_BY_KIND:
        return (
            repository_root / "schemas/manifests" / _SCHEMA_BY_KIND[kind],
            kind,
        )
    if value.get("purpose") == "synthetic_acceptance":
        return (
            repository_root / "schemas/manifests/synthetic-fixture-manifest.schema.json",
            "synthetic_acceptance",
        )
    if "evidence_id" in value:
        return (
            repository_root / "schemas/manifests/budget-calibration-evidence.schema.json",
            "calibration_evidence",
        )
    if "reference_environment_specification" in value:
        return (
            repository_root / "schemas/manifests/budget-calibration-spec.schema.json",
            "calibration_spec",
        )
    if {"spec_id", "world_sampling", "lookahead"}.issubset(value):
        return (
            repository_root / "schemas/manifests/search-execution-spec.schema.json",
            "search_execution",
        )
    return None


def _document_index(root: Path) -> dict[tuple[str, int], list[dict[str, object]]]:
    result: dict[tuple[str, int], list[dict[str, object]]] = {}
    for path in sorted((root / "docs").rglob("*.md")):
        if "archive" in path.relative_to(root / "docs").parts:
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
            "contracts/snapshots" not in str(record["path"]).replace("\\", "/"),
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
        _validate_document_reference(
            reference,
            documents,
            errors,
            expected_document_type="roadmap",
            expected_normative=False,
        )
    return errors


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
            elif kind == "calibration_spec":
                validate_calibration_spec(value)
            elif kind == "search_execution":
                errors.extend(
                    f"{relative}: {error}"
                    for error in _validate_search_execution_references(value, repository_root)
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
                fixture = by_digest.get(fixture_digest) if isinstance(fixture_digest, str) else None
                if fixture is None or fixture[2] != "synthetic_acceptance":
                    errors.append(f"{relative}: synthetic fixture digest is unresolved")
                else:
                    fixture_value = fixture[1]
                    expected_fixture_fields = {
                        "schedule_digest": fixture_value.get("schedule_rows"),
                        "seed_family_digest": fixture_value.get("seed_family"),
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
