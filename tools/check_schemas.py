from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

# Allow `python tools/check_schemas.py` without -m
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from jsonschema import Draft202012Validator, FormatChecker  # noqa: E402

from battlebelief_core.domain.engine_capabilities import (  # noqa: E402
    CapabilityApproximation,
    CapabilityCatalog,
    CapabilityClaim,
    CapabilityEvidenceRef,
    CapabilityMigrationClosure,
    CapabilityStatus,
    EngineCapabilityManifest,
    EngineEnvironmentBinding,
)
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
from battlebelief_lab.oracle.showdown import (  # noqa: E402
    ShowdownBuildManifest,
    ShowdownSourceManifest,
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
    "engine-capability-catalog-v1.example.json": "engine-capability-catalog-v1.schema.json",
    "engine-capability-v2.example.json": "engine-capability-v2.schema.json",
    "engine-capability-evidence.example.json": "engine-capability-evidence.schema.json",
    "engine-source.example.json": "engine-source.schema.json",
    "engine-build.example.json": "engine-build.schema.json",
    "engine-artifact-index.example.json": "engine-artifact-index.schema.json",
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
    "showdown-oracle-source.example.json": "showdown-oracle-source.schema.json",
    "showdown-oracle-build.example.json": "showdown-oracle-build.schema.json",
}

