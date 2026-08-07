"""Fail-closed conversion of a v1 engine-capability document into v2."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from battlebelief_core.domain.engine_capabilities import (
    ENGINE_CAPABILITY_V1_SCHEMA_ID,
    ENGINE_CAPABILITY_V1_TO_V2_LOSS_CODES,
    ENGINE_CAPABILITY_V1_TO_V2_MIGRATOR_ID,
    ENGINE_CAPABILITY_V1_TO_V2_MIGRATOR_VERSION,
    CapabilityCatalog,
    CapabilityMigrationClosure,
    EngineCapabilityManifest,
    EngineEnvironmentBinding,
)
from tools.canonicalize_manifest import manifest_digest

MIGRATOR_ID = ENGINE_CAPABILITY_V1_TO_V2_MIGRATOR_ID
MIGRATOR_VERSION = ENGINE_CAPABILITY_V1_TO_V2_MIGRATOR_VERSION
SOURCE_SCHEMA_ID = ENGINE_CAPABILITY_V1_SCHEMA_ID
LOSS_CODES = ENGINE_CAPABILITY_V1_TO_V2_LOSS_CODES
_ROOT = Path(__file__).resolve().parents[1]
_V1_SCHEMA = _ROOT / "schemas/manifests/engine-capability.schema.json"
_V2_SCHEMA = _ROOT / "schemas/manifests/engine-capability-v2.schema.json"
_LOSS_REPORT_SCHEMA = (
    _ROOT / "schemas/manifests/engine-capability-migration-loss-report.schema.json"
)
_BINDING_FIELDS = frozenset(
    {
        "engine_source_manifest_digest",
        "artifact_index_digest",
        "environment_bindings",
        "canonicalization_contract_digest",
    }
)


def _schema_errors(path: Path, document: Mapping[str, object]) -> list[object]:
    schema = __import__("json").loads(path.read_text(encoding="utf-8"))
    return list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document))


def _require_valid_source(source: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(source, Mapping) or type(source.get("schema_version")) is not int:
        raise ValueError("source must be an engine-capability v1 document")
    document = dict(source)
    if _schema_errors(_V1_SCHEMA, document):
        raise ValueError("source fails the engine-capability v1 schema")
    return document


def _require_catalog(catalog: Mapping[str, object]) -> CapabilityCatalog:
    if not isinstance(catalog, Mapping):
        raise ValueError("catalog must be a v1 capability catalog document")
    try:
        return CapabilityCatalog.from_document(catalog)
    except (TypeError, ValueError) as error:
        raise ValueError(f"catalog is invalid: {error}") from error


def _require_binding(
    binding: Mapping[str, object], catalog: CapabilityCatalog
) -> tuple[str, str, tuple[EngineEnvironmentBinding, ...], str]:
    if not isinstance(binding, Mapping) or set(binding) != _BINDING_FIELDS:
        raise ValueError("unqualified target binding has an invalid shape")
    canonicalization_contract_digest = binding["canonicalization_contract_digest"]
    if canonicalization_contract_digest != catalog.canonicalization_contract_digest:
        raise ValueError("target binding canonicalization does not match catalog")
    try:
        environment_bindings = tuple(
            EngineEnvironmentBinding(**item) for item in binding["environment_bindings"]
        )
    except (TypeError, ValueError) as error:
        raise ValueError(f"target binding environments are invalid: {error}") from error
    cells = tuple(item.environment_cell_id for item in environment_bindings)
    if cells != tuple(sorted(cells)) or len(set(cells)) != len(cells):
        raise ValueError("target binding environments must be uniquely sorted")
    source_digest = binding["engine_source_manifest_digest"]
    index_digest = binding["artifact_index_digest"]
    if type(source_digest) is not str or type(index_digest) is not str:
        raise ValueError("target binding engine provenance must be strings")
    if type(canonicalization_contract_digest) is not str:
        raise ValueError("target binding canonicalization must be a string")
    return source_digest, index_digest, environment_bindings, canonicalization_contract_digest


def _v2_compatible_id(value: str) -> str:
    """Map a schema-valid v1 ID into the narrower v2 ID grammar."""

    return value if value[0].isalpha() else f"v1-{value}"


def migrate_v1_document(
    source: Mapping[str, object],
    catalog: Mapping[str, object],
    unqualified_target_binding: Mapping[str, object],
    *,
    source_document_id: str | None = None,
    loss_report_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Produce a Core-valid, explicitly unqualified v2 target and loss report."""

    source_document = _require_valid_source(source)
    catalog_value = _require_catalog(catalog)
    source_digest, index_digest, environment_bindings, canonicalization_digest = _require_binding(
        unqualified_target_binding, catalog_value
    )
    source_manifest_id = _v2_compatible_id(str(source_document["manifest_id"]))
    source_document_id = _v2_compatible_id(
        str(source_document_id) if source_document_id is not None else source_manifest_id
    )
    target_manifest_id = f"{source_manifest_id}-v2-unqualified"
    loss_report_id = (
        str(loss_report_id)
        if loss_report_id is not None
        else f"{target_manifest_id}-loss-report-v1"
    )
    loss = {
        name: len(source_document[name])
        for name in ("exact", "approximated", "unsupported", "known_divergences")
    }
    loss_codes = LOSS_CODES
    report_projection = {
        "report_id": loss_report_id,
        "source_document_id": source_document_id,
        "source_schema_id": SOURCE_SCHEMA_ID,
        "source_digest": manifest_digest(source_document),
        "migrator_id": MIGRATOR_ID,
        "migrator_version": MIGRATOR_VERSION,
        "loss_codes": list(loss_codes),
        "loss": loss,
    }
    loss_report_digest = manifest_digest(report_projection)
    target: dict[str, Any] = {
        "schema_version": 2,
        "manifest_id": target_manifest_id,
        "catalog_id": catalog_value.catalog_id,
        "catalog_version": catalog_value.catalog_version,
        "catalog_digest": catalog_value.catalog_digest,
        "generation": 9,
        "format": "gen9ou",
        "engine_source_manifest_digest": source_digest,
        "artifact_index_digest": index_digest,
        "environment_bindings": [
            {
                "environment_cell_id": item.environment_cell_id,
                "engine_build_manifest_digest": item.engine_build_manifest_digest,
                "wheel_digest": item.wheel_digest,
            }
            for item in environment_bindings
        ],
        "transition_adapter_id": None,
        "transition_adapter_version": None,
        "transition_adapter_source_digest": None,
        "transition_model_contract_digest": None,
        "transition_adapter_conformance_digest": None,
        "oracle_source_manifest_digest": None,
        "oracle_build_manifest_digest": None,
        "ruleset_digest": None,
        "corpus_digest": None,
        "runner_source_digest": None,
        "classifier_source_digest": None,
        "evidence_set_digest": None,
        "canonicalization_contract_digest": canonicalization_digest,
        "migration": {
            "source_schema_id": SOURCE_SCHEMA_ID,
            "source_document_id": source_document_id,
            "source_digest": report_projection["source_digest"],
            "migrator_id": MIGRATOR_ID,
            "migrator_version": MIGRATOR_VERSION,
            "loss_codes": list(loss_codes),
            "loss_report_id": loss_report_id,
            "loss_report_digest": loss_report_digest,
        },
        "claims": [],
    }
    if _schema_errors(_V2_SCHEMA, target):
        raise ValueError("migrated target fails the engine-capability v2 schema")
    try:
        EngineCapabilityManifest(
            manifest_id=target["manifest_id"],
            catalog=catalog_value,
            generation=target["generation"],
            format=target["format"],
            engine_source_manifest_digest=target["engine_source_manifest_digest"],
            artifact_index_digest=target["artifact_index_digest"],
            environment_bindings=environment_bindings,
            transition_adapter_id=None,
            transition_adapter_version=None,
            transition_adapter_source_digest=None,
            transition_model_contract_digest=None,
            transition_adapter_conformance_digest=None,
            oracle_source_manifest_digest=None,
            oracle_build_manifest_digest=None,
            ruleset_digest=None,
            corpus_digest=None,
            runner_source_digest=None,
            classifier_source_digest=None,
            evidence_set_digest=None,
            canonicalization_contract_digest=canonicalization_digest,
            migration=CapabilityMigrationClosure(
                source_schema_id=SOURCE_SCHEMA_ID,
                source_document_id=source_document_id,
                source_digest=report_projection["source_digest"],
                migrator_id=MIGRATOR_ID,
                migrator_version=MIGRATOR_VERSION,
                loss_codes=loss_codes,
                loss_report_id=loss_report_id,
                loss_report_digest=loss_report_digest,
            ),
            claims=(),
        )
    except ValueError as error:
        raise ValueError(f"migrated target fails Core validation: {error}") from error
    report = {
        "schema_version": 1,
        **report_projection,
        "loss_report_digest": loss_report_digest,
        "target_digest": manifest_digest(target),
    }
    if _schema_errors(_LOSS_REPORT_SCHEMA, report):
        raise ValueError("migration loss report fails its schema")
    return target, report
