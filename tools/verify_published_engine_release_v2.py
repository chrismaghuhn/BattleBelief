"""Verify the immutable v2 downstream-patched poke-engine release closure."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from battlebelief_core.canonicalization import manifest_digest  # noqa: E402
from tools.build_poke_engine_wheel import LEGAL_CHOICE_RELEASE_TAG  # noqa: E402
from tools.verify_published_engine_release import (  # noqa: E402
    CHECKSUMS_NAME,
    LICENSE_NAME,
    _load_object,
    _sha256,
    _verify_checksums,
    _verify_downloaded_assets,
    _verify_release_metadata,
)
from tools.verify_published_wheel_manifest_v2 import (  # noqa: E402
    verify_manifest_wheel_binding_v2,
)

EXPECTED_CELLS = frozenset(
    f"{operating_system}-x86_64-cp{minor}"
    for operating_system in ("ubuntu-24.04", "windows-2025")
    for minor in ("312", "313", "314")
)


class PublishedReleaseV2Error(RuntimeError):
    """A stable immutable v2-release closure failure."""


def _fail(message: str) -> NoReturn:
    raise PublishedReleaseV2Error(message)


def _verify_manifest_closure(
    *,
    bundle_root: Path,
    manifest_root: Path,
    expected_tag: str,
    expected_repository: str,
) -> set[str]:
    index, index_raw = _load_object(bundle_root / "engine-artifact-index.json", canonical=True)
    source, source_raw = _load_object(bundle_root / "engine-source.json", canonical=True)
    if index.get("schema_id") != "urn:battlebelief:schema:manifest:engine-artifact-index:v2":
        _fail("v2 release index schema differs")
    if source.get("schema_id") != "urn:battlebelief:schema:manifest:engine-source:v2":
        _fail("v2 release source schema differs")
    if {
        "release_assets_immutable": index.get("release_assets_immutable"),
        "release_prerelease": index.get("release_prerelease"),
        "release_tag": index.get("release_tag"),
        "source_manifest_digest": index.get("source_manifest_digest"),
    } != {
        "release_assets_immutable": True,
        "release_prerelease": True,
        "release_tag": expected_tag,
        "source_manifest_digest": manifest_digest(source),
    }:
        _fail("v2 release index identity differs")
    cells = index.get("cells")
    if (
        not isinstance(cells, list)
        or len(cells) != 6
        or not all(isinstance(cell, dict) for cell in cells)
    ):
        _fail("v2 release cell closure differs")
    cell_ids = [cell.get("cell_id") for cell in cells]
    if set(cell_ids) != EXPECTED_CELLS or len(set(cell_ids)) != 6:
        _fail("v2 release cell closure differs")

    manifest_names = {"engine-artifact-index.json", "engine-source.json"}
    try:
        if (manifest_root / "engine-artifact-index.json").read_bytes() != index_raw:
            _fail("v2 committed index differs")
        if (manifest_root / "engine-source.json").read_bytes() != source_raw:
            _fail("v2 committed source differs")
    except OSError:
        _fail("v2 committed manifest is unreadable")

    wheel_digests: set[str] = set()
    for cell in cells:
        cell_id = cell.get("cell_id")
        if not isinstance(cell_id, str):
            _fail("v2 release cell identity differs")
        build_name = f"engine-build-{cell_id}.json"
        manifest_names.add(build_name)
        build, build_raw = _load_object(bundle_root / build_name, canonical=True)
        try:
            if (manifest_root / build_name).read_bytes() != build_raw:
                _fail("v2 committed build differs")
        except OSError:
            _fail("v2 committed build is unreadable")
        wheel = build.get("wheel")
        if not isinstance(wheel, dict):
            _fail("v2 release wheel manifest differs")
        wheel_name = wheel.get("filename")
        if not isinstance(wheel_name, str) or not wheel_name.startswith("poke_engine-0.0.49-"):
            _fail("v2 release wheel identity differs")
        wheel_path = bundle_root / wheel_name
        if not wheel_path.is_file():
            _fail("v2 release wheel is unreadable")
        verify_manifest_wheel_binding_v2(source, build, wheel_path)
        digest = str(wheel.get("sha256"))
        if digest in wheel_digests:
            _fail("v2 release wheel identities are reused")
        wheel_digests.add(digest)
        expected_cell = {
            "availability_status": "available",
            "build_manifest_digest": manifest_digest(build),
            "release_asset_url": (
                f"https://github.com/{expected_repository}/releases/download/{expected_tag}/{wheel_name}"
            ),
            "source_manifest_digest": manifest_digest(source),
            "wheel_filename": wheel_name,
            "wheel_sha256": wheel.get("sha256"),
            "wheel_size": wheel.get("size"),
        }
        if build.get("cell_id") != cell_id or any(
            cell.get(key) != value for key, value in expected_cell.items()
        ):
            _fail("v2 release cell manifest differs")
        manifest_names.add(wheel_name)

    if len(wheel_digests) != 6:
        _fail("v2 release wheel closure differs")
    license_value = source.get("license")
    if not isinstance(license_value, Mapping):
        _fail("v2 release license binding differs")
    license_path = bundle_root / LICENSE_NAME
    if not license_path.is_file() or _sha256(license_path) != license_value.get("sha256"):
        _fail("v2 release license binding differs")
    return manifest_names


def verify_published_release_v2(
    *,
    release_metadata_path: Path,
    bundle_root: Path,
    manifest_root: Path,
    expected_tag: str,
    expected_repository: str,
) -> None:
    release, _ = _load_object(release_metadata_path, canonical=False)
    assets = _verify_release_metadata(
        release, expected_tag=expected_tag, expected_repository=expected_repository
    )
    asset_names = _verify_downloaded_assets(
        assets=assets,
        bundle_root=bundle_root,
        expected_repository=expected_repository,
        expected_tag=expected_tag,
    )
    manifest_names = _verify_manifest_closure(
        bundle_root=bundle_root,
        manifest_root=manifest_root,
        expected_tag=expected_tag,
        expected_repository=expected_repository,
    )
    expected_names = manifest_names | {CHECKSUMS_NAME, LICENSE_NAME}
    if asset_names != expected_names or len(asset_names) != 16:
        _fail("v2 release asset closure differs")
    _verify_checksums(bundle_root, asset_names)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-metadata", type=Path, required=True)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--manifest-root", type=Path, required=True)
    parser.add_argument("--expected-tag", default=LEGAL_CHOICE_RELEASE_TAG)
    parser.add_argument("--expected-repository", required=True)
    args = parser.parse_args(argv)
    try:
        verify_published_release_v2(
            release_metadata_path=args.release_metadata,
            bundle_root=args.bundle_root,
            manifest_root=args.manifest_root,
            expected_tag=args.expected_tag,
            expected_repository=args.expected_repository,
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(f"v2 immutable release closure failed: {error}", file=sys.stderr)
        return 1
    print("v2_immutable_release_closure=verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
