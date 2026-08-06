from __future__ import annotations

from typing import Any

import pytest
from tools.create_engine_artifact_index import (
    ArtifactIndexError,
    create_artifact_index,
)

from battlebelief_core.canonicalization import manifest_digest

DIGEST = "sha256:" + "a" * 64


def _source() -> dict[str, Any]:
    return {
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


def _builds() -> list[dict[str, Any]]:
    builds = []
    for operating_system in ("ubuntu-24.04", "windows-2025"):
        windows = operating_system == "windows-2025"
        target = "x86_64-pc-windows-msvc" if windows else "x86_64-unknown-linux-gnu"
        platform = "win_amd64" if windows else "linux_x86_64"
        abi = "none" if windows else None
        for minor in ("312", "313", "314"):
            cell_id = f"{operating_system}-x86_64-cp{minor}"
            abi_tag = abi or f"cp{minor}"
            filename = f"poke_engine-0.0.48-cp{minor}-{abi_tag}-{platform}.whl"
            builds.append(
                {
                    "schema_version": 1,
                    "schema_id": "urn:battlebelief:schema:manifest:engine-build:v1",
                    "cell_id": cell_id,
                    "source_manifest_digest": manifest_digest(_source()),
                    "rust_toolchain": f"1.83.0-{target}",
                    "maturin_version": "1.7.1",
                    "locked": True,
                    "no_default_features": True,
                    "features": ["poke-engine/gen9", "poke-engine/terastallization"],
                    "target_triple": target,
                    "operating_system": operating_system,
                    "architecture": "x86_64",
                    "python": {
                        "implementation": "CPython",
                        "version": f"3.{minor[-2:]}.1",
                        "python_tag": f"cp{minor}",
                        "abi_tag": abi_tag,
                        "platform_tag": platform,
                    },
                    "distribution": {"name": "poke-engine", "version": "0.0.48"},
                    "wheel": {"filename": filename, "size": 123, "sha256": DIGEST},
                    "adapter_version": "battlebelief-poke-engine-v1",
                    "canonicalization_profile": "rfc8785-jcs-v1",
                }
            )
    return builds


def _evidence(builds: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        build["cell_id"]: {
            "schema_version": 1,
            "cell_id": build["cell_id"],
            "classification": "healthy",
            "source_manifest_digest": build["source_manifest_digest"],
            "build_manifest_digest": manifest_digest(build),
            "wheel_sha256": build["wheel"]["sha256"],
            "fixture_digest": DIGEST,
            "configuration_digest": DIGEST,
            "result_digest": DIGEST,
        }
        for build in builds
    }


def test_candidate_index_has_exactly_the_six_closed_cells() -> None:
    index = create_artifact_index(
        source_manifest=_source(),
        build_manifests=_builds(),
        fixture_digest=DIGEST,
        configuration_digest=DIGEST,
        result_digest=DIGEST,
        availability_status="candidate",
        evidence_by_cell=None,
    )

    assert len(index["cells"]) == 6
    assert {cell["availability_status"] for cell in index["cells"]} == {"candidate"}
    assert len({cell["cell_id"] for cell in index["cells"]}) == 6


def test_available_index_requires_matching_health_evidence_for_every_cell() -> None:
    builds = _builds()
    evidence = _evidence(builds)
    del evidence[builds[0]["cell_id"]]

    with pytest.raises(ArtifactIndexError, match="sentinel evidence closure differs"):
        create_artifact_index(
            source_manifest=_source(),
            build_manifests=builds,
            fixture_digest=DIGEST,
            configuration_digest=DIGEST,
            result_digest=DIGEST,
            availability_status="available",
            evidence_by_cell=evidence,
        )


def test_available_index_binds_matching_evidence_and_release_urls() -> None:
    builds = _builds()
    index = create_artifact_index(
        source_manifest=_source(),
        build_manifests=builds,
        fixture_digest=DIGEST,
        configuration_digest=DIGEST,
        result_digest=DIGEST,
        availability_status="available",
        evidence_by_cell=_evidence(builds),
    )

    assert {cell["availability_status"] for cell in index["cells"]} == {"available"}
    assert all(
        "/engine-poke-engine-v0.0.48-bcf13823-v1/" in cell["release_asset_url"]
        for cell in index["cells"]
    )


def test_duplicate_or_wrong_build_cells_are_rejected() -> None:
    builds = _builds()
    builds[-1] = builds[0]

    with pytest.raises(ArtifactIndexError, match="build cell closure differs"):
        create_artifact_index(
            source_manifest=_source(),
            build_manifests=builds,
            fixture_digest=DIGEST,
            configuration_digest=DIGEST,
            result_digest=DIGEST,
            availability_status="candidate",
            evidence_by_cell=None,
        )
