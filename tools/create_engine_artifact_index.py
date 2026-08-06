"""Create the six-cell poke-engine artifact index from verified build outputs."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from battlebelief_core.canonicalization import canonicalize, manifest_digest  # noqa: E402
from battlebelief_runtime.adapters.poke_engine.errors import EngineArtifactError  # noqa: E402
from battlebelief_runtime.adapters.poke_engine.native_probe import (  # noqa: E402
    healthy_probe_result,
    load_fixture_bundle,
)
from tools.build_poke_engine_wheel import inspect_wheel  # noqa: E402

RELEASE_TAG = "engine-poke-engine-v0.0.48-bcf13823-v1"
FEATURES = ["poke-engine/gen9", "poke-engine/terastallization"]
EXPECTED_CELLS = frozenset(
    f"{operating_system}-x86_64-cp{minor}"
    for operating_system in ("ubuntu-24.04", "windows-2025")
    for minor in ("312", "313", "314")
)


class ArtifactIndexError(RuntimeError):
    """A stable artifact-index closure failure."""


def _fail(message: str) -> NoReturn:
    raise ArtifactIndexError(message)


def _build_cell(build: Mapping[str, Any]) -> dict[str, Any]:
    python = build.get("python")
    distribution = build.get("distribution")
    wheel = build.get("wheel")
    if (
        not isinstance(python, dict)
        or not isinstance(distribution, dict)
        or not isinstance(wheel, dict)
    ):
        _fail("build manifest structure differs")
    cell_id = build.get("cell_id")
    if not isinstance(cell_id, str):
        _fail("build cell identity differs")
    expected_target = (
        "x86_64-unknown-linux-gnu"
        if build.get("operating_system") == "ubuntu-24.04"
        else "x86_64-pc-windows-msvc"
    )
    expected_build = {
        "schema_version": 1,
        "schema_id": "urn:battlebelief:schema:manifest:engine-build:v1",
        "rust_toolchain": f"1.83.0-{expected_target}",
        "maturin_version": "1.7.1",
        "locked": True,
        "no_default_features": True,
        "features": FEATURES,
        "target_triple": expected_target,
        "architecture": "x86_64",
        "adapter_version": "battlebelief-poke-engine-v1",
        "canonicalization_profile": "rfc8785-jcs-v1",
    }
    if any(build.get(key) != value for key, value in expected_build.items()):
        _fail("build manifest identity differs")
    if distribution != {"name": "poke-engine", "version": "0.0.48"}:
        _fail("build distribution identity differs")
    return {
        "cell_id": cell_id,
        "source_manifest_digest": build.get("source_manifest_digest"),
        "build_manifest_digest": manifest_digest(build),
        "wheel_filename": wheel.get("filename"),
        "wheel_size": wheel.get("size"),
        "wheel_sha256": wheel.get("sha256"),
        "distribution_name": "poke-engine",
        "distribution_version": "0.0.48",
        "python_tag": python.get("python_tag"),
        "abi_tag": python.get("abi_tag"),
        "platform_tag": python.get("platform_tag"),
        "operating_system": build.get("operating_system"),
        "architecture": "x86_64",
        "features": FEATURES,
        "adapter_version": "battlebelief-poke-engine-v1",
        "release_tag": RELEASE_TAG,
        "release_asset_url": (
            "https://github.com/chrismaghuhn/BattleBelief/releases/download/"
            f"{RELEASE_TAG}/{wheel.get('filename')}"
        ),
    }


def _verify_evidence(
    *,
    cell: Mapping[str, Any],
    evidence: Mapping[str, Any],
    fixture_digest: str,
    configuration_digest: str,
    result_digest: str,
) -> None:
    expected = {
        "schema_version": 1,
        "cell_id": cell.get("cell_id"),
        "classification": "healthy",
        "source_manifest_digest": cell.get("source_manifest_digest"),
        "build_manifest_digest": cell.get("build_manifest_digest"),
        "wheel_sha256": cell.get("wheel_sha256"),
        "fixture_digest": fixture_digest,
        "configuration_digest": configuration_digest,
        "result_digest": result_digest,
    }
    if dict(evidence) != expected:
        _fail("sentinel evidence differs")


def create_artifact_index(
    *,
    source_manifest: Mapping[str, Any],
    build_manifests: Sequence[Mapping[str, Any]],
    fixture_digest: str,
    configuration_digest: str,
    result_digest: str,
    availability_status: str,
    evidence_by_cell: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Create a candidate or fully evidence-closed artifact index."""

    fixed_source = {
        "schema_version": 1,
        "schema_id": "urn:battlebelief:schema:manifest:engine-source:v1",
        "repository_url": "https://github.com/pmariglia/poke-engine",
        "commit": "bcf13823abc162a608e187b26bbf683f759f385e",
        "observed_tag": "v0.0.48",
        "tag_peeled_commit": "bcf13823abc162a608e187b26bbf683f759f385e",
        "git_tree_oid": "74d10964d7470b2b9d92ba734550825388178d2d",
        "source_scope": "full_git_tree",
        "clean_tree": True,
        "canonicalization_profile": "rfc8785-jcs-v1",
    }
    if any(source_manifest.get(key) != value for key, value in fixed_source.items()):
        _fail("source manifest identity differs")
    if availability_status not in ("candidate", "available"):
        _fail("availability status differs")
    cells = [_build_cell(build) for build in build_manifests]
    identifiers = [cell["cell_id"] for cell in cells]
    if len(cells) != 6 or len(set(identifiers)) != 6 or set(identifiers) != EXPECTED_CELLS:
        _fail("build cell closure differs")
    source_digest = manifest_digest(source_manifest)
    if any(cell["source_manifest_digest"] != source_digest for cell in cells):
        _fail("build source closure differs")
    if availability_status == "available":
        if evidence_by_cell is None or set(evidence_by_cell) != EXPECTED_CELLS:
            _fail("sentinel evidence closure differs")
        for cell in cells:
            _verify_evidence(
                cell=cell,
                evidence=evidence_by_cell[str(cell["cell_id"])],
                fixture_digest=fixture_digest,
                configuration_digest=configuration_digest,
                result_digest=result_digest,
            )
    for cell in cells:
        cell.update(
            {
                "sentinel_fixture_digest": fixture_digest,
                "sentinel_result_digest": result_digest,
                "sentinel_configuration_digest": configuration_digest,
                "availability_status": availability_status,
            }
        )
    cells.sort(key=lambda cell: str(cell["cell_id"]))
    return {
        "schema_version": 1,
        "schema_id": "urn:battlebelief:schema:manifest:engine-artifact-index:v1",
        "manifest_id": "poke-engine-artifact-index-v1",
        "source_schema_id": "urn:battlebelief:schema:manifest:engine-source:v1",
        "build_schema_id": "urn:battlebelief:schema:manifest:engine-build:v1",
        "source_manifest_digest": source_digest,
        "repository_url": "https://github.com/chrismaghuhn/BattleBelief",
        "release_tag": RELEASE_TAG,
        "release_prerelease": True,
        "release_assets_immutable": True,
        "cells": cells,
        "canonicalization_profile": "rfc8785-jcs-v1",
    }


