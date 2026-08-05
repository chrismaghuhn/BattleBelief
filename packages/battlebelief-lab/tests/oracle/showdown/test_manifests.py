from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from tools.canonicalize_manifest import manifest_digest

from battlebelief_lab.oracle.showdown import (
    OracleFailureClass,
    ShowdownBuildManifest,
    ShowdownSourceManifest,
)

ROOT = Path(__file__).resolve().parents[5]
_DIGEST = "sha256:" + "0" * 64
_RULESET_EXTRACTOR_DIGEST = (
    "sha256:82ae637f73a81aa9bafeab27fc0bc057d1fc281660985898a9c0006159e56f58"
)


def _ruleset_snapshot() -> dict[str, object]:
    return {
        "schema_version": 1,
        "extractor_id": "battlebelief-showdown-ruleset-extractor-v1",
        "extractor_digest": _RULESET_EXTRACTOR_DIGEST,
        "format": {
            "id": "gen9ou",
            "name": "[Gen 9] OU",
            "mod": "gen9",
            "game_type": "singles",
            "gen": 9,
            "rated": True,
            "ruleset": ["Standard"],
            "base_ruleset": [],
            "banlist": ["Uber"],
            "restricted": [],
            "unbanlist": [],
        },
        "resolved_rule_table": {
            "entries": [{"key": "standard", "value": ""}],
            "value_rules": [{"key": "evlimit", "value": "Auto"}],
            "complex_bans": [],
            "complex_team_bans": [],
            "tag_rules": [{"prefix": "-", "tag": "uber"}],
            "team_constraints": {
                "ev_limit": 510,
                "max_level": 100,
                "max_move_count": 4,
                "max_team_size": 6,
                "min_level": 1,
                "min_source_gen": 9,
                "min_team_size": 1,
            },
        },
    }


def _records() -> list[dict[str, object]]:
    return _source_document()["source_files"]  # type: ignore[return-value]


def _source_document() -> dict[str, object]:
    return json.loads(
        (ROOT / "schemas/examples/showdown-oracle-source.example.json").read_text(encoding="utf-8")
    )


def _build_document() -> dict[str, object]:
    source = ShowdownSourceManifest.from_dict(_source_document())
    records = [{"path": "dist/sim/battle-stream.js", "digest": _DIGEST, "size": 42}]
    dependency_files = [
        {
            "kind": "file",
            "path": "node_modules/test-runtime/index.js",
            "digest": _DIGEST,
            "size": 42,
        }
    ]
    snapshot = _ruleset_snapshot()
    return {
        "schema_version": 1,
        "manifest_id": "showdown-oracle-build-test-only",
        "source_manifest_digest": source.digest,
        "commit": source.commit,
        "node_version": "22.23.2",
        "npm_version": "10.9.8",
        "probe_role": "candidate",
        "os": "windows",
        "architecture": "x86_64",
        "npm_ci_argv": ["npm", "ci", "--no-audit", "--no-fund"],
        "npm_build_argv": ["npm", "run", "build"],
        "simulator_argv": ["node", "pokemon-showdown", "--skip-build", "simulate-battle"],
        "npm_config": {"audit": "false", "fund": "false", "ignore-scripts": "false"},
        "dependency_tree_digest": _DIGEST,
        "dependency_files": dependency_files,
        "dependency_files_digest": manifest_digest(dependency_files),
        "dist_files": records,
        "dist_tree_digest": manifest_digest(records),
        "format_id": "gen9ou",
        "ruleset_snapshot": snapshot,
        "ruleset_snapshot_digest": manifest_digest(snapshot),
        "format_identity_digest": manifest_digest(snapshot["format"]),
        "adapter_version": "showdown-oracle-v1",
        "canonicalization_profile": "rfc8785-jcs-v1",
        "schema_id": "urn:battlebelief:schema:manifest:showdown-oracle-build:v1",
    }


def test_build_manifest_requires_a_self_resolving_ruleset_closure() -> None:
    document = _build_document()
    document["ruleset_snapshot"]["format"]["banlist"] = ["Different Ban"]  # type: ignore[index]

    with pytest.raises(ValueError, match="ruleset_snapshot_digest"):
        ShowdownBuildManifest.from_dict(document)


def test_build_manifest_requires_the_exact_ruleset_extractor() -> None:
    document = _build_document()
    document["ruleset_snapshot"]["extractor_digest"] = _DIGEST  # type: ignore[index]
    document["ruleset_snapshot_digest"] = manifest_digest(document["ruleset_snapshot"])

    with pytest.raises(ValueError, match="extractor digest"):
        ShowdownBuildManifest.from_dict(document)


def test_failure_taxonomy_is_closed_and_stable() -> None:
    assert {failure.value for failure in OracleFailureClass} == {
        "node_not_found",
        "node_version_not_approved",
        "source_missing",
        "source_commit_mismatch",
        "source_dirty",
        "license_mismatch",
        "lockfile_mismatch",
        "npm_version_mismatch",
        "build_failed",
        "build_output_missing",
        "start_timeout",
        "write_timeout",
        "response_timeout",
        "fixture_timeout",
        "malformed_output",
        "protocol_desynchronization",
        "ruleset_rejected",
        "process_crash",
        "unexpected_exit_code",
        "shutdown_failed",
        "orphaned_child_process",
        "external_network_attempt",
        "input_too_large",
        "output_too_large",
    }