INVALID_EXAMPLE_SCHEMA_MAP = {
    "invalid/engine-source.invalid.json": "engine-source.schema.json",
    "invalid/engine-build.invalid.json": "engine-build.schema.json",
    "invalid/engine-artifact-index.invalid.json": "engine-artifact-index.schema.json",
    "invalid/engine-capability-catalog-v1.invalid.json": "engine-capability-catalog-v1.schema.json",
    "invalid/engine-capability-v2.invalid.json": "engine-capability-v2.schema.json",
    "invalid/engine-capability-evidence.invalid.json": "engine-capability-evidence.schema.json",
    "invalid/showdown-oracle-source.invalid.json": "showdown-oracle-source.schema.json",
    "invalid/showdown-oracle-build.invalid.json": "showdown-oracle-build.schema.json",
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

CATALOG_SCHEMA_NAMES = frozenset({"engine-capability-catalog-v1.schema.json"})


def _schema_path_for_example(schema_root: Path, schema_name: str) -> Path:
    if schema_name in CATALOG_SCHEMA_NAMES:
        return schema_root / "catalogs" / schema_name
    directory = "records" if schema_name in RECORD_SCHEMA_NAMES else "manifests"
    return schema_root / directory / schema_name


def _validate_capability_catalog(
    document: dict[str, Any],
) -> tuple[CapabilityCatalog | None, list[str]]:
    try:
        catalog = CapabilityCatalog.from_document(document)
    except (TypeError, ValueError) as error:
        return None, [f"catalog reconstruction failed: {error}"]
    return catalog, []


def _validate_capability_evidence(
    document: dict[str, Any], catalog: CapabilityCatalog
) -> list[str]:
    try:
        CapabilityEvidenceRef.from_document(document, catalog)
    except (KeyError, TypeError, ValueError) as error:
        return [f"capability evidence semantic validation failed: {error}"]
    return []


def _validate_capability_manifest(
    document: dict[str, Any],
    catalog: CapabilityCatalog,
    evidence_documents: Mapping[str, CapabilityEvidenceRef] | None = None,
) -> list[str]:
    try:
        if (
            document["catalog_id"] != catalog.catalog_id
            or document["catalog_version"] != catalog.catalog_version
            or document["catalog_digest"] != catalog.catalog_digest
        ):
            raise ValueError("manifest catalog identity does not match the catalog")
        if (
            document["engine_source_manifest_digest"] is None
            or document["artifact_index_digest"] is None
        ):
            raise ValueError("usable capability manifest requires engine source and artifact index")
        bindings = tuple(
            EngineEnvironmentBinding(**binding) for binding in document["environment_bindings"]
        )
        claims: list[CapabilityClaim] = []
        for item in document["claims"]:
            refs = tuple(
                CapabilityEvidenceRef(
                    **{
                        **ref,
                        "capability_id": catalog.id_for(ref["capability_id"]),
                    }
                )
                for ref in item["evidence_refs"]
            )
            approximation = item["approximation"]
            claims.append(
                CapabilityClaim(
                    capability_id=catalog.id_for(item["capability_id"]),
                    status=CapabilityStatus(item["status"]),
                    evidence_refs=refs,
                    approximation=(
                        None if approximation is None else CapabilityApproximation(**approximation)
                    ),
                )
            )
        EngineCapabilityManifest(
            manifest_id=document["manifest_id"],
            catalog=catalog,
            generation=document["generation"],
            format=document["format"],
            engine_source_manifest_digest=document["engine_source_manifest_digest"],
            artifact_index_digest=document["artifact_index_digest"],
            environment_bindings=bindings,
            transition_adapter_id=document["transition_adapter_id"],
            transition_adapter_version=document["transition_adapter_version"],
            transition_adapter_source_digest=document["transition_adapter_source_digest"],
            transition_model_contract_digest=document["transition_model_contract_digest"],
            transition_adapter_conformance_digest=document["transition_adapter_conformance_digest"],
            oracle_source_manifest_digest=document["oracle_source_manifest_digest"],
            oracle_build_manifest_digest=document["oracle_build_manifest_digest"],
            ruleset_digest=document["ruleset_digest"],
            corpus_digest=document["corpus_digest"],
            runner_source_digest=document["runner_source_digest"],
            classifier_source_digest=document["classifier_source_digest"],
            evidence_set_digest=document["evidence_set_digest"],
            canonicalization_contract_digest=document["canonicalization_contract_digest"],
            migration=(
                None
                if document["migration"] is None
                else CapabilityMigrationClosure(
                    source_schema_id=document["migration"]["source_schema_id"],
                    source_digest=document["migration"]["source_digest"],
                    migrator_id=document["migration"]["migrator_id"],
                    migrator_version=document["migration"]["migrator_version"],
                    loss_codes=tuple(document["migration"]["loss_codes"]),
                    loss_report_digest=document["migration"]["loss_report_digest"],
                )
            ),
            claims=tuple(claims),
        )
        if evidence_documents is not None:
            for claim in claims:
                for ref in claim.evidence_refs:
                    document_ref = evidence_documents.get(ref.evidence_id)
                    if document_ref is None or document_ref != ref:
                        raise ValueError("referenced evidence document does not match evidence_ref")
    except (KeyError, TypeError, ValueError) as error:
        return [f"capability manifest semantic validation failed: {error}"]
    return []


def _load_capability_evidence_documents(
    evidence_directory: Path, catalog: CapabilityCatalog, schema: dict[str, Any]
) -> tuple[dict[str, CapabilityEvidenceRef], list[str]]:
    """Load canonical evidence documents from the deterministic Task-26 directory."""

    if not evidence_directory.exists():
        return {}, []
    if not evidence_directory.is_dir():
        return {}, [f"{evidence_directory}: evidence path is not a directory"]
    documents: dict[str, CapabilityEvidenceRef] = {}
    errors: list[str] = []
    for path in sorted(evidence_directory.glob("*.json")):
        document = load_json_strict(path)
        errors.extend(
            f"{path}: {schema_issue_summary(issue)}"
            for issue in Draft202012Validator(schema).iter_errors(document)
        )
        try:
            reference = CapabilityEvidenceRef.from_document(document, catalog)
            if reference.evidence_id in documents:
                raise ValueError("duplicate evidence_id")
            if any(
                item.evidence_digest == reference.evidence_digest for item in documents.values()
            ):
                raise ValueError("duplicate evidence_digest")
            documents[reference.evidence_id] = reference
        except (TypeError, ValueError) as error:
            errors.append(f"{path}: capability evidence semantic validation failed: {error}")
    return documents, errors


def _validate_engine_capability_artifacts(root: Path) -> list[str]:
    errors: list[str] = []
    schema_root = root / "schemas"
    catalog_path = root / "artifacts/gen9ou/m2/engine-capability-catalog-v1.json"
    manifest_path = (
        root / "artifacts/gen9ou/m2/engine-capabilities/engine-capability-v2-unqualified.json"
    )
    engine_root = root / "artifacts/gen9ou/m2/engine"
    source_path = engine_root / "engine-source.json"
    index_path = engine_root / "engine-artifact-index.json"
    if not all(path.is_file() for path in (catalog_path, manifest_path, source_path, index_path)):
        return ["engine capability catalog or initial v2 manifest is missing"]
    catalog_document = load_json_strict(catalog_path)
    manifest_document = load_json_strict(manifest_path)
    source_document = load_json_strict(source_path)
    index_document = load_json_strict(index_path)
    for path, schema_name, document in (
        (catalog_path, "engine-capability-catalog-v1.schema.json", catalog_document),
        (manifest_path, "engine-capability-v2.schema.json", manifest_document),
    ):
        schema = load_json_strict(_schema_path_for_example(schema_root, schema_name))
        errors.extend(
            f"{path.relative_to(root)}: {schema_issue_summary(issue)}"
            for issue in Draft202012Validator(schema).iter_errors(document)
        )
    catalog, catalog_errors = _validate_capability_catalog(catalog_document)
    errors.extend(f"{catalog_path.relative_to(root)}: {error}" for error in catalog_errors)
    if catalog is not None:
        evidence_schema = load_json_strict(
            _schema_path_for_example(schema_root, "engine-capability-evidence.schema.json")
        )
        evidence_documents, evidence_errors = _load_capability_evidence_documents(
            manifest_path.parent / "evidence", catalog, evidence_schema
        )
        errors.extend(evidence_errors)
        errors.extend(
            f"{manifest_path.relative_to(root)}: {error}"
            for error in _validate_capability_manifest(
                manifest_document, catalog, evidence_documents
            )
        )
    source_digest = manifest_digest(source_document)
    index_digest = manifest_digest(index_document)
    if manifest_document["engine_source_manifest_digest"] != source_digest:
        errors.append(f"{manifest_path.relative_to(root)}: engine source digest does not match")
    if manifest_document["artifact_index_digest"] != index_digest:
        errors.append(f"{manifest_path.relative_to(root)}: artifact index digest does not match")
    if index_document.get("source_manifest_digest") != source_digest:
        errors.append(
            f"{index_path.relative_to(root)}: source digest does not match source manifest"
        )
    for cell in index_document["cells"]:
        cell_id = cell["cell_id"]
        build_path = engine_root / f"engine-build-{cell_id}.json"
        if not build_path.is_file():
            errors.append(f"{index_path.relative_to(root)}: build manifest missing for {cell_id}")
            continue
        build_document = load_json_strict(build_path)
        if manifest_digest(build_document) != cell["build_manifest_digest"]:
            errors.append(f"{build_path.relative_to(root)}: canonical digest does not match index")
        if build_document.get("cell_id") != cell_id:
            errors.append(f"{build_path.relative_to(root)}: cell ID does not match index")
        if build_document.get("source_manifest_digest") != source_digest:
            errors.append(
                f"{build_path.relative_to(root)}: source digest does not match source manifest"
            )
        wheel = build_document.get("wheel")
        if not isinstance(wheel, dict) or wheel.get("sha256") != cell["wheel_sha256"]:
            errors.append(f"{build_path.relative_to(root)}: wheel digest does not match index")
    expected_cells = [
        {
            "environment_cell_id": cell["cell_id"],
            "engine_build_manifest_digest": cell["build_manifest_digest"],
            "wheel_digest": cell["wheel_sha256"],
        }
        for cell in sorted(index_document["cells"], key=lambda item: item["cell_id"])
    ]
    if manifest_document["environment_bindings"] != expected_cells:
        errors.append(f"{manifest_path.relative_to(root)}: environment bindings do not match index")
    adapter_fields = (
        "transition_adapter_id",
        "transition_adapter_version",
        "transition_adapter_source_digest",
        "transition_model_contract_digest",
        "transition_adapter_conformance_digest",
    )
    if not manifest_document["claims"] and any(
        manifest_document[name] is not None for name in adapter_fields
    ):
        errors.append(
            f"{manifest_path.relative_to(root)}: initial artifact must not bind an adapter"
        )
    return errors


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
                    elif kind == "measurement_run_result":
                        errors.extend(
                            f"{example_path.relative_to(root)}: schema violation: {error}"
                            for error in validate_measurement_run_result_document(instance)
                        )
                except RegistrationValidationError as error:
                    errors.append(f"{example_path.relative_to(root)}: {error}")
        if example_path.name == "showdown-oracle-source.example.json":
            try:
                ShowdownSourceManifest.from_dict(instance)
            except ValueError as error:
                errors.append(f"{example_path.relative_to(root)}: source manifest: {error}")
        if example_path.name == "showdown-oracle-build.example.json":
            try:
                ShowdownBuildManifest.from_dict(instance)
            except ValueError as error:
                errors.append(f"{example_path.relative_to(root)}: build manifest: {error}")

    invalid_root = schema_root / "examples" / "invalid"
    invalid_paths = sorted(invalid_root.rglob("*.invalid.json")) if invalid_root.exists() else []
    invalid_names = {
        path.relative_to(schema_root / "examples").as_posix() for path in invalid_paths
    }
    if invalid_names != set(INVALID_EXAMPLE_SCHEMA_MAP):
        errors.append("schemas/examples/invalid: explicit invalid example mapping is incomplete")
    for invalid_path in invalid_paths:
        invalid_name = invalid_path.relative_to(schema_root / "examples").as_posix()
        schema_name = INVALID_EXAMPLE_SCHEMA_MAP.get(invalid_name)
        if schema_name is None:
            continue
        schema_path = _schema_path_for_example(schema_root, schema_name)
        if not schema_path.exists():
            errors.append(f"{invalid_path.relative_to(root)}: schema missing")
            continue
        instance = load_json_strict(invalid_path)
        schema = load_json_strict(schema_path)
        if not list(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(instance)
        ):
            errors.append(f"{invalid_path.relative_to(root)}: expected schema rejection")

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
    errors.extend(_validate_engine_capability_artifacts(root))
    evidence_example_path = schema_root / "examples/engine-capability-evidence.example.json"
    catalog_artifact_path = root / "artifacts/gen9ou/m2/engine-capability-catalog-v1.json"
    if evidence_example_path.is_file() and catalog_artifact_path.is_file():
        catalog, catalog_errors = _validate_capability_catalog(
            load_json_strict(catalog_artifact_path)
        )
        errors.extend(
            f"{catalog_artifact_path.relative_to(root)}: {error}" for error in catalog_errors
        )
        if catalog is not None:
            errors.extend(
                f"{evidence_example_path.relative_to(root)}: {error}"
                for error in _validate_capability_evidence(
                    load_json_strict(evidence_example_path), catalog
                )
            )
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
