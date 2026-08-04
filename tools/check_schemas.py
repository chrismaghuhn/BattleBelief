from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Allow `python tools/check_schemas.py` without -m
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from jsonschema import Draft202012Validator, FormatChecker  # noqa: E402

from battlebelief_core.domain.records.decision_record import (  # noqa: E402
    RunScopePayload,
    derive_battle_id_digest,
    derive_run_scope_digest,
    validate_decision_record_envelope,
    validate_measurement_run_context,
)
from battlebelief_lab.evaluation.measurement_runner import (  # noqa: E402
    validate_measurement_run_result_document,
)
from battlebelief_lab.registration_validation import (  # noqa: E402
    RegistrationValidationError,
    _schema_for_artifact,
    _validate_search_execution_references,
    load_json_strict,
    schema_issue_summary,
    validate_calibration_spec,
    validate_registration_semantics,
    validate_repository_artifacts,
    validate_synthetic_fixture_manifest,
)
from tools.canonicalize_manifest import canonicalize, manifest_digest  # noqa: E402

EXAMPLE_SCHEMA_MAP = {
    "dataset-manifest.example.json": "dataset-manifest.schema.json",
    "engine-capability.example.json": "engine-capability.schema.json",
    "evaluation-claim.example.json": "evaluation-claim.schema.json",
    "ruleset-snapshot.example.json": "ruleset-snapshot.schema.json",
    "search-contract.example.json": "search-contract.schema.json",
    "experiment-registration.example.json": "experiment-registration.schema.json",
    "evaluation-arm-binding.example.json": "evaluation-arm-binding.schema.json",
    "evaluation-run-binding.example.json": "evaluation-run-binding.schema.json",
    "budget-calibration-spec.example.json": "budget-calibration-spec.schema.json",
    "budget-calibration-evidence.example.json": "budget-calibration-evidence.schema.json",
    "search-execution-spec.example.json": "search-execution-spec.schema.json",
    "synthetic-fixture-manifest.example.json": "synthetic-fixture-manifest.schema.json",
    "decision-record.example.json": "decision-record.schema.json",
    "decision-record-payload.example.json": "decision-record-payload.schema.json",
    "decision-record-v2.example.json": "decision-record-v2.schema.json",
    "decision-record-payload-v2.example.json": "decision-record-payload-v2.schema.json",
    "measurement-run.example.json": "measurement-run.schema.json",
    "measurement-run-result.example.json": "measurement-run-result.schema.json",
}


def validate_decision_record_vector(
    vector: dict[str, Any], payload_schema: dict[str, Any]
) -> list[str]:
    """Validate one decision-record vector and its complete identity chain."""

    name = vector.get("name", "decision-record-vector")
    errors: list[str] = []
    payload = vector.get("value")
    if not isinstance(payload, dict):
        return [f"{name}: decision-record payload is not an object"]
    errors.extend(
        f"{name}: {schema_issue_summary(issue)}"
        for issue in Draft202012Validator(payload_schema).iter_errors(payload)
    )
    run_context = vector.get("run_context")
    if not isinstance(run_context, dict):
        return [*errors, f"{name}: measurement-run context is not an object"]
    errors.extend(f"{name}: {error}" for error in validate_measurement_run_context(run_context))
    if run_context.get("run_context_digest") != vector.get("run_context_digest"):
        errors.append(f"{name}: run_context digest is not bound to vector")
    if run_context.get("run_scope_digest") != vector.get("run_scope_digest"):
        errors.append(f"{name}: run_scope digest is not bound to run context")
    if run_context.get("battle_id_digest") != vector.get("battle_id_digest"):
        errors.append(f"{name}: battle ID digest is not bound to run context")
    if run_context.get("battle_ordinal") != vector.get("battle_ordinal"):
        errors.append(f"{name}: battle ordinal is not bound to run context")
    if payload.get("run_context_digest") != vector.get("run_context_digest"):
        errors.append(f"{name}: payload run_context digest is not bound to vector")
    if payload.get("battle_id_digest") != vector.get("battle_id_digest"):
        errors.append(f"{name}: payload battle ID digest is not bound to vector")
    envelope = {
        "record_id": vector.get("record_id"),
        "record_digest": vector.get("record_digest"),
        "payload": payload,
    }
    errors.extend(f"{name}: {error}" for error in validate_decision_record_envelope(envelope))
    try:
        scope = RunScopePayload(**vector["run_scope"])
        if derive_run_scope_digest(scope) != vector.get("run_scope_digest"):
            errors.append(f"{name}: run_scope_digest differs")
        if derive_battle_id_digest(
            vector["run_scope_digest"],
            scope.schedule_row_id,
            vector["battle_ordinal"],
        ) != vector.get("battle_id_digest"):
            errors.append(f"{name}: battle_id_digest differs")
    except (KeyError, TypeError, ValueError) as error:
        errors.append(f"{name}: run-scope identity is invalid: {error}")
    try:
        if canonicalize(payload) != vector["canonical_utf8"].encode("utf-8"):
            errors.append(f"{name}: canonical bytes differ")
        if manifest_digest(payload) != "sha256:" + vector["sha256"]:
            errors.append(f"{name}: payload digest differs")
    except (KeyError, TypeError, ValueError) as error:
        errors.append(f"{name}: canonical vector is invalid: {error}")
    return errors


