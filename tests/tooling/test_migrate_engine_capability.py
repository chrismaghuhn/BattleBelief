from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from tools.canonicalize_manifest import manifest_digest
from tools.migrate_engine_capability import migrate_v1_document

from battlebelief_core.domain import CapabilityMigrationClosure

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
        "source_schema_id",
        "migrator_id",
        "migrator_version",
        "source_digest",
        "loss_codes",
        "loss_report_digest",
        "target_digest",
        "loss",
    }
    assert migrated["migration"]["loss_report_digest"] == report["loss_report_digest"]
    assert report["target_digest"] == manifest_digest(migrated)
    projection = {
        name: report[name]
        for name in (
            "source_schema_id",
            "source_digest",
            "migrator_id",
            "migrator_version",
            "loss_codes",
            "loss",
        )
    }
    assert report["loss_report_digest"] == manifest_digest(projection)
    changed_projection = deepcopy(projection)
    changed_projection["loss"]["exact"] += 1
    assert manifest_digest(changed_projection) != migrated["migration"]["loss_report_digest"]
    changed_target = deepcopy(migrated)
    changed_target["migration"]["source_digest"] = "sha256:" + "0" * 64
    assert manifest_digest(changed_target) != report["target_digest"]


def test_migration_closure_is_a_curated_immutable_core_value() -> None:
    closure = CapabilityMigrationClosure(
        source_schema_id="urn:battlebelief:schema:manifest:engine-capability:v1",
        source_digest="sha256:" + "a" * 64,
        migrator_id="battlebelief.engine-capability-v1-to-v2",
        migrator_version="1",
        loss_codes=("approximated", "exact", "known-divergences", "unsupported"),
        loss_report_digest="sha256:" + "b" * 64,
    )

    assert closure.document()["loss_codes"] == [
        "approximated",
        "exact",
        "known-divergences",
        "unsupported",
    ]
