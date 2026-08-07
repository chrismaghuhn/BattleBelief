"""Create the six-cell v2 legal-choice artifact index."""

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
from battlebelief_runtime.adapters.poke_engine.native_probe import load_fixture_bundle  # noqa: E402
from tools.build_poke_engine_wheel import (  # noqa: E402
    FEATURES,
    LEGAL_CHOICE_ADAPTER_VERSION,
    LEGAL_CHOICE_INDEX_SCHEMA_ID,
    LEGAL_CHOICE_RELEASE_TAG,
    inspect_wheel,
)

EXPECTED_CELLS = frozenset(
    f"{operating_system}-x86_64-cp{minor}"
    for operating_system in ("ubuntu-24.04", "windows-2025")
    for minor in ("312", "313", "314")
)


class ArtifactIndexV2Error(RuntimeError):
    """A stable v2 artifact-index closure failure."""


def _fail(message: str) -> NoReturn:
    raise ArtifactIndexV2Error(message)


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


def _build_cell(
    build: Mapping[str, Any], *, source_digest: str, wheel_path: Path
) -> dict[str, Any]:
    python = build.get("python")
    distribution = build.get("distribution")
    wheel = build.get("wheel")
    if not isinstance(python, dict) or not isinstance(distribution, dict) or not isinstance(wheel, dict):
        _fail("build manifest structure differs")
    cell_id = build.get("cell_id")
    if not isinstance(cell_id, str) or cell_id not in EXPECTED_CELLS:
        _fail("build cell identity differs")
    expected_target = (
        "x86_64-unknown-linux-gnu"
        if build.get("operating_system") == "ubuntu-24.04"
        else "x86_64-pc-windows-msvc"
    )
    expected_build = {
        "schema_version": 2,
        "schema_id": "urn:battlebelief:schema:manifest:engine-build:v2",
        "source_schema_id": "urn:battlebelief:schema:manifest:engine-source:v2",
        "source_manifest_digest": source_digest,
        "rust_toolchain": f"1.83.0-{expected_target}",
        "maturin_version": "1.7.1",
        "locked": True,
        "no_default_features": True,
        "features": list(FEATURES),
        "target_triple": expected_target,
        "architecture": "x86_64",
        "adapter_version": LEGAL_CHOICE_ADAPTER_VERSION,
        "canonicalization_profile": "rfc8785-jcs-v1",
    }
    if any(build.get(key) != value for key, value in expected_build.items()):
        _fail("build manifest identity differs")
    if distribution != {"name": "poke-engine", "version": "0.0.49"}:
        _fail("build distribution identity differs")
    if build.get("downstream_patch_digest", "").startswith("sha256:") is False:
        _fail("downstream patch identity differs")
    expected = inspect_wheel(
        wheel_path,
        python_tag=str(python.get("python_tag")),
        abi_tag=str(python.get("abi_tag")),
        platform_tag=str(python.get("platform_tag")),
        distribution_version="0.0.49",
    )
    if expected != wheel:
        _fail("wheel manifest differs")
    return {
        "cell_id": cell_id,
        "source_manifest_digest": source_digest,
        "build_manifest_digest": manifest_digest(build),
        "wheel_filename": wheel["filename"],
        "wheel_size": wheel["size"],
        "wheel_sha256": wheel["sha256"],
        "distribution_name": "poke-engine",
        "distribution_version": "0.0.49",
        "python_tag": python["python_tag"],
        "abi_tag": python["abi_tag"],
        "platform_tag": python["platform_tag"],
        "operating_system": build["operating_system"],
        "architecture": "x86_64",
        "features": FEATURES,
        "adapter_version": LEGAL_CHOICE_ADAPTER_VERSION,
        "release_tag": LEGAL_CHOICE_RELEASE_TAG,
        "release_asset_url": (
            "https://github.com/chrismaghuhn/BattleBelief/releases/download/"
            f"{LEGAL_CHOICE_RELEASE_TAG}/{wheel['filename']}"
        ),
    }


def _evidence_for_cell(
    evidence: Mapping[str, Any], cell: Mapping[str, Any], *, fixture_digest: str
) -> dict[str, str]:
    expected = {
        "schema_version": 2,
        "cell_id": cell["cell_id"],
        "classification": "healthy",
        "source_manifest_digest": cell["source_manifest_digest"],
        "build_manifest_digest": cell["build_manifest_digest"],
        "wheel_sha256": cell["wheel_sha256"],
        "fixture_digest": fixture_digest,
    }
    if any(evidence.get(key) != value for key, value in expected.items()):
        _fail("sentinel evidence differs")
    fields = ("configuration_digest", "result_digest")
    if any(not isinstance(evidence.get(key), str) for key in fields):
        _fail("sentinel evidence differs")
    return {key: str(evidence[key]) for key in fields}