RECORD_SCHEMA_NAMES = frozenset(
    {
        "decision-record.schema.json",
        "decision-record-payload.schema.json",
        "decision-record-v2.schema.json",
        "decision-record-payload-v2.schema.json",
        "measurement-run.schema.json",
        "measurement-run-result.schema.json",
    }
)


def _schema_path_for_example(schema_root: Path, schema_name: str) -> Path:
    directory = "records" if schema_name in RECORD_SCHEMA_NAMES else "manifests"
    return schema_root / directory / schema_name


def collect_schema_errors(root: Path) -> list[str]:
    errors: list[str] = []
    schema_root = root / "schemas"
    ids: dict[str, Path] = {}

    for path in sorted(schema_root.rglob("*.schema.json")):
        schema = load_json_strict(path)
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as error:
            errors.append(f"{path.relative_to(root)}: invalid schema: {error}")
            continue
        schema_id = schema.get("$id")
        if (
            not isinstance(schema_id, str)
            or not schema_id.startswith("urn:battlebelief:schema:")
            or ":v" not in schema_id
        ):
            errors.append(f"{path.relative_to(root)}: invalid project schema ID")
        elif schema_id in ids:
            errors.append(
                f"{path.relative_to(root)}: duplicate schema ID also in "
                f"{ids[schema_id].relative_to(root)}"
            )
        else:
            ids[schema_id] = path

    example_paths = sorted((schema_root / "examples").glob("*.example.json"))
    if {path.name for path in example_paths} != set(EXAMPLE_SCHEMA_MAP):
        errors.append("schemas/examples: explicit example-to-schema mapping is incomplete")
    for example_path in example_paths:
        schema_name = EXAMPLE_SCHEMA_MAP.get(example_path.name)
        if schema_name is None:
            continue
        schema_path = _schema_path_for_example(schema_root, schema_name)
        if not schema_path.exists():
            errors.append(f"{example_path.relative_to(root)}: schema missing")
            continue
        instance = load_json_strict(example_path)
        schema = load_json_strict(schema_path)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors.extend(
            f"{example_path.relative_to(root)}: {schema_issue_summary(issue)}"
            for issue in validator.iter_errors(instance)
        )
        if not any(
            error.startswith(f"{example_path.relative_to(root)}: schema violation")
            for error in errors
        ):
            classified = _schema_for_artifact(example_path, instance, root)
            if example_path.name == "measurement-run-result.example.json":
                errors.extend(
                    f"{example_path.relative_to(root)}: {error}"
                    for error in validate_measurement_run_result_document(instance)
                )
            if classified is not None:
                kind = classified[1]
                try:
                    if kind == "registration":
                        validate_registration_semantics(instance, root)
                    elif kind == "calibration_spec":
                        validate_calibration_spec(instance)
                    elif kind == "search_execution":
                        errors.extend(
                            f"{example_path.relative_to(root)}: {error}"
                            for error in _validate_search_execution_references(instance, root)
                        )
                    elif kind == "synthetic_acceptance":
                        validate_synthetic_fixture_manifest(instance, root)
                except RegistrationValidationError as error:
                    errors.append(f"{example_path.relative_to(root)}: {error}")

    vectors: list[dict[str, Any]] = load_json_strict(
        schema_root / "canonicalization/test-vectors.json"
    )
    for vector in vectors:
        actual_bytes = canonicalize(vector["value"])
        expected_bytes = vector["canonical_utf8"].encode("utf-8")
        if actual_bytes != expected_bytes:
            errors.append(f"{vector['name']}: canonical bytes differ")
        actual_digest = manifest_digest(vector["value"])
        if actual_digest != "sha256:" + vector["sha256"]:
            errors.append(f"{vector['name']}: digest differs")

    decision_vectors = load_json_strict(
        schema_root / "canonicalization/decision-record-test-vectors.json"
    )
    for vector in decision_vectors:
        payload_schema_name = vector.get("schema_filename", "decision-record-payload.schema.json")
        payload_schema = load_json_strict(schema_root / "records" / payload_schema_name)
        errors.extend(validate_decision_record_vector(vector, payload_schema))
    errors.extend(validate_repository_artifacts(root))
    return sorted(errors)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = collect_schema_errors(root)
    if errors:
        print(*errors, sep="\n", file=sys.stderr)
        return 1
    print("PASS: schemas, examples, IDs, and canonicalization vectors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
