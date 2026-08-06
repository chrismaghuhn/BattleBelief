from __future__ import annotations

import json
from pathlib import Path

from tools.migrate_engine_capability import migrate_v1_document

ROOT = Path(__file__).resolve().parents[2]


def _target_binding() -> dict[str, object]:
    manifest = json.loads(
        (
            ROOT
            / "artifacts"
            / "gen9ou"
            / "m2"
            / "engine-capabilities"
            / "engine-capability-v2-unqualified.json"
        ).read_text(encoding="utf-8")
    )
    return {
        name: manifest[name]
        for name in (
            "engine_source_manifest_digest",
            "artifact_index_digest",
            "environment_bindings",
            "canonicalization_contract_digest",
        )
    }


def test_v1_migration_is_fail_closed_and_records_deterministic_loss() -> None:
    source = json.loads(
        (ROOT / "schemas" / "examples" / "engine-capability.example.json").read_text(
            encoding="utf-8"
        )
    )
    catalog = json.loads(
        (ROOT / "artifacts" / "gen9ou" / "m2" / "engine-capability-catalog-v1.json").read_text(
            encoding="utf-8"
        )
    )

    migrated, report = migrate_v1_document(source, catalog, _target_binding())

    assert migrated["schema_version"] == 2
    assert migrated["claims"] == []
    assert report["migrator_id"] == "battlebelief.engine-capability-v1-to-v2"
    assert report["migrator_version"] == "1"
    assert report["loss"] == {
        "exact": len(source["exact"]),
        "approximated": len(source["approximated"]),
        "unsupported": len(source["unsupported"]),
        "known_divergences": len(source["known_divergences"]),
    }
    assert set(report) == {
        "migrator_id",
        "migrator_version",
        "source_digest",
        "target_digest",
        "loss",
    }
