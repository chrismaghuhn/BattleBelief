"""Verify the immutable Task-25 GitHub release and its complete asset closure."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from battlebelief_core.canonicalization import canonicalize, manifest_digest  # noqa: E402

EXPECTED_CELLS = frozenset(
    f"{operating_system}-x86_64-cp{minor}"
    for operating_system in ("ubuntu-24.04", "windows-2025")
    for minor in ("312", "313", "314")
)
LICENSE_NAME = "poke-engine-LICENSE-MIT.txt"
CHECKSUMS_NAME = "SHA256SUMS"
_CHECKSUM_LINE = re.compile(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)")


class PublishedReleaseError(RuntimeError):
    """A stable immutable-release closure failure."""


def _fail(message: str) -> NoReturn:
    raise PublishedReleaseError(message)


def _reject_constant(_value: str) -> NoReturn:
    raise ValueError("non-finite JSON constant")


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("release input has duplicate keys")
        result[key] = value
    return result


def _load_object(path: Path, *, canonical: bool) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw,
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        _fail("release input is unreadable")
    if not isinstance(value, dict):
        _fail("release input structure differs")
    if canonical and raw != canonicalize(value) + b"\n":
        _fail("release manifest is not canonical")
    return value, raw


def _sha256(path: Path) -> str:
    try:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        _fail("release asset is unreadable")


def _asset_map(release: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    assets = release.get("assets")
    if not isinstance(assets, list) or not all(isinstance(asset, dict) for asset in assets):
        _fail("release asset metadata differs")
    result: dict[str, Mapping[str, Any]] = {}
    for asset in assets:
        name = asset.get("name")
        if not isinstance(name, str) or name in result:
            _fail("release asset metadata differs")
        result[name] = asset
    return result


def _verify_release_metadata(
    release: Mapping[str, Any], *, expected_tag: str, expected_repository: str
) -> dict[str, Mapping[str, Any]]:
    expected_identity = {
        "draft": False,
        "html_url": f"https://github.com/{expected_repository}/releases/tag/{expected_tag}",
        "immutable": True,
        "prerelease": True,
        "tag_name": expected_tag,
    }
    if any(release.get(key) != value for key, value in expected_identity.items()):
        _fail("release identity differs")
    return _asset_map(release)


def _verify_downloaded_assets(
    *,
    assets: Mapping[str, Mapping[str, Any]],
    bundle_root: Path,
    expected_repository: str,
    expected_tag: str,
) -> set[str]:
    try:
        bundle_files = {path.name: path for path in bundle_root.iterdir() if path.is_file()}
        has_nonfiles = any(not path.is_file() for path in bundle_root.iterdir())
    except OSError:
        _fail("release bundle is unreadable")
    if has_nonfiles or set(bundle_files) != set(assets):
        _fail("release asset closure differs")
    for name, asset in assets.items():
        path = bundle_files[name]
        expected_url = (
            f"https://github.com/{expected_repository}/releases/download/{expected_tag}/{name}"
        )
        try:
            size = path.stat().st_size
        except OSError:
            _fail("release asset is unreadable")
        if asset.get("browser_download_url") != expected_url or asset.get("size") != size:
            _fail("release asset metadata differs")
        if asset.get("digest") != _sha256(path):
            _fail("release asset digest differs")
    return set(bundle_files)


def _verify_checksums(bundle_root: Path, asset_names: set[str]) -> None:
    checksums_path = bundle_root / CHECKSUMS_NAME
    try:
        text = checksums_path.read_text(encoding="ascii")
    except (OSError, UnicodeDecodeError):
        _fail("release checksums are unreadable")
    lines = text.splitlines()
    entries: dict[str, str] = {}
    for line in lines:
        match = _CHECKSUM_LINE.fullmatch(line)
        if match is None or match.group(2) in entries:
            _fail("release checksum format differs")
        entries[match.group(2)] = "sha256:" + match.group(1)
    expected_names = asset_names - {CHECKSUMS_NAME}
    if list(entries) != sorted(expected_names) or set(entries) != expected_names:
        _fail("release checksum closure differs")
    for name, digest in entries.items():
        if _sha256(bundle_root / name) != digest:
            _fail("release checksum differs")


def _verify_manifest_closure(
    *,
    bundle_root: Path,
    manifest_root: Path,
    expected_tag: str,
    expected_repository: str,
) -> set[str]:
    index, index_raw = _load_object(bundle_root / "engine-artifact-index.json", canonical=True)
    source, source_raw = _load_object(bundle_root / "engine-source.json", canonical=True)
    expected_index = {
        "release_assets_immutable": True,
        "release_prerelease": True,
        "release_tag": expected_tag,
        "source_manifest_digest": manifest_digest(source),
    }
    if any(index.get(key) != value for key, value in expected_index.items()):
        _fail("release index identity differs")
    cells = index.get("cells")
    if not isinstance(cells, list) or not all(isinstance(cell, dict) for cell in cells):
        _fail("release index cell closure differs")
    cell_ids = [cell.get("cell_id") for cell in cells]
    if (
        len(cell_ids) != 6
        or not all(isinstance(cell_id, str) for cell_id in cell_ids)
        or len(set(cell_ids)) != 6
        or set(cell_ids) != EXPECTED_CELLS
    ):
        _fail("release index cell closure differs")

    manifest_names = {"engine-artifact-index.json", "engine-source.json"}
    try:
        committed_index = (manifest_root / "engine-artifact-index.json").read_bytes()
        committed_source = (manifest_root / "engine-source.json").read_bytes()
    except OSError:
        _fail("committed manifest differs")
    if committed_index != index_raw or committed_source != source_raw:
        _fail("committed manifest differs")

    source_digest = manifest_digest(source)
    for cell in cells:
        cell_id = cell.get("cell_id")
        if not isinstance(cell_id, str):
            _fail("release index cell closure differs")
        build_name = f"engine-build-{cell_id}.json"
        manifest_names.add(build_name)
        build, build_raw = _load_object(bundle_root / build_name, canonical=True)
        try:
            committed_build = (manifest_root / build_name).read_bytes()
        except OSError:
            _fail("committed manifest differs")
        if committed_build != build_raw:
            _fail("committed manifest differs")
        wheel = build.get("wheel")
        if not isinstance(wheel, dict):
            _fail("release build manifest differs")
        expected_cell = {
            "availability_status": "available",
            "build_manifest_digest": manifest_digest(build),
            "release_asset_url": (
                f"https://github.com/{expected_repository}/releases/download/{expected_tag}/"
                f"{cell.get('wheel_filename')}"
            ),
            "source_manifest_digest": source_digest,
            "wheel_filename": wheel.get("filename"),
            "wheel_sha256": wheel.get("sha256"),
            "wheel_size": wheel.get("size"),
        }
        if (
            build.get("cell_id") != cell_id
            or build.get("source_manifest_digest") != source_digest
            or any(cell.get(key) != value for key, value in expected_cell.items())
        ):
            _fail("release build manifest differs")
        wheel_name = cell.get("wheel_filename")
        if not isinstance(wheel_name, str):
            _fail("release build manifest differs")
        wheel_path = bundle_root / wheel_name
        try:
            wheel_size = wheel_path.stat().st_size
        except OSError:
            _fail("release wheel is unreadable")
        if wheel_size != cell.get("wheel_size") or _sha256(wheel_path) != cell.get("wheel_sha256"):
            _fail("release wheel differs")

    license_value = source.get("license")
    if not isinstance(license_value, dict):
        _fail("release license binding differs")
    license_path = bundle_root / LICENSE_NAME
    try:
        license_size = license_path.stat().st_size
    except OSError:
        _fail("release license is unreadable")
    if license_size != license_value.get("size") or _sha256(license_path) != license_value.get(
        "sha256"
    ):
        _fail("release license binding differs")
    return manifest_names


def verify_published_release(
    *,
    release_metadata_path: Path,
    bundle_root: Path,
    manifest_root: Path,
    expected_tag: str,
    expected_repository: str,
) -> None:
    """Fail closed unless metadata, assets, checksums, and manifests close exactly."""

    release, _raw = _load_object(release_metadata_path, canonical=False)
    assets = _verify_release_metadata(
        release,
        expected_tag=expected_tag,
        expected_repository=expected_repository,
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
    expected_names = manifest_names | {
        CHECKSUMS_NAME,
        LICENSE_NAME,
    }
    index, _index_raw = _load_object(bundle_root / "engine-artifact-index.json", canonical=True)
    cells = index["cells"]
    expected_names.update(str(cell["wheel_filename"]) for cell in cells)
    if asset_names != expected_names or len(asset_names) != 16:
        _fail("release asset closure differs")
    _verify_checksums(bundle_root, asset_names)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-metadata", type=Path, required=True)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--manifest-root", type=Path, required=True)
    parser.add_argument("--expected-tag", required=True)
    parser.add_argument("--expected-repository", required=True)
    args = parser.parse_args(argv)
    try:
        verify_published_release(
            release_metadata_path=args.release_metadata,
            bundle_root=args.bundle_root,
            manifest_root=args.manifest_root,
            expected_tag=args.expected_tag,
            expected_repository=args.expected_repository,
        )
    except (OSError, PublishedReleaseError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print("immutable_release_closure=verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