def create_artifact_index_v2(
    *,
    source_manifest: Mapping[str, Any],
    build_manifests: Sequence[Mapping[str, Any]],
    wheel_paths: Mapping[str, Path],
    fixture_digest: str,
    availability_status: str,
    evidence_by_cell: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, Any]:
    if source_manifest.get("schema_id") != "urn:battlebelief:schema:manifest:engine-source:v2":
        _fail("source manifest identity differs")
    if availability_status not in ("candidate", "available"):
        _fail("availability status differs")
    source_digest = manifest_digest(source_manifest)
    cells = [
        _build_cell(
            build,
            source_digest=source_digest,
            wheel_path=wheel_paths[str(build.get("wheel", {}).get("filename"))],
        )
        for build in build_manifests
    ]
    identifiers = [str(cell["cell_id"]) for cell in cells]
    if len(cells) != 6 or len(set(identifiers)) != 6 or set(identifiers) != EXPECTED_CELLS:
        _fail("build cell closure differs")
    wheel_digests = [str(cell["wheel_sha256"]) for cell in cells]
    if len(set(wheel_digests)) != 6:
        _fail("wheel identities are reused")
    patch_digest = source_manifest.get("downstream_patch", {}).get("sha256")
    if not isinstance(patch_digest, str):
        _fail("downstream patch identity differs")
    if availability_status == "available":
        if evidence_by_cell is None or set(evidence_by_cell) != EXPECTED_CELLS:
            _fail("sentinel evidence closure differs")
        evidence_values = {
            str(cell["cell_id"]): _evidence_for_cell(
                evidence_by_cell[str(cell["cell_id"])], cell, fixture_digest=fixture_digest
            )
            for cell in cells
        }
    else:
        candidate_result = manifest_digest({"profile": LEGAL_CHOICE_ADAPTER_VERSION})
        evidence_values = {
            str(cell["cell_id"]): {
                "configuration_digest": fixture_digest,
                "result_digest": candidate_result,
            }
            for cell in cells
        }
    for cell in cells:
        values = evidence_values[str(cell["cell_id"])]
        cell.update(
            {
                "sentinel_fixture_digest": fixture_digest,
                "sentinel_result_digest": values["result_digest"],
                "sentinel_configuration_digest": values["configuration_digest"],
                "availability_status": availability_status,
            }
        )
    cells.sort(key=lambda cell: str(cell["cell_id"]))
    return {
        "schema_version": 2,
        "schema_id": LEGAL_CHOICE_INDEX_SCHEMA_ID,
        "manifest_id": "poke-engine-artifact-index-v2-legal-choices",
        "source_schema_id": "urn:battlebelief:schema:manifest:engine-source:v2",
        "build_schema_id": "urn:battlebelief:schema:manifest:engine-build:v2",
        "source_manifest_digest": source_digest,
        "source_tree_digest": source_manifest.get("source_tree_digest"),
        "downstream_patch_digest": patch_digest,
        "repository_url": "https://github.com/chrismaghuhn/BattleBelief",
        "release_tag": LEGAL_CHOICE_RELEASE_TAG,
        "release_prerelease": True,
        "release_assets_immutable": True,
        "cells": cells,
        "canonicalization_profile": "rfc8785-jcs-v1",
    }


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
        manifest_paths = sorted(args.input_root.rglob("engine-build-*.json"))
        if len(manifest_paths) != 6:
            _fail("build manifest closure differs")
        builds = [_strict_canonical(path) for path in manifest_paths]
        wheel_paths = {
            path.name: path for path in args.input_root.rglob("*.whl")
        }
        if len(wheel_paths) != 6:
            _fail("wheel closure differs")
        bundle = load_fixture_bundle(args.fixture_root)
        evidence_by_cell = None
        if args.evidence_root is not None:
            evidence_paths = sorted(args.evidence_root.rglob("legal-choice-sentinel-*.json"))
            evidence_by_cell = {
                str(document.get("cell_id")): _strict_canonical(path)
                for path in evidence_paths
                for document in [_strict_canonical(path)]
            }
        index = create_artifact_index_v2(
            source_manifest=source,
            build_manifests=builds,
            wheel_paths=wheel_paths,
            fixture_digest=bundle.fixture_digest,
            availability_status=args.availability_status,
            evidence_by_cell=evidence_by_cell,
        )
        if args.output.exists():
            _fail("output already exists")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonicalize(index) + b"\n")
    except (ArtifactIndexV2Error, KeyError, ValueError, OSError):
        print("v2 artifact index creation failed", file=sys.stderr)
        return 1
    print(f"artifact_index_digest={manifest_digest(index)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