def _strict_canonical(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                _fail("input has duplicate keys")
            result[key] = value
        return result

    try:
        raw = path.read_bytes()
        value = json.loads(raw, object_pairs_hook=reject_duplicates)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _fail("input is unreadable")
    if not isinstance(value, dict) or raw != canonicalize(value) + b"\n":
        _fail("input is not canonical")
    return value


def _load_builds_and_verify_wheels(input_root: Path) -> list[dict[str, Any]]:
    manifest_paths = sorted(input_root.rglob("engine-build-*.json"))
    if len(manifest_paths) != 6:
        _fail("build manifest closure differs")
    builds = [_strict_canonical(path) for path in manifest_paths]
    wheel_paths = list(input_root.rglob("*.whl"))
    for build in builds:
        python = build.get("python")
        wheel = build.get("wheel")
        if not isinstance(python, dict) or not isinstance(wheel, dict):
            _fail("build manifest structure differs")
        matches = [path for path in wheel_paths if path.name == wheel.get("filename")]
        if len(matches) != 1:
            _fail("wheel closure differs")
        inspected = inspect_wheel(
            matches[0],
            python_tag=str(python.get("python_tag")),
            abi_tag=str(python.get("abi_tag")),
            platform_tag=str(python.get("platform_tag")),
        )
        if inspected != wheel:
            _fail("wheel manifest differs")
    return builds


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--availability-status", choices=("candidate", "available"), required=True)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        source = _strict_canonical(args.source_manifest)
        builds = _load_builds_and_verify_wheels(args.input_root)
        bundle = load_fixture_bundle(args.fixture_root)
        result_digest = manifest_digest(healthy_probe_result(bundle))
        evidence_by_cell = None
        if args.evidence_root is not None:
            evidence_paths = sorted(args.evidence_root.rglob("sentinel-*.json"))
            evidence_documents = [_strict_canonical(path) for path in evidence_paths]
            evidence_by_cell = {
                str(document.get("cell_id")): document for document in evidence_documents
            }
        index = create_artifact_index(
            source_manifest=source,
            build_manifests=builds,
            fixture_digest=bundle.fixture_digest,
            configuration_digest=bundle.configuration_digest,
            result_digest=result_digest,
            availability_status=args.availability_status,
            evidence_by_cell=evidence_by_cell,
        )
        if args.output.exists():
            _fail("output already exists")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonicalize(index) + b"\n")
    except (ArtifactIndexError, EngineArtifactError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"artifact_index_digest={manifest_digest(index)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
