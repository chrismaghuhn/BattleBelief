"""Fail-closed verification of the installed, release-bound poke-engine wheel."""

from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import importlib.machinery
import importlib.metadata
import io
import json
import platform
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn, cast
from urllib.parse import unquote, urlparse

from battlebelief_core.canonicalization import canonicalize, manifest_digest
from battlebelief_runtime.search_status import EngineArtifactIdentity

from .errors import EngineArtifactError, EngineFailureClass

_RELEASE_TAG = "engine-poke-engine-v0.0.48-bcf13823-v1"
_FEATURES = ("poke-engine/gen9", "poke-engine/terastallization")
_EXPECTED_CELLS = frozenset(
    f"{operating_system}-x86_64-cp{minor}"
    for operating_system in ("ubuntu-24.04", "windows-2025")
    for minor in ("312", "313", "314")
)
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_DEFAULT_DATA_ROOT = Path(__file__).with_name("data")
EXPECTED_ARTIFACT_INDEX_DIGEST = (
    "sha256:5b4f59849ff01c6024b7b5f78f95f5457f3f69030bf46822d9f323c911908d98"
)


@dataclass(frozen=True, slots=True)
class RuntimeEnvironment:
    operating_system: str
    architecture: str
    python_tag: str
    abi_tag: str
    platform_tag: str

    @property
    def cell_id(self) -> str:
        return f"{self.operating_system}-{self.architecture}-{self.python_tag}"


@dataclass(frozen=True, slots=True)
class VerifiedEngineArtifact:
    identity: EngineArtifactIdentity
    package_root: Path
    extension_path: Path


