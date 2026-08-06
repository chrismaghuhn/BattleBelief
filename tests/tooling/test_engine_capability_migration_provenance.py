from __future__ import annotations

import json
import shutil
from pathlib import Path

from tools.check_schemas import _validate_engine_capability_artifacts
from tools.migrate_engine_capability import migrate_v1_document

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "artifacts/gen9ou/m2/engine-capability-catalog-v1.json"
INITIAL_MANIFEST = (
    ROOT / "artifacts/gen9ou/m2/engine-capabilities/engine-capability-v2-unqualified.json"
)
V1_SOURCE = ROOT / "schemas/examples/engine-capability.example.json"


def _document(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _target_binding() -> dict[str, object]:
    manifest = _document(INITIAL_MANIFEST)
    return {
        name: manifest[name]
        for name in (
            "engine_source_manifest_digest",
            "artifact_index_digest",
            "environment_bindings",
            "canonicalization_contract_digest",
        )
    }


def _write_migration_repository(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    shutil.copytree(ROOT / "schemas", tmp_path / "schemas")
    artifact_root = tmp_path / "artifacts/gen9ou/m2"
    shutil.copytree(ROOT / "artifacts/gen9ou/m2/engine", artifact_root / "engine")
    shutil.copy2(CATALOG, artifact_root / CATALOG.name)
    capability_root = artifact_root / "engine-capabilities"
    capability_root.mkdir()
    shutil.copy2(INITIAL_MANIFEST, capability_root / INITIAL_MANIFEST.name)

    source = _document(V1_SOURCE)
    catalog = _document(CATALOG)
    target, report = migrate_v1_document(source, catalog, _target_binding())
    source_directory = capability_root / "migration-sources"
    report_directory = capability_root / "migration-reports"
    source_directory.mkdir()
    report_directory.mkdir()
    source_path = source_directory / f"{report['source_document_id']}.json"
    report_path = report_directory / f"{report['report_id']}.json"
    target_path = capability_root / "engine-capability-v2-migrated.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    report_path.write_text(json.dumps(report), encoding="utf-8")
    target_path.write_text(json.dumps(target), encoding="utf-8")
    return tmp_path, target_path, source_path, report_path


def test_repository_validator_resolves_every_migration_identity(tmp_path: Path) -> None:
    root, target_path, source_path, report_path = _write_migration_repository(tmp_path)
    assert _validate_engine_capability_artifacts(root) == []

    mutations = (
        (
            "migration source document is missing",
            lambda target, source, report: source_path.unlink(),
        ),
        (
            "source digest",
            lambda target, source, report: target["migration"].__setitem__(
                "source_digest", "sha256:" + "0" * 64
            ),
        ),
        (
            "loss report is missing",
            lambda target, source, report: report_path.unlink(),
        ),
        (
            "loss report digest does not match report projection",
            lambda target, source, report: report["loss"].__setitem__("exact", 999),
        ),
        (
            "target digest does not match manifest",
            lambda target, source, report: report.__setitem__(
                "target_digest", "sha256:" + "f" * 64
            ),
        ),
    )
    for expected, mutate in mutations:
        root, target_path, source_path, report_path = _write_migration_repository(
            tmp_path / expected
        )
        target = _document(target_path)
        source = _document(source_path)
        report = _document(report_path)
        mutate(target, source, report)
        target_path.write_text(json.dumps(target), encoding="utf-8")
        if report_path.exists():
            report_path.write_text(json.dumps(report), encoding="utf-8")
        errors = _validate_engine_capability_artifacts(root)
        assert any(expected in error for error in errors)
