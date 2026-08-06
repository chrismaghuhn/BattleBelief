from __future__ import annotations

import json
import shutil
from pathlib import Path

from jsonschema import Draft202012Validator
from tools.check_schemas import (
    _validate_capability_catalog,
    _validate_engine_capability_artifacts,
)

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "artifacts/gen9ou/m2/engine-capability-catalog-v1.json"
MANIFEST_PATH = (
    ROOT / "artifacts/gen9ou/m2/engine-capabilities/engine-capability-v2-unqualified.json"
)


def _document(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _copy_engine_artifacts(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    shutil.copytree(ROOT / "schemas", tmp_path / "schemas")
    artifact_root = tmp_path / "artifacts/gen9ou/m2"
    shutil.copytree(ROOT / "artifacts/gen9ou/m2/engine", artifact_root / "engine")
    shutil.copy2(CATALOG_PATH, artifact_root / CATALOG_PATH.name)
    capability_root = artifact_root / "engine-capabilities"
    capability_root.mkdir()
    shutil.copy2(MANIFEST_PATH, capability_root / MANIFEST_PATH.name)
    return tmp_path


def test_artifact_validator_rejects_legacy_task29_evidence_file_outside_closure(
    tmp_path: Path,
) -> None:
    root = _copy_engine_artifacts(tmp_path)
    capability_root = root / "artifacts/gen9ou/m2/engine-capabilities"
    qualified = _document(capability_root / MANIFEST_PATH.name)
    qualified["manifest_id"] = "poke-engine-gen9ou-capabilities-v2-qualified"
    qualified_path = capability_root / "engine-capability-v2-qualified.json"
    qualified_path.write_text(json.dumps(qualified), encoding="utf-8")
    evidence_path = capability_root / "capability-evidence-v1.json"
    evidence_path.write_text(
        (ROOT / "schemas/examples/engine-capability-evidence.example.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    errors = _validate_engine_capability_artifacts(root)

    assert any("outside approved evidence directory" in error for error in errors)


def test_artifact_validator_reports_malformed_discovered_evidence_without_exception(
    tmp_path: Path,
) -> None:
    root = _copy_engine_artifacts(tmp_path)
    evidence_dir = root / "artifacts/gen9ou/m2/engine-capabilities/evidence"
    evidence_dir.mkdir()
    evidence_path = evidence_dir / "broken.json"
    evidence_path.write_text('{"broken": true}', encoding="utf-8")

    errors = _validate_engine_capability_artifacts(root)

    assert errors
    assert any("broken.json" in error and "evidence document" in error for error in errors)


def test_artifact_validator_requires_evidence_filename_to_match_evidence_id(
    tmp_path: Path,
) -> None:
    root = _copy_engine_artifacts(tmp_path)
    evidence_dir = root / "artifacts/gen9ou/m2/engine-capabilities/evidence"
    evidence_dir.mkdir()
    evidence = _document(ROOT / "schemas/examples/engine-capability-evidence.example.json")
    (evidence_dir / "wrong-name.json").write_text(json.dumps(evidence), encoding="utf-8")

    errors = _validate_engine_capability_artifacts(root)

    assert any("filename must match evidence_id" in error for error in errors)


def test_artifact_validator_rejects_evidence_without_a_qualifying_manifest_reference(
    tmp_path: Path,
) -> None:
    root = _copy_engine_artifacts(tmp_path)
    evidence_dir = root / "artifacts/gen9ou/m2/engine-capabilities/evidence"
    evidence_dir.mkdir()
    evidence = _document(ROOT / "schemas/examples/engine-capability-evidence.example.json")
    evidence_path = evidence_dir / f"{evidence['evidence_id']}.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    errors = _validate_engine_capability_artifacts(root)

    assert any("unreferenced evidence document" in error for error in errors)


def test_artifact_validator_reports_manifest_schema_errors_without_keyerror(tmp_path: Path) -> None:
    root = _copy_engine_artifacts(tmp_path)
    manifest_path = root / "artifacts/gen9ou/m2/engine-capabilities" / MANIFEST_PATH.name
    manifest = _document(manifest_path)
    del manifest["engine_source_manifest_digest"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    errors = _validate_engine_capability_artifacts(root)

    assert errors
    assert any("schema violation (required)" in error for error in errors)


def test_artifact_validator_reports_index_schema_errors_without_keyerror(tmp_path: Path) -> None:
    root = _copy_engine_artifacts(tmp_path)
    index_path = root / "artifacts/gen9ou/m2/engine" / "engine-artifact-index.json"
    index = _document(index_path)
    del index["cells"]
    index_path.write_text(json.dumps(index), encoding="utf-8")

    errors = _validate_engine_capability_artifacts(root)

    assert errors
    assert any("schema violation (required)" in error for error in errors)


def test_duplicate_catalog_value_is_rejected_by_semantic_catalog_gate() -> None:
    schema = _document(ROOT / "schemas/catalogs/engine-capability-catalog-v1.schema.json")
    catalog = _document(CATALOG_PATH)
    catalog["definitions"] = [
        {"value": "gen9.transition.order.speed", "description": "First."},
        {"value": "gen9.transition.order.speed", "description": "Second."},
    ]

    # JSON Schema's uniqueItems compares complete objects, so this fixture is
    # structurally valid; the catalog semantic gate owns value uniqueness.
    assert list(Draft202012Validator(schema).iter_errors(catalog)) == []
    _, errors = _validate_capability_catalog(catalog)

    assert any("unique" in error.lower() and "value" in error.lower() for error in errors)