def _fail(failure_class: EngineFailureClass) -> NoReturn:
    raise EngineArtifactError(failure_class)


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _strict_json(data: bytes, failure_class: EngineFailureClass) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                _fail(failure_class)
            result[key] = value
        return result

    try:
        value = json.loads(data, object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail(failure_class)
    if not isinstance(value, dict):
        _fail(failure_class)
    return value


def _load_canonical(path: Path, *, missing: EngineFailureClass) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError:
        _fail(missing)
    document = _strict_json(raw, EngineFailureClass.ARTIFACT_MISMATCH)
    try:
        expected = canonicalize(document) + b"\n"
    except (TypeError, ValueError):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    if raw != expected:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    return document


def current_environment() -> RuntimeEnvironment:
    implementation = platform.python_implementation()
    version = sys.version_info
    machine = platform.machine().lower()
    architecture = "x86_64" if machine in ("amd64", "x86_64") else "unsupported"
    python_tag = f"cp{version.major}{version.minor}"
    if implementation != "CPython" or python_tag not in ("cp312", "cp313", "cp314"):
        python_tag = "unsupported"
    if sys.platform == "win32":
        edition = platform.win32_edition().lower()
        build = sys.getwindowsversion().build
        operating_system = (
            "windows-2025" if "server" in edition and build >= 26100 else "unsupported"
        )
        abi_tag = "none"
        platform_tag = "win_amd64"
    elif sys.platform == "linux":
        operating_system = _linux_operating_system()
        abi_tag = python_tag
        platform_tag = "linux_x86_64"
    else:
        operating_system = "unsupported"
        abi_tag = "unsupported"
        platform_tag = "unsupported"
    return RuntimeEnvironment(
        operating_system=operating_system,
        architecture=architecture,
        python_tag=python_tag,
        abi_tag=abi_tag,
        platform_tag=platform_tag,
    )


def _linux_operating_system() -> str:
    try:
        values = platform.freedesktop_os_release()
    except OSError:
        return "unsupported"
    if values.get("ID") == "ubuntu" and values.get("VERSION_ID") == "24.04":
        return "ubuntu-24.04"
    return "unsupported"


def _cell(index: Mapping[str, Any], environment: RuntimeEnvironment) -> Mapping[str, Any]:
    cells = index.get("cells")
    if not isinstance(cells, list) or len(cells) != 6:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    if not all(isinstance(cell, dict) for cell in cells):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    identifiers = [cell.get("cell_id") for cell in cells]
    if len(set(identifiers)) != 6 or set(identifiers) != _EXPECTED_CELLS:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    if environment.cell_id not in _EXPECTED_CELLS:
        _fail(EngineFailureClass.UNSUPPORTED_ENVIRONMENT)
    selected = [cell for cell in cells if cell.get("cell_id") == environment.cell_id]
    if len(selected) != 1:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    return cast(Mapping[str, Any], selected[0])


def _require_digest(value: object) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    return value


def _expected_build_argv(target: str) -> list[str]:
    arguments = [
        "maturin",
        "build",
        "--release",
        "--strip",
        "--locked",
        "--manifest-path",
        "poke-engine-py/Cargo.toml",
        "--no-default-features",
        "--features",
        "poke-engine/gen9,poke-engine/terastallization",
        "--interpreter",
        "python",
        "--target",
        target,
        "--out",
        "wheelhouse",
    ]
    if target == "x86_64-unknown-linux-gnu":
        arguments.extend(("--compatibility", "linux"))
    return arguments


def _verify_manifest_closure(
    *,
    data_root: Path,
    index: Mapping[str, Any],
    cell: Mapping[str, Any],
    environment: RuntimeEnvironment,
    allow_candidate: bool,
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    fixed_index = {
        "schema_version": 1,
        "schema_id": "urn:battlebelief:schema:manifest:engine-artifact-index:v1",
        "release_tag": _RELEASE_TAG,
        "release_prerelease": True,
        "release_assets_immutable": True,
        "canonicalization_profile": "rfc8785-jcs-v1",
    }
    if any(index.get(key) != value for key, value in fixed_index.items()):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    source = _load_canonical(
        data_root / "engine-source.json", missing=EngineFailureClass.ARTIFACT_UNAVAILABLE
    )
    source_digest = manifest_digest(source)
    if source_digest != _require_digest(index.get("source_manifest_digest")) or (
        source_digest != _require_digest(cell.get("source_manifest_digest"))
    ):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
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
    if any(source.get(key) != value for key, value in fixed_source.items()):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    build = _load_canonical(
        data_root / f"engine-build-{environment.cell_id}.json",
        missing=EngineFailureClass.ARTIFACT_UNAVAILABLE,
    )
    if manifest_digest(build) != _require_digest(cell.get("build_manifest_digest")):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    expected_target = (
        "x86_64-unknown-linux-gnu"
        if environment.operating_system == "ubuntu-24.04"
        else "x86_64-pc-windows-msvc"
    )
    expected_build = {
        "schema_version": 1,
        "schema_id": "urn:battlebelief:schema:manifest:engine-build:v1",
        "cell_id": environment.cell_id,
        "source_manifest_digest": source_digest,
        "rust_toolchain": f"1.83.0-{expected_target}",
        "cargo_version": "cargo 1.83.0 (5ffbef321 2024-10-29)",
        "rustup_components": ["cargo", "rust-std", "rustc"],
        "rust_targets": [expected_target],
        "maturin_version": "1.7.1",
        "build_backend": "maturin",
        "build_argv": _expected_build_argv(expected_target),
        "locked": True,
        "no_default_features": True,
        "features": list(_FEATURES),
        "target_triple": expected_target,
        "operating_system": environment.operating_system,
        "architecture": environment.architecture,
        "adapter_version": "battlebelief-poke-engine-v1",
        "canonicalization_profile": "rfc8785-jcs-v1",
        "build_environment": {
            "allowlist": [
                {
                    "name": "CARGO_HOME",
                    "value": "../battlebelief-engine-cargo-home",
                },
                {"name": "CARGO_INCREMENTAL", "value": "false"},
                {"name": "CARGO_NET_OFFLINE", "value": "true"},
                {"name": "CARGO_PROFILE_RELEASE_DEBUG", "value": "0"},
                {"name": "PYTHONUTF8", "value": "1"},
                {"name": "SOURCE_DATE_EPOCH", "value": "1784471591"},
            ]
        },
    }
    if any(build.get(key) != value for key, value in expected_build.items()):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    rustc_vv = build.get("rustc_vv")
    if not isinstance(rustc_vv, str) or not {
        "rustc 1.83.0 (90b35a623 2024-11-26)",
        "commit-hash: 90b35a6239c3d8bdabc530a6a0816f7ff89a0aaf",
        "commit-date: 2024-11-26",
        f"host: {expected_target}",
        "release: 1.83.0",
    }.issubset(set(rustc_vv.splitlines())):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    python_identity = build.get("python")
    if not isinstance(python_identity, dict) or any(
        python_identity.get(key) != value
        for key, value in {
            "implementation": "CPython",
            "python_tag": environment.python_tag,
            "abi_tag": environment.abi_tag,
            "platform_tag": environment.platform_tag,
        }.items()
    ):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    distribution = build.get("distribution")
    wheel = build.get("wheel")
    if distribution != {"name": "poke-engine", "version": "0.0.48"} or not isinstance(wheel, dict):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    expected_cell = {
        "wheel_filename": wheel.get("filename"),
        "wheel_size": wheel.get("size"),
        "wheel_sha256": wheel.get("sha256"),
        "distribution_name": "poke-engine",
        "distribution_version": "0.0.48",
        "python_tag": environment.python_tag,
        "abi_tag": environment.abi_tag,
        "platform_tag": environment.platform_tag,
        "operating_system": environment.operating_system,
        "architecture": environment.architecture,
        "features": list(_FEATURES),
        "adapter_version": "battlebelief-poke-engine-v1",
        "release_tag": _RELEASE_TAG,
    }
    if any(cell.get(key) != value for key, value in expected_cell.items()):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    allowed_statuses = {"available", "candidate"} if allow_candidate else {"available"}
    if cell.get("availability_status") not in allowed_statuses:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    filename = cell.get("wheel_filename")
    expected_url = (
        f"https://github.com/chrismaghuhn/BattleBelief/releases/download/{_RELEASE_TAG}/{filename}"
    )
    if cell.get("release_asset_url") != expected_url:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    for field in (
        "sentinel_fixture_digest",
        "sentinel_result_digest",
        "sentinel_configuration_digest",
    ):
        _require_digest(cell.get(field))
    return source, build


def _safe_record_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or "\\" in value
        or any(part in ("", ".", "..") for part in path.parts)
    ):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    return path


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction is not None and is_junction())


