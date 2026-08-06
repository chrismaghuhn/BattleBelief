from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from tools.verify_published_engine_release import (
    PublishedReleaseError,
    verify_published_release,
)

from battlebelief_core.canonicalization import canonicalize, manifest_digest

TAG = "engine-poke-engine-v0.0.48-bcf13823-v1"
REPOSITORY = "chrismaghuhn/BattleBelief"


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _release_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    manifest_root = tmp_path / "manifests"
    bundle_root = tmp_path / "bundle"
    source = {
        "license": {"sha256": "", "size": 0},
        "schema_version": 1,
    }
    license_bytes = b"MIT license fixture\n"
    source["license"] = {"sha256": _sha256(license_bytes), "size": len(license_bytes)}
    source_bytes = canonicalize(source) + b"\n"
    source_digest = manifest_digest(source)
    _write(manifest_root / "engine-source.json", source_bytes)
    _write(bundle_root / "engine-source.json", source_bytes)
    _write(bundle_root / "poke-engine-LICENSE-MIT.txt", license_bytes)

    cells: list[dict[str, Any]] = []
    for operating_system in ("ubuntu-24.04", "windows-2025"):
        for minor in ("312", "313", "314"):
            cell_id = f"{operating_system}-x86_64-cp{minor}"
            abi = "none" if operating_system == "windows-2025" else f"cp{minor}"
            platform = "win_amd64" if operating_system == "windows-2025" else "linux_x86_64"
            wheel_name = f"poke_engine-0.0.48-cp{minor}-{abi}-{platform}.whl"
            wheel_bytes = f"wheel:{cell_id}\n".encode()
            wheel_digest = _sha256(wheel_bytes)
            build = {
                "cell_id": cell_id,
                "source_manifest_digest": source_digest,
                "wheel": {
                    "filename": wheel_name,
                    "sha256": wheel_digest,
                    "size": len(wheel_bytes),
                },
            }
            build_bytes = canonicalize(build) + b"\n"
            build_name = f"engine-build-{cell_id}.json"
            _write(manifest_root / build_name, build_bytes)
            _write(bundle_root / build_name, build_bytes)
            _write(bundle_root / wheel_name, wheel_bytes)
            cells.append(
                {
                    "availability_status": "available",
                    "build_manifest_digest": manifest_digest(build),
                    "cell_id": cell_id,
                    "release_asset_url": (
                        f"https://github.com/{REPOSITORY}/releases/download/{TAG}/{wheel_name}"
                    ),
                    "source_manifest_digest": source_digest,
                    "wheel_filename": wheel_name,
                    "wheel_sha256": wheel_digest,
                    "wheel_size": len(wheel_bytes),
                }
            )

    index = {
        "cells": cells,
        "release_assets_immutable": True,
        "release_prerelease": True,
        "release_tag": TAG,
        "source_manifest_digest": source_digest,
    }
    index_bytes = canonicalize(index) + b"\n"
    _write(manifest_root / "engine-artifact-index.json", index_bytes)
    _write(bundle_root / "engine-artifact-index.json", index_bytes)

    checksummed = sorted(path for path in bundle_root.iterdir() if path.is_file())
    sums = "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in checksummed
    ).encode("ascii")
    _write(bundle_root / "SHA256SUMS", sums)

    assets = []
    for path in sorted(bundle_root.iterdir()):
        data = path.read_bytes()
        assets.append(
            {
                "browser_download_url": (
                    f"https://github.com/{REPOSITORY}/releases/download/{TAG}/{path.name}"
                ),
                "digest": _sha256(data),
                "name": path.name,
                "size": len(data),
            }
        )
    release = {
        "assets": assets,
        "draft": False,
        "html_url": f"https://github.com/{REPOSITORY}/releases/tag/{TAG}",
        "immutable": True,
        "prerelease": True,
        "tag_name": TAG,
    }
    release_path = tmp_path / "release.json"
    release_path.write_text(json.dumps(release), encoding="utf-8")
    return release_path, bundle_root, manifest_root


def test_published_release_requires_exact_immutable_asset_closure(tmp_path: Path) -> None:
    release, bundle, manifests = _release_fixture(tmp_path)

    verify_published_release(
        release_metadata_path=release,
        bundle_root=bundle,
        manifest_root=manifests,
        expected_tag=TAG,
        expected_repository=REPOSITORY,
    )


def test_published_release_rejects_mutable_metadata_before_asset_use(tmp_path: Path) -> None:
    release, bundle, manifests = _release_fixture(tmp_path)
    metadata = json.loads(release.read_text(encoding="utf-8"))
    metadata["immutable"] = False
    release.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(PublishedReleaseError, match="release identity differs"):
        verify_published_release(
            release_metadata_path=release,
            bundle_root=bundle,
            manifest_root=manifests,
            expected_tag=TAG,
            expected_repository=REPOSITORY,
        )


def test_published_release_rejects_a_changed_wheel(tmp_path: Path) -> None:
    release, bundle, manifests = _release_fixture(tmp_path)
    wheel = next(bundle.glob("*.whl"))
    wheel_bytes = bytearray(wheel.read_bytes())
    wheel_bytes[0] ^= 1
    wheel.write_bytes(wheel_bytes)

    with pytest.raises(PublishedReleaseError, match="release asset digest differs"):
        verify_published_release(
            release_metadata_path=release,
            bundle_root=bundle,
            manifest_root=manifests,
            expected_tag=TAG,
            expected_repository=REPOSITORY,
        )


def test_published_release_rejects_manifest_drift(tmp_path: Path) -> None:
    release, bundle, manifests = _release_fixture(tmp_path)
    (manifests / "engine-source.json").write_bytes(b"{}\n")

    with pytest.raises(PublishedReleaseError, match="committed manifest differs"):
        verify_published_release(
            release_metadata_path=release,
            bundle_root=bundle,
            manifest_root=manifests,
            expected_tag=TAG,
            expected_repository=REPOSITORY,
        )


def test_published_release_rejects_a_self_consistent_bad_checksum_asset(
    tmp_path: Path,
) -> None:
    release, bundle, manifests = _release_fixture(tmp_path)
    checksums = bundle / "SHA256SUMS"
    lines = checksums.read_text(encoding="ascii").splitlines()
    lines[0] = "0" * 64 + lines[0][64:]
    checksums.write_text("\n".join(lines) + "\n", encoding="ascii")
    metadata = json.loads(release.read_text(encoding="utf-8"))
    asset = next(item for item in metadata["assets"] if item["name"] == "SHA256SUMS")
    data = checksums.read_bytes()
    asset["digest"] = _sha256(data)
    asset["size"] = len(data)
    release.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(PublishedReleaseError, match="release checksum differs"):
        verify_published_release(
            release_metadata_path=release,
            bundle_root=bundle,
            manifest_root=manifests,
            expected_tag=TAG,
            expected_repository=REPOSITORY,
        )