def test_source_manifest_round_trips_with_stable_canonical_bytes() -> None:
    document = _source_document()
    manifest = ShowdownSourceManifest.from_dict(document)

    assert manifest.to_dict() == document
    assert (
        manifest.canonical_bytes()
        == ShowdownSourceManifest.from_dict(
            json.loads(json.dumps(document, sort_keys=True))
        ).canonical_bytes()
    )
    assert manifest.digest == manifest_digest(document)


def test_source_manifest_mutation_changes_digest() -> None:
    document = _source_document()
    mutated = _source_document()
    mutated["manifest_id"] = "showdown-oracle-source-6a1836dd-other"

    assert (
        ShowdownSourceManifest.from_dict(document).digest
        != ShowdownSourceManifest.from_dict(mutated).digest
    )


def test_build_schema_and_parser_reject_an_unapproved_role_version_pair() -> None:
    document = _build_document()
    document["node_version"] = "22.23.1"
    schema = json.loads(
        (ROOT / "schemas/manifests/showdown-oracle-build.schema.json").read_text(encoding="utf-8")
    )

    assert list(Draft202012Validator(schema).iter_errors(document))
    with pytest.raises(ValueError):
        ShowdownBuildManifest.from_dict(document)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("commit", "0" * 40),
        ("package_lock_digest", _DIGEST),
        ("declared_node_version", ""),
    ],
)
def test_source_manifest_rejects_wrong_commit_lock_or_declared_node(
    field: str, value: object
) -> None:
    document = _source_document()
    document[field] = value

    with pytest.raises(ValueError):
        ShowdownSourceManifest.from_dict(document)


@pytest.mark.parametrize(
    "records",
    [
        list(reversed(_records())),
        [_records()[0], _records()[0]],
        [{"path": "../LICENSE", "digest": _DIGEST, "size": 1}],
        [{"path": "/LICENSE", "digest": _DIGEST, "size": 1}],
    ],
)
def test_source_manifest_rejects_unsorted_duplicate_or_unsafe_file_records(
    records: list[dict[str, object]],
) -> None:
    document = _source_document()
    document["source_files"] = records
    document["source_tree_digest"] = manifest_digest(records)

    with pytest.raises(ValueError):
        ShowdownSourceManifest.from_dict(document)


def test_manifest_rejects_mismatched_derived_digest() -> None:
    source = _source_document()
    source["source_tree_digest"] = _DIGEST
    with pytest.raises(ValueError):
        ShowdownSourceManifest.from_dict(source)


@pytest.mark.parametrize(
    "field",
    [
        "pid",
        "port",
        "hostname",
        "timestamp",
        "wall_time",
        "source_path",
        "build_path",
        "local_path",
    ],
)
def test_manifests_reject_operational_fields_after_otherwise_valid_data(field: str) -> None:
    source = _source_document()
    build = _build_document()
    source[field] = "operational-value"
    build[field] = "operational-value"
    source_schema = json.loads(
        (ROOT / "schemas/manifests/showdown-oracle-source.schema.json").read_text(encoding="utf-8")
    )
    build_schema = json.loads(
        (ROOT / "schemas/manifests/showdown-oracle-build.schema.json").read_text(encoding="utf-8")
    )

    assert list(Draft202012Validator(source_schema).iter_errors(source))
    assert list(Draft202012Validator(build_schema).iter_errors(build))
    with pytest.raises(ValueError):
        ShowdownSourceManifest.from_dict(source)
    with pytest.raises(ValueError):
        ShowdownBuildManifest.from_dict(build)


def test_source_manifest_rejects_self_consistent_historical_file_mutation() -> None:
    source = _source_document()
    source["source_files"][0]["digest"] = _DIGEST  # type: ignore[index]
    source["source_tree_digest"] = manifest_digest(source["source_files"])

    with pytest.raises(ValueError):
        ShowdownSourceManifest.from_dict(source)


def test_new_manifest_examples_pass_and_invalid_examples_fail() -> None:
    schema_root = ROOT / "schemas"
    mappings = {
        "showdown-oracle-source.example.json": "showdown-oracle-source.schema.json",
        "showdown-oracle-build.example.json": "showdown-oracle-build.schema.json",
    }
    for example_name, schema_name in mappings.items():
        schema = json.loads((schema_root / "manifests" / schema_name).read_text(encoding="utf-8"))
        example = json.loads((schema_root / "examples" / example_name).read_text(encoding="utf-8"))
        assert list(Draft202012Validator(schema).iter_errors(example)) == []
        if example_name == "showdown-oracle-build.example.json":
            assert ShowdownBuildManifest.from_dict(example).to_dict() == example

        invalid_name = example_name.replace(".example.json", ".invalid.json")
        invalid = json.loads(
            (schema_root / "examples" / "invalid" / invalid_name).read_text(encoding="utf-8")
        )
        assert list(Draft202012Validator(schema).iter_errors(invalid))


def test_manifest_input_is_not_mutated() -> None:
    document = _source_document()
    source_files = document["source_files"]
    ShowdownSourceManifest.from_dict(document)
    assert document["source_files"] is source_files