def _installed_path(root: Path, relative: str) -> Path:
    pure = _safe_record_path(relative)
    candidate = root.joinpath(*pure.parts)
    current = root
    if _is_link_or_reparse(current):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    for part in pure.parts:
        current = current / part
        if _is_link_or_reparse(current):
            _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    try:
        candidate.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    if not candidate.is_file():
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    return candidate


def _read_installed(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)


def _decode_record_hash(value: str) -> str:
    try:
        algorithm, encoded = value.split("=", 1)
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (ValueError, binascii.Error):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    if algorithm != "sha256" or len(decoded) != 32:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    return "sha256:" + decoded.hex()


def _installed_record(record: bytes) -> dict[str, tuple[str | None, int | None]]:
    try:
        rows = list(csv.reader(io.StringIO(record.decode("utf-8", errors="strict"))))
    except (UnicodeDecodeError, csv.Error):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    result: dict[str, tuple[str | None, int | None]] = {}
    for row in rows:
        if len(row) != 3 or row[0] in result:
            _fail(EngineFailureClass.ARTIFACT_MISMATCH)
        path, raw_digest, raw_size = row
        _safe_record_path(path)
        if not raw_digest and not raw_size:
            result[path] = (None, None)
            continue
        if not raw_digest or not raw_size:
            _fail(EngineFailureClass.ARTIFACT_MISMATCH)
        try:
            result[path] = (_decode_record_hash(raw_digest), int(raw_size))
        except ValueError:
            _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    return result


def _distribution_root_and_info(
    distribution: importlib.metadata.Distribution,
) -> tuple[Path, str, set[str]]:
    files = distribution.files
    if files is None:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    paths = {str(path).replace("\\", "/") for path in files}
    metadata_paths = sorted(path for path in paths if path.endswith(".dist-info/METADATA"))
    if len(metadata_paths) != 1:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    dist_info = metadata_paths[0].split("/", 1)[0]
    try:
        root = Path(str(distribution.locate_file(""))).resolve(strict=True)
    except OSError:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    return root, dist_info, paths


def _verify_direct_url(
    content: bytes, *, cell: Mapping[str, Any], staged_wheel: Path | None
) -> None:
    document = _strict_json(content, EngineFailureClass.ARTIFACT_MISMATCH)
    if "vcs_info" in document or "dir_info" in document:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    url = document.get("url")
    archive = document.get("archive_info")
    if not isinstance(url, str) or not isinstance(archive, dict):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    digest = _require_digest(cell.get("wheel_sha256"))
    expected_hash = "sha256=" + digest.removeprefix("sha256:")
    hash_declared = "hash" in archive or "hashes" in archive
    hashes = archive.get("hashes")
    hash_matches = archive.get("hash") == expected_hash or (
        isinstance(hashes, dict) and hashes.get("sha256") == digest.removeprefix("sha256:")
    )
    if (hash_declared and not hash_matches) or (staged_wheel is None and not hash_matches):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    if staged_wheel is None:
        if url != cell.get("release_asset_url"):
            _fail(EngineFailureClass.ARTIFACT_MISMATCH)
        return
    parsed = urlparse(url)
    if parsed.scheme != "file":
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    raw_path = unquote(parsed.path)
    if sys.platform == "win32" and re.match(r"^/[A-Za-z]:/", raw_path):
        raw_path = raw_path[1:]
    try:
        recorded = Path(raw_path).resolve(strict=True)
        staged = staged_wheel.resolve(strict=True)
    except OSError:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    if recorded != staged:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)


