from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from tools.canonicalize_manifest import manifest_digest
from tools.check_schemas import (
    _validate_capability_catalog,
    _validate_capability_catalog_contract_bindings,
    _validate_capability_evidence,
    _validate_capability_manifest,
    _validate_engine_capability_artifacts,
)
from tools.migrate_engine_capability import migrate_v1_document

from battlebelief_core.domain.engine_capabilities import CapabilityDefinition

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas"
CATALOG_PATH = ROOT / "artifacts/gen9ou/m2/engine-capability-catalog-v1.json"
MANIFEST_PATH = (
    ROOT / "artifacts/gen9ou/m2/engine-capabilities/engine-capability-v2-unqualified.json"
)


def _document(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _target_binding() -> dict[str, object]:
    manifest = _document(MANIFEST_PATH)
    return {
        name: manifest[name]
        for name in (
            "engine_source_manifest_digest",
            "artifact_index_digest",
            "environment_bindings",
            "canonicalization_contract_digest",
        )
    }


def test_migration_requires_valid_v1_source_catalog_and_complete_unqualified_binding() -> None:
    source = _document(SCHEMAS / "examples/engine-capability.example.json")
    catalog = _document(CATALOG_PATH)

    migrated, report = migrate_v1_document(source, catalog, _target_binding())

    v2_schema = _document(SCHEMAS / "manifests/engine-capability-v2.schema.json")
    assert list(Draft202012Validator(v2_schema).iter_errors(migrated)) == []
    assert migrated["claims"] == []
    assert report["loss"] == {
        "exact": 1,
        "approximated": 0,
        "unsupported": 0,
        "known_divergences": 0,
    }

    malformed_source = copy.deepcopy(source)
    malformed_source["generated_at"] = "not-a-date"
    with pytest.raises(ValueError, match="v1 schema"):
        migrate_v1_document(malformed_source, catalog, _target_binding())

    bool_source = copy.deepcopy(source)
    bool_source["schema_version"] = True
    with pytest.raises(ValueError, match="engine-capability v1 document"):
        migrate_v1_document(bool_source, catalog, _target_binding())

    malformed_catalog = copy.deepcopy(catalog)
    malformed_catalog["definitions"] = [{"value": "gen9.x", "description": "x"}]
    with pytest.raises(ValueError, match="catalog"):
        migrate_v1_document(source, malformed_catalog, _target_binding())

    bool_catalog = copy.deepcopy(catalog)
    bool_catalog["generation"] = True
    with pytest.raises(ValueError, match="catalog"):
        migrate_v1_document(source, bool_catalog, _target_binding())

    wrong_digest_binding = _target_binding()
    wrong_digest_binding["canonicalization_contract_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="canonicalization"):
        migrate_v1_document(source, catalog, wrong_digest_binding)


def test_v2_schema_requires_engine_provenance_and_allows_only_complete_qualifying_closure() -> None:
    schema = _document(SCHEMAS / "manifests/engine-capability-v2.schema.json")
    manifest = _document(MANIFEST_PATH)

    without_source = copy.deepcopy(manifest)
    without_source["engine_source_manifest_digest"] = None
    assert list(Draft202012Validator(schema).iter_errors(without_source))

    exact = copy.deepcopy(manifest)
    exact["claims"] = [
        {
            "capability_id": "gen9.legality.move.selection",
            "status": "exact",
            "evidence_refs": [],
            "approximation": None,
        }
    ]
    assert list(Draft202012Validator(schema).iter_errors(exact))

    bounded = copy.deepcopy(exact)
    bounded["claims"][0]["status"] = "bounded_approximation"
    bounded["claims"][0]["approximation"] = {"bound": "x", "condition": "y"}
    assert list(Draft202012Validator(schema).iter_errors(bounded))


def test_evidence_is_not_a_claim_and_uses_project_schema_urn() -> None:
    schema = _document(SCHEMAS / "manifests/engine-capability-evidence.schema.json")
    evidence = _document(SCHEMAS / "examples/engine-capability-evidence.example.json")

    assert "status" not in evidence
    assert list(Draft202012Validator(schema).iter_errors(evidence)) == []
    assert evidence["qualification_result_schema_id"].startswith("urn:battlebelief:schema:")


def test_evidence_context_rejects_catalog_and_capability_mismatches() -> None:
    from battlebelief_core.domain.engine_capabilities import CapabilityCatalog

    catalog = CapabilityCatalog.from_document(_document(CATALOG_PATH))
    evidence = _document(SCHEMAS / "examples/engine-capability-evidence.example.json")
    assert _validate_capability_evidence(evidence, catalog) == []
    for name, replacement, expected in (
        ("catalog_id", "other-catalog", "catalog identity"),
        ("catalog_version", "2", "catalog identity"),
        ("catalog_digest", "sha256:" + "0" * 64, "catalog identity"),
        ("capability_id", "gen9.not.in-catalog", "not defined by this catalog"),
    ):
        mismatched = copy.deepcopy(evidence)
        mismatched[name] = replacement
        errors = _validate_capability_evidence(mismatched, catalog)
        assert any(expected in error for error in errors)


def test_catalog_contract_bindings_resolve_exact_document_bytes(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    shutil.copytree(ROOT / "schemas/canonicalization", tmp_path / "schemas/canonicalization")
    catalog = _document(CATALOG_PATH)

    assert _validate_capability_catalog_contract_bindings(tmp_path, catalog) == []
    for field, value in (
        ("capability_contract_id", "other-contract"),
        ("capability_contract_version", "999"),
        ("capability_contract_digest", "sha256:" + "0" * 64),
        ("canonicalization_contract_id", "other-profile"),
        ("canonicalization_contract_version", "999"),
        ("canonicalization_contract_digest", "sha256:" + "0" * 64),
    ):
        mismatched = copy.deepcopy(catalog)
        mismatched[field] = value
        assert _validate_capability_catalog_contract_bindings(tmp_path, mismatched)


def test_catalog_semantics_reject_duplicate_capability_values_with_distinct_descriptions() -> None:
    catalog = _document(CATALOG_PATH)
    duplicate = copy.deepcopy(catalog)
    duplicate["definitions"].append(
        {
            "value": duplicate["definitions"][-1]["value"],
            "description": "A distinct description cannot create a second capability.",
        }
    )
    schema = _document(SCHEMAS / "catalogs/engine-capability-catalog-v1.schema.json")

    assert list(Draft202012Validator(schema).iter_errors(duplicate)) == []
    _, errors = _validate_capability_catalog(duplicate)
    assert any("uniquely sorted by value" in error for error in errors)


def test_v2_digest_ignores_object_key_order_but_core_rejects_noncanonical_arrays() -> None:
    from battlebelief_core.domain.engine_capabilities import CapabilityCatalog

    manifest = _document(MANIFEST_PATH)
    assert manifest_digest(manifest) == manifest_digest(dict(reversed(list(manifest.items()))))
    catalog = CapabilityCatalog.from_document(_document(CATALOG_PATH))
    reordered = copy.deepcopy(manifest)
    reordered["environment_bindings"] = list(reversed(reordered["environment_bindings"]))
    assert manifest_digest(reordered) != manifest_digest(manifest)
    assert _validate_capability_manifest(reordered, catalog)


@pytest.mark.parametrize("value", ["gen9.x.y", "gen9.a.b.c.d.e.f.g"])
def test_capability_grammar_accepts_three_to_eight_segments_across_core_and_schemas(
    value: str,
) -> None:
    CapabilityDefinition(value=value, description="x")
    catalog_schema = _document(SCHEMAS / "catalogs/engine-capability-catalog-v1.schema.json")
    catalog = _document(CATALOG_PATH)
    catalog["definitions"] = [{"value": value, "description": "x"}]
    assert list(Draft202012Validator(catalog_schema).iter_errors(catalog)) == []


@pytest.mark.parametrize("value", ["gen9.x", "gen9.a.b.c.d.e.f.g.h.i"])
def test_capability_grammar_rejects_outside_three_to_eight_segments(value: str) -> None:
    with pytest.raises(ValueError):
        CapabilityDefinition(value=value, description="x")
    catalog_schema = _document(SCHEMAS / "catalogs/engine-capability-catalog-v1.schema.json")
    catalog = _document(CATALOG_PATH)
    catalog["definitions"] = [{"value": value, "description": "x"}]
    assert list(Draft202012Validator(catalog_schema).iter_errors(catalog))


def test_task25_closure_rejects_stale_source_index_and_environment_cells(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    shutil.copytree(ROOT / "schemas", tmp_path / "schemas")
    artifact_root = tmp_path / "artifacts/gen9ou/m2"
    shutil.copytree(ROOT / "artifacts/gen9ou/m2/engine", artifact_root / "engine")
    shutil.copy2(CATALOG_PATH, artifact_root / CATALOG_PATH.name)
    (artifact_root / "engine-capabilities").mkdir()
    target = artifact_root / "engine-capabilities/engine-capability-v2-unqualified.json"

    target.write_text(MANIFEST_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    assert _validate_engine_capability_artifacts(tmp_path) == []

    for mutation in (
        lambda document: document.__setitem__(
            "engine_source_manifest_digest", "sha256:" + "0" * 64
        ),
        lambda document: document.__setitem__("artifact_index_digest", "sha256:" + "0" * 64),
        lambda document: document["environment_bindings"].pop(),
        lambda document: document["environment_bindings"].append(
            {
                "environment_cell_id": "stale-cell",
                "engine_build_manifest_digest": "sha256:" + "0" * 64,
                "wheel_digest": "sha256:" + "0" * 64,
            }
        ),
        lambda document: document.__setitem__("transition_adapter_id", "not-task25"),
    ):
        manifest = _document(MANIFEST_PATH)
        mutation(manifest)
        target.write_text(json.dumps(manifest), encoding="utf-8")
        assert _validate_engine_capability_artifacts(tmp_path)

    source_path = artifact_root / "engine/engine-source.json"
    source = _document(source_path)
    source["manifest_id"] = "stale-source"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    target.write_text(MANIFEST_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    assert _validate_engine_capability_artifacts(tmp_path)

    source_path.write_text(
        (ROOT / "artifacts/gen9ou/m2/engine/engine-source.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    index_path = artifact_root / "engine/engine-artifact-index.json"
    for field in ("build_manifest_digest", "wheel_sha256"):
        index = _document(ROOT / "artifacts/gen9ou/m2/engine/engine-artifact-index.json")
        index["cells"][0][field] = "sha256:" + "0" * 64
        index_path.write_text(json.dumps(index), encoding="utf-8")
        assert _validate_engine_capability_artifacts(tmp_path)

    index = _document(ROOT / "artifacts/gen9ou/m2/engine/engine-artifact-index.json")
    index["cells"][0]["build_manifest_digest"] = "sha256:" + "0" * 64
    index_path.write_text(json.dumps(index), encoding="utf-8")
    coordinated = _document(MANIFEST_PATH)
    coordinated["artifact_index_digest"] = manifest_digest(index)
    coordinated["environment_bindings"][0]["engine_build_manifest_digest"] = "sha256:" + "0" * 64
    target.write_text(json.dumps(coordinated), encoding="utf-8")
    assert _validate_engine_capability_artifacts(tmp_path)


def test_semantic_reconstruction_rejects_unsorted_or_duplicate_unknown_claims() -> None:
    from battlebelief_core.domain.engine_capabilities import CapabilityCatalog

    catalog = CapabilityCatalog.from_document(_document(CATALOG_PATH))
    manifest = _document(MANIFEST_PATH)
    manifest["claims"] = [
        {
            "capability_id": "gen9.transition.terminal.value",
            "status": "unknown",
            "evidence_refs": [],
            "approximation": None,
        },
        {
            "capability_id": "gen9.transition.terastallization.damage",
            "status": "unknown",
            "evidence_refs": [],
            "approximation": None,
        },
    ]
    assert _validate_capability_manifest(manifest, catalog)
    manifest["claims"][1] = copy.deepcopy(manifest["claims"][0])
    assert _validate_capability_manifest(manifest, catalog)


def test_evidence_reference_is_derived_from_the_complete_evidence_document() -> None:
    from battlebelief_core.domain.engine_capabilities import (
        CapabilityCatalog,
        CapabilityEvidenceRef,
    )

    catalog = CapabilityCatalog.from_document(_document(CATALOG_PATH))
    evidence = _document(SCHEMAS / "examples/engine-capability-evidence.example.json")

    reference = CapabilityEvidenceRef.from_document(evidence, catalog)

    assert reference.evidence_id == evidence["evidence_id"]
    assert reference.evidence_digest == manifest_digest(evidence)
    assert reference.capability_id == catalog.id_for(evidence["capability_id"])
    assert reference.runner_source_digest == evidence["runner_source_digest"]
    assert reference.classifier_source_digest == evidence["classifier_source_digest"]
    changed = copy.deepcopy(evidence)
    changed["capability_id"] = "gen9.legality.terastallization.activation"
    assert (
        CapabilityEvidenceRef.from_document(changed, catalog).evidence_digest
        != reference.evidence_digest
    )


def test_qualified_manifest_validates_exact_directory_evidence_closure(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts/gen9ou/m2"
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    shutil.copytree(ROOT / "schemas", tmp_path / "schemas")
    shutil.copytree(ROOT / "artifacts/gen9ou/m2/engine", artifact_root / "engine")
    shutil.copy2(CATALOG_PATH, artifact_root / CATALOG_PATH.name)
    evidence_dir = artifact_root / "engine-capabilities/evidence"
    evidence_dir.mkdir(parents=True)

    catalog = _document(CATALOG_PATH)
    evidence = _document(SCHEMAS / "examples/engine-capability-evidence.example.json")
    manifest = _document(MANIFEST_PATH)
    evidence.update(
        {
            "catalog_id": catalog["catalog_id"],
            "catalog_version": catalog["catalog_version"],
            "catalog_digest": manifest_digest(catalog),
            "capability_id": "gen9.legality.move.selection",
            "engine_source_manifest_digest": manifest["engine_source_manifest_digest"],
            "artifact_index_digest": manifest["artifact_index_digest"],
        }
    )
    evidence_documents: list[dict[str, object]] = []
    references: list[dict[str, object]] = []
    for index, binding in enumerate(manifest["environment_bindings"], start=1):
        document = copy.deepcopy(evidence)
        document.update(
            {
                "evidence_id": f"fixture-evidence-{index}",
                "environment_cell_id": binding["environment_cell_id"],
                "engine_build_manifest_digest": binding["engine_build_manifest_digest"],
                "wheel_digest": binding["wheel_digest"],
            }
        )
        evidence_documents.append(document)
        reference = {**document, "evidence_digest": manifest_digest(document)}
        reference.pop("schema_version")
        references.append(reference)
    manifest.update(
        {
            "manifest_id": "poke-engine-gen9ou-capabilities-v2-qualified",
            "transition_adapter_id": evidence["transition_adapter_id"],
            "transition_adapter_version": evidence["transition_adapter_version"],
            "transition_adapter_source_digest": evidence["transition_adapter_source_digest"],
            "transition_model_contract_digest": evidence["transition_model_contract_digest"],
            "transition_adapter_conformance_digest": evidence[
                "transition_adapter_conformance_digest"
            ],
            "oracle_source_manifest_digest": evidence["oracle_source_manifest_digest"],
            "oracle_build_manifest_digest": evidence["oracle_build_manifest_digest"],
            "ruleset_digest": evidence["ruleset_digest"],
            "corpus_digest": evidence["corpus_digest"],
            "runner_source_digest": evidence["runner_source_digest"],
            "classifier_source_digest": evidence["classifier_source_digest"],
            "claims": [
                {
                    "capability_id": evidence["capability_id"],
                    "status": "exact",
                    "evidence_refs": references,
                    "approximation": None,
                },
                {
                    "capability_id": "gen9.transition.order.speed",
                    "status": "unsupported",
                    "evidence_refs": [],
                    "approximation": None,
                },
            ],
        }
    )
    manifest["evidence_set_digest"] = manifest_digest({"evidence_refs": references})
    manifest_path = artifact_root / "engine-capabilities/engine-capability-v2-qualified.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    migrated_unqualified = copy.deepcopy(_document(MANIFEST_PATH))
    migrated_unqualified["manifest_id"] = "poke-engine-gen9ou-capabilities-v2-migrated"
    migrated_path = artifact_root / "engine-capabilities/engine-capability-v2-migrated.json"
    migrated_path.write_text(json.dumps(migrated_unqualified), encoding="utf-8")

    assert _validate_engine_capability_artifacts(tmp_path)
    for document in evidence_documents:
        (evidence_dir / f"{document['evidence_id']}.json").write_text(
            json.dumps(document), encoding="utf-8"
        )
    assert _validate_engine_capability_artifacts(tmp_path) == []

    second_documents: list[dict[str, object]] = []
    second_references: list[dict[str, object]] = []
    for index, document in enumerate(evidence_documents, start=1):
        second_document = copy.deepcopy(document)
        second_document["evidence_id"] = f"second-fixture-evidence-{index}"
        second_document["capability_id"] = "gen9.transition.order.speed"
        second_documents.append(second_document)
        second_reference = {**second_document, "evidence_digest": manifest_digest(second_document)}
        second_reference.pop("schema_version")
        second_references.append(second_reference)
        (evidence_dir / f"{second_document['evidence_id']}.json").write_text(
            json.dumps(second_document), encoding="utf-8"
        )
    second_manifest = copy.deepcopy(manifest)
    second_manifest["manifest_id"] = "poke-engine-gen9ou-capabilities-v2-qualified-second"
    second_manifest["claims"] = [
        {
            "capability_id": "gen9.transition.order.speed",
            "status": "exact",
            "evidence_refs": second_references,
            "approximation": None,
        }
    ]
    second_manifest["evidence_set_digest"] = manifest_digest({"evidence_refs": second_references})
    second_manifest_path = (
        artifact_root / "engine-capabilities/engine-capability-v2-qualified-second.json"
    )
    second_manifest_path.write_text(json.dumps(second_manifest), encoding="utf-8")
    assert _validate_engine_capability_artifacts(tmp_path) == []

    unsupported_evidence = copy.deepcopy(evidence_documents[0])
    unsupported_evidence["evidence_id"] = "unsupported-capability-evidence"
    unsupported_evidence["capability_id"] = "gen9.transition.order.speed"
    unsupported_path = evidence_dir / "unsupported-capability-evidence.json"
    unsupported_path.write_text(json.dumps(unsupported_evidence), encoding="utf-8")
    errors = _validate_engine_capability_artifacts(tmp_path)
    assert any("unreferenced evidence" in error for error in errors)
    unsupported_path.unlink()
    second_manifest_path.unlink()
    for document in second_documents:
        (evidence_dir / f"{document['evidence_id']}.json").unlink()

    missing_path = evidence_dir / f"{evidence_documents[0]['evidence_id']}.json"
    missing_path.unlink()
    errors = _validate_engine_capability_artifacts(tmp_path)
    assert any("referenced evidence document" in error for error in errors)
    missing_path.write_text(json.dumps(evidence_documents[0]), encoding="utf-8")

    extra = copy.deepcopy(evidence_documents[0])
    extra["evidence_id"] = "unreferenced-evidence"
    extra_path = evidence_dir / "unreferenced-evidence.json"
    extra_path.write_text(json.dumps(extra), encoding="utf-8")
    errors = _validate_engine_capability_artifacts(tmp_path)
    assert any("unreferenced evidence" in error for error in errors)
    extra_path.unlink()

    duplicate_id = copy.deepcopy(evidence_documents[0])
    duplicate_id_path = evidence_dir / "zzz-duplicate-evidence.json"
    duplicate_id_path.write_text(json.dumps(duplicate_id), encoding="utf-8")
    errors = _validate_engine_capability_artifacts(tmp_path)
    assert any("duplicate evidence_id" in error for error in errors)
    duplicate_id_path.unlink()

    duplicate_digest = copy.deepcopy(manifest)
    duplicate_digest["claims"][0]["evidence_refs"][1]["evidence_digest"] = duplicate_digest[
        "claims"
    ][0]["evidence_refs"][0]["evidence_digest"]
    manifest_path.write_text(json.dumps(duplicate_digest), encoding="utf-8")
    errors = _validate_engine_capability_artifacts(tmp_path)
    assert any("unique evidence digests" in error for error in errors)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    wrong_cell = copy.deepcopy(evidence_documents[0])
    wrong_cell["environment_cell_id"] = "wrong-cell"
    missing_path.write_text(json.dumps(wrong_cell), encoding="utf-8")
    errors = _validate_engine_capability_artifacts(tmp_path)
    assert any(
        "referenced evidence document does not match evidence_ref" in error for error in errors
    )
    missing_path.write_text(json.dumps(evidence_documents[0]), encoding="utf-8")

    evidence_documents[0]["capability_id"] = "gen9.legality.terastallization.activation"
    (evidence_dir / f"{evidence_documents[0]['evidence_id']}.json").write_text(
        json.dumps(evidence_documents[0]), encoding="utf-8"
    )
    errors = _validate_engine_capability_artifacts(tmp_path)
    assert any("capability" in error and "evidence" in error for error in errors)
