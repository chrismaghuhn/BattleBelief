from __future__ import annotations

import json
import os
import shutil
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest
import tools.check_schemas as schema_checker
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
    assert all(str(tmp_path) not in error for error in errors)


@pytest.mark.parametrize(
    "relative_link",
    (
        Path("engine-capabilities/evidence/linked.json"),
        Path("engine-capabilities/migration-sources/linked.json"),
        Path("engine-capabilities/migration-reports/linked.json"),
    ),
)
def test_artifact_validator_rejects_symlinked_governed_documents(
    tmp_path: Path, relative_link: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _copy_engine_artifacts(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    link = root / "artifacts/gen9ou/m2" / relative_link
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"symlink creation unavailable: {error}")

    opened_targets: list[Path] = []
    load_json_strict = schema_checker.load_json_strict

    def guarded_load(path: Path) -> object:
        if Path(path).resolve(strict=False) == outside.resolve(strict=False):
            opened_targets.append(Path(path))
        return load_json_strict(path)

    monkeypatch.setattr(schema_checker, "load_json_strict", guarded_load)
    errors = _validate_engine_capability_artifacts(root)

    normalized = relative_link.as_posix()
    assert any(
        normalized in error.replace("\\", "/")
        and "symlinked artifact paths are not allowed" in error
        for error in errors
    )
    assert opened_targets == []


def test_artifact_validator_rejects_symlinked_governed_directory_before_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _copy_engine_artifacts(tmp_path)
    capability_root = root / "artifacts/gen9ou/m2/engine-capabilities"
    outside_directory = tmp_path / "outside-evidence"
    outside_directory.mkdir()
    outside = outside_directory / "linked.json"
    outside.write_text("{}", encoding="utf-8")
    evidence_directory = capability_root / "evidence"
    try:
        os.symlink(outside_directory, evidence_directory, target_is_directory=True)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"symlink creation unavailable: {error}")

    opened_targets: list[Path] = []
    load_json_strict = schema_checker.load_json_strict

    def guarded_load(path: Path) -> object:
        if Path(path).resolve(strict=False) == outside.resolve(strict=False):
            opened_targets.append(Path(path))
        return load_json_strict(path)

    monkeypatch.setattr(schema_checker, "load_json_strict", guarded_load)
    errors = _validate_engine_capability_artifacts(root)

    assert any(
        "engine-capabilities/evidence" in error.replace("\\", "/")
        and "symlinked artifact paths are not allowed" in error
        for error in errors
    )
    assert opened_targets == []


def test_reparse_point_metadata_is_rejected_without_symlink_privilege(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reparse_flag = 0x40000000
    monkeypatch.setattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", reparse_flag, raising=False)

    regular = SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0)
    reparse = SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=reparse_flag)
    symlink = SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0)

    assert not schema_checker._is_link_or_reparse_entry(Path("regular.json"), regular)
    assert schema_checker._is_link_or_reparse_entry(Path("reparse.json"), reparse)
    assert schema_checker._is_link_or_reparse_entry(Path("symlink.json"), symlink)


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