def _verify_uv_cache(content: bytes) -> None:
    document = _strict_json(content, EngineFailureClass.ARTIFACT_MISMATCH)
    if set(document) != {"timestamp", "commit", "tags", "env", "directories"}:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    timestamp = document.get("timestamp")
    if not isinstance(timestamp, dict) or set(timestamp) != {
        "secs_since_epoch",
        "nanos_since_epoch",
    }:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    seconds = timestamp.get("secs_since_epoch")
    nanoseconds = timestamp.get("nanos_since_epoch")
    if (
        not isinstance(seconds, int)
        or isinstance(seconds, bool)
        or seconds < 0
        or not isinstance(nanoseconds, int)
        or isinstance(nanoseconds, bool)
        or not 0 <= nanoseconds < 1_000_000_000
        or document.get("commit") is not None
        or document.get("tags") is not None
        or document.get("env") != {}
        or document.get("directories") != {}
    ):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)


def _verify_installation(
    *,
    distribution: importlib.metadata.Distribution,
    build: Mapping[str, Any],
    cell: Mapping[str, Any],
    staged_wheel: Path | None,
) -> tuple[Path, Path]:
    if distribution.metadata.get("Name") != "poke-engine" or distribution.version != "0.0.48":
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    root, dist_info, distribution_paths = _distribution_root_and_info(distribution)
    record_relative = f"{dist_info}/RECORD"
    record_path = _installed_path(root, record_relative)
    installed_record = _installed_record(_read_installed(record_path))
    if set(installed_record) != distribution_paths:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    wheel = build.get("wheel")
    if not isinstance(wheel, dict) or not isinstance(wheel.get("record_entries"), list):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    original: dict[str, tuple[str | None, int | None]] = {}
    for item in wheel["record_entries"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            _fail(EngineFailureClass.ARTIFACT_MISMATCH)
        path = item["path"]
        if path in original:
            _fail(EngineFailureClass.ARTIFACT_MISMATCH)
        original[path] = (item.get("sha256"), item.get("size"))
    if record_relative not in original or original[record_relative] != (None, None):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    allowed_added = {
        f"{dist_info}/INSTALLER",
        f"{dist_info}/REQUESTED",
        f"{dist_info}/direct_url.json",
        f"{dist_info}/uv_cache.json",
    }
    if not set(installed_record).issubset(set(original) | allowed_added) or not set(
        original
    ).issubset(installed_record):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    for relative, (record_digest, record_size) in installed_record.items():
        path = _installed_path(root, relative)
        if relative == record_relative:
            if (record_digest, record_size) != (None, None):
                _fail(EngineFailureClass.ARTIFACT_MISMATCH)
            continue
        content = _read_installed(path)
        if record_digest != _sha256(content) or record_size != len(content):
            _fail(EngineFailureClass.ARTIFACT_MISMATCH)
        if relative in original and original[relative] != (record_digest, record_size):
            _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    actual_paths: set[str] = set()
    for directory in (root / "poke_engine", root / dist_info):
        if not directory.is_dir() or _is_link_or_reparse(directory):
            _fail(EngineFailureClass.ARTIFACT_MISMATCH)
        for path in directory.rglob("*"):
            if path.is_dir():
                if _is_link_or_reparse(path):
                    _fail(EngineFailureClass.ARTIFACT_MISMATCH)
                continue
            if _is_link_or_reparse(path) or not path.is_file():
                _fail(EngineFailureClass.ARTIFACT_MISMATCH)
            actual_paths.add(path.relative_to(root).as_posix())
    if actual_paths != set(installed_record):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    metadata_path = _installed_path(root, f"{dist_info}/METADATA")
    wheel_path = _installed_path(root, f"{dist_info}/WHEEL")
    if _sha256(_read_installed(metadata_path)) != wheel.get("metadata_sha256") or _sha256(
        _read_installed(wheel_path)
    ) != wheel.get("wheel_metadata_sha256"):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    direct_url_path = _installed_path(root, f"{dist_info}/direct_url.json")
    _verify_direct_url(_read_installed(direct_url_path), cell=cell, staged_wheel=staged_wheel)
    uv_cache_relative = f"{dist_info}/uv_cache.json"
    if uv_cache_relative in installed_record:
        uv_cache_path = _installed_path(root, uv_cache_relative)
        _verify_uv_cache(_read_installed(uv_cache_path))
    extension_candidates = sorted(
        _installed_path(root, path)
        for path in original
        if path.startswith("poke_engine/poke_engine.") and path.endswith((".pyd", ".so"))
    )
    if len(extension_candidates) != 1:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    expected_package = _installed_path(root, "poke_engine/__init__.py")
    spec = importlib.machinery.PathFinder.find_spec("poke_engine", sys.path)
    if spec is None or spec.origin is None:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    try:
        origin = Path(spec.origin).resolve(strict=True)
        expected_origin = expected_package.resolve(strict=True)
    except OSError:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    if origin != expected_origin:
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    return root / "poke_engine", extension_candidates[0]


def verify_installed_artifact(
    *,
    data_root: Path = _DEFAULT_DATA_ROOT,
    expected_index_digest: str | None = EXPECTED_ARTIFACT_INDEX_DIGEST,
    environment: RuntimeEnvironment | None = None,
    distribution: importlib.metadata.Distribution | None = None,
    staged_wheel: Path | None = None,
) -> VerifiedEngineArtifact:
    """Verify manifests, installation closure, origin, and release identity."""

    if expected_index_digest is None:
        _fail(EngineFailureClass.ARTIFACT_UNAVAILABLE)
    index = _load_canonical(
        data_root / "engine-artifact-index.json",
        missing=EngineFailureClass.ARTIFACT_UNAVAILABLE,
    )
    if manifest_digest(index) != _require_digest(expected_index_digest):
        _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    selected_environment = current_environment() if environment is None else environment
    cell = _cell(index, selected_environment)
    _source, build = _verify_manifest_closure(
        data_root=data_root,
        index=index,
        cell=cell,
        environment=selected_environment,
        allow_candidate=staged_wheel is not None,
    )
    if staged_wheel is not None:
        try:
            wheel_bytes = staged_wheel.read_bytes()
        except OSError:
            _fail(EngineFailureClass.ARTIFACT_UNAVAILABLE)
        if (
            staged_wheel.name != cell.get("wheel_filename")
            or len(wheel_bytes) != cell.get("wheel_size")
            or _sha256(wheel_bytes) != cell.get("wheel_sha256")
        ):
            _fail(EngineFailureClass.ARTIFACT_MISMATCH)
    if distribution is None:
        try:
            distribution = importlib.metadata.distribution("poke-engine")
        except importlib.metadata.PackageNotFoundError:
            _fail(EngineFailureClass.EXTRA_UNAVAILABLE)
    package_root, extension_path = _verify_installation(
        distribution=distribution,
        build=build,
        cell=cell,
        staged_wheel=staged_wheel,
    )
    identity = EngineArtifactIdentity(
        artifact_index_digest=expected_index_digest,
        source_manifest_digest=_require_digest(cell.get("source_manifest_digest")),
        build_manifest_digest=_require_digest(cell.get("build_manifest_digest")),
        wheel_sha256=_require_digest(cell.get("wheel_sha256")),
        wheel_filename=str(cell.get("wheel_filename")),
        cell_id=str(cell.get("cell_id")),
        distribution_name=str(cell.get("distribution_name")),
        distribution_version=str(cell.get("distribution_version")),
        python_tag=str(cell.get("python_tag")),
        abi_tag=str(cell.get("abi_tag")),
        platform_tag=str(cell.get("platform_tag")),
        operating_system=str(cell.get("operating_system")),
        architecture=str(cell.get("architecture")),
        features=tuple(cell.get("features", ())),
        adapter_version=str(cell.get("adapter_version")),
        release_tag=str(cell.get("release_tag")),
        release_asset_url=str(cell.get("release_asset_url")),
        sentinel_fixture_digest=_require_digest(cell.get("sentinel_fixture_digest")),
        sentinel_result_digest=_require_digest(cell.get("sentinel_result_digest")),
        sentinel_configuration_digest=_require_digest(cell.get("sentinel_configuration_digest")),
    )
    return VerifiedEngineArtifact(
        identity=identity,
        package_root=package_root,
        extension_path=extension_path,
    )


__all__: list[str] = []
