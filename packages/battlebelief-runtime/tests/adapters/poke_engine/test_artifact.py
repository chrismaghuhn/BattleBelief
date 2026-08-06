from __future__ import annotations

import base64
import csv
import hashlib
import importlib.machinery
import importlib.metadata
import json
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

import pytest

from battlebelief_core.canonicalization import canonicalize, manifest_digest
from battlebelief_runtime.adapters.poke_engine.artifact import (
    RuntimeEnvironment,
    _verify_direct_url,
    verify_installed_artifact,
)
from battlebelief_runtime.adapters.poke_engine.errors import (
    EngineArtifactError,
    EngineFailureClass,
)

DIGEST = "sha256:" + "a" * 64
FEATURES = ["poke-engine/gen9", "poke-engine/terastallization"]
RELEASE_TAG = "engine-poke-engine-v0.0.48-bcf13823-v1"
CELL_ID = "windows-2025-x86_64-cp314"
WHEEL = "poke_engine-0.0.48-cp314-none-win_amd64.whl"


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _record_hash(data: bytes) -> str:
    return "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")


def _environment() -> RuntimeEnvironment:
    return RuntimeEnvironment(
        operating_system="windows-2025",
        architecture="x86_64",
        python_tag="cp314",
        abi_tag="none",
        platform_tag="win_amd64",
    )


def _write_canonical(path: Path, document: dict[str, object]) -> None:
    path.write_bytes(canonicalize(document) + b"\n")


def test_staged_wheel_direct_url_may_omit_an_archive_hash(tmp_path: Path) -> None:
    staged_wheel = tmp_path / WHEEL
    wheel_bytes = b"staged wheel bytes"
    staged_wheel.write_bytes(wheel_bytes)
    direct_url = canonicalize({"archive_info": {}, "url": staged_wheel.as_uri()})

    _verify_direct_url(
        direct_url,
        cell={"wheel_sha256": _sha256(wheel_bytes)},
        staged_wheel=staged_wheel,
    )


def test_release_direct_url_still_requires_the_bound_archive_hash() -> None:
    direct_url = canonicalize(
        {
            "archive_info": {},
            "url": f"https://github.com/example/release/{WHEEL}",
        }
    )

    with pytest.raises(EngineArtifactError, match="artifact_mismatch"):
        _verify_direct_url(
            direct_url,
            cell={
                "wheel_sha256": DIGEST,
                "release_asset_url": f"https://github.com/example/release/{WHEEL}",
            },
            staged_wheel=None,
        )


def _installation(tmp_path: Path) -> tuple[Path, Path, importlib.metadata.Distribution, str]:
    data_root = tmp_path / "sidecars"
    data_root.mkdir()
    site = tmp_path / "site"
    package = site / "poke_engine"
    dist_info = site / "poke_engine-0.0.48.dist-info"
    package.mkdir(parents=True)
    dist_info.mkdir()

    source = {
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
    source_digest = manifest_digest(source)
    source_path = data_root / "engine-source.json"
    _write_canonical(source_path, source)

    metadata_bytes = b"Metadata-Version: 2.1\nName: poke-engine\nVersion: 0.0.48\n"
    wheel_bytes = b"Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: cp314-none-win_amd64\n"
    direct_url_bytes = canonicalize(
        {
            "archive_info": {"hash": "sha256=" + "a" * 64},
            "url": (
                "https://github.com/chrismaghuhn/BattleBelief/releases/download/"
                f"{RELEASE_TAG}/{WHEEL}"
            ),
        }
    )
    installed = {
        "poke_engine/__init__.py": b"from .poke_engine import State\n",
        "poke_engine/poke_engine.cp314-win_amd64.pyd": b"native fixture",
        "poke_engine-0.0.48.dist-info/METADATA": metadata_bytes,
        "poke_engine-0.0.48.dist-info/WHEEL": wheel_bytes,
        "poke_engine-0.0.48.dist-info/direct_url.json": direct_url_bytes,
        "poke_engine-0.0.48.dist-info/uv_cache.json": (
            b'{"timestamp":{"secs_since_epoch":1786006259,"nanos_since_epoch":1},'
            b'"commit":null,"tags":null,"env":{},"directories":{}}'
        ),
    }
    for relative, content in installed.items():
        path = site / Path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    record_relative = "poke_engine-0.0.48.dist-info/RECORD"
    rows = [
        [relative, _record_hash(content), str(len(content))]
        for relative, content in sorted(installed.items())
    ]
    rows.append([record_relative, "", ""])
    record_path = site / record_relative
    with record_path.open("w", encoding="utf-8", newline="") as output:
        csv.writer(output, lineterminator="\n").writerows(rows)
    record_bytes = record_path.read_bytes()

    build = {
        "schema_version": 1,
        "schema_id": "urn:battlebelief:schema:manifest:engine-build:v1",
        "cell_id": CELL_ID,
        "source_manifest_digest": source_digest,
        "rust_toolchain": "1.83.0-x86_64-pc-windows-msvc",
        "rustc_vv": (
            "rustc 1.83.0 (90b35a623 2024-11-26)\n"
            "binary: rustc\n"
            "commit-hash: 90b35a6239c3d8bdabc530a6a0816f7ff89a0aaf\n"
            "commit-date: 2024-11-26\n"
            "host: x86_64-pc-windows-msvc\n"
            "release: 1.83.0\n"
            "LLVM version: 19.1.1"
        ),
        "cargo_version": "cargo 1.83.0 (5ffbef321 2024-10-29)",
        "rustup_components": ["cargo", "rust-std", "rustc"],
        "rust_targets": ["x86_64-pc-windows-msvc"],
        "maturin_version": "1.7.1",
        "build_backend": "maturin",
        "build_argv": [
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
            "x86_64-pc-windows-msvc",
            "--out",
            "wheelhouse",
        ],
        "locked": True,
        "no_default_features": True,
        "features": FEATURES,
        "target_triple": "x86_64-pc-windows-msvc",
        "operating_system": "windows-2025",
        "architecture": "x86_64",
        "python": {
            "implementation": "CPython",
            "version": "3.14.2",
            "python_tag": "cp314",
            "abi_tag": "none",
            "platform_tag": "win_amd64",
        },
        "distribution": {"name": "poke-engine", "version": "0.0.48"},
        "wheel": {
            "filename": WHEEL,
            "size": 123,
            "sha256": DIGEST,
            "metadata_sha256": _sha256(metadata_bytes),
            "wheel_metadata_sha256": _sha256(wheel_bytes),
            "record_sha256": _sha256(record_bytes),
            "record_entries": [
                {
                    "path": relative,
                    "sha256": _sha256(content),
                    "size": len(content),
                }
                for relative, content in sorted(installed.items())
                if not relative.endswith(("direct_url.json", "uv_cache.json"))
            ]
            + [{"path": record_relative, "sha256": None, "size": None}],
            "root_is_purelib": False,
            "tags": ["cp314-none-win_amd64"],
        },
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
        "adapter_version": "battlebelief-poke-engine-v1",
        "canonicalization_profile": "rfc8785-jcs-v1",
    }
    build_digest = manifest_digest(build)
    _write_canonical(data_root / f"engine-build-{CELL_ID}.json", build)

    def cell(operating_system: str, python_tag: str) -> dict[str, object]:
        windows = operating_system == "windows-2025"
        platform_tag = "win_amd64" if windows else "linux_x86_64"
        abi_tag = "none" if windows else python_tag
        filename = f"poke_engine-0.0.48-{python_tag}-{abi_tag}-{platform_tag}.whl"
        cell_id = f"{operating_system}-x86_64-{python_tag}"
        return {
            "cell_id": cell_id,
            "source_manifest_digest": source_digest,
            "build_manifest_digest": build_digest if cell_id == CELL_ID else DIGEST,
            "wheel_filename": filename,
            "wheel_size": 123,
            "wheel_sha256": DIGEST,
            "distribution_name": "poke-engine",
            "distribution_version": "0.0.48",
            "python_tag": python_tag,
            "abi_tag": abi_tag,
            "platform_tag": platform_tag,
            "operating_system": operating_system,
            "architecture": "x86_64",
            "features": FEATURES,
            "adapter_version": "battlebelief-poke-engine-v1",
            "release_tag": RELEASE_TAG,
            "release_asset_url": (
                "https://github.com/chrismaghuhn/BattleBelief/releases/download/"
                f"{RELEASE_TAG}/{filename}"
            ),
            "sentinel_fixture_digest": DIGEST,
            "sentinel_result_digest": DIGEST,
            "sentinel_configuration_digest": DIGEST,
            "availability_status": "available",
        }

    index = {
        "schema_version": 1,
        "schema_id": "urn:battlebelief:schema:manifest:engine-artifact-index:v1",
        "source_manifest_digest": source_digest,
        "release_tag": RELEASE_TAG,
        "release_prerelease": True,
        "release_assets_immutable": True,
        "cells": [
            cell(operating_system, python_tag)
            for operating_system in ("ubuntu-24.04", "windows-2025")
            for python_tag in ("cp312", "cp313", "cp314")
        ],
        "canonicalization_profile": "rfc8785-jcs-v1",
    }
    index_digest = manifest_digest(index)
    _write_canonical(data_root / "engine-artifact-index.json", index)
    distribution = importlib.metadata.PathDistribution(dist_info)
    return data_root, site, distribution, index_digest


def test_verified_installation_returns_only_sanitized_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root, site, distribution, index_digest = _installation(tmp_path)
    monkeypatch.syspath_prepend(str(site))

    verified = verify_installed_artifact(
        data_root=data_root,
        expected_index_digest=index_digest,
        environment=_environment(),
        distribution=distribution,
    )

    assert verified.identity.cell_id == CELL_ID
    assert verified.identity.wheel_filename == WHEEL
    assert verified.extension_path.name.endswith(".pyd")
    assert str(tmp_path) not in str(verified.identity.to_dict())


def test_installed_file_read_error_is_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root, site, distribution, index_digest = _installation(tmp_path)
    monkeypatch.syspath_prepend(str(site))
    blocked = site / "poke_engine" / "__init__.py"
    original_read_bytes = Path.read_bytes

    def fail_one_read(path: Path) -> bytes:
        if path == blocked:
            raise PermissionError("private local path detail")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fail_one_read)

    with pytest.raises(EngineArtifactError) as caught:
        verify_installed_artifact(
            data_root=data_root,
            expected_index_digest=index_digest,
            environment=_environment(),
            distribution=distribution,
        )

    assert caught.value.failure_class is EngineFailureClass.ARTIFACT_MISMATCH
    assert str(caught.value) == "artifact_mismatch"


@pytest.mark.parametrize(
    ("error_type", "private_detail"),
    [
        pytest.param(PermissionError, "private expected package resolution detail", id="os-error"),
        pytest.param(RuntimeError, "private loop path", id="symlink-loop"),
    ],
)
def test_expected_package_resolution_error_is_sanitized_after_origin_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[OSError] | type[RuntimeError],
    private_detail: str,
) -> None:
    data_root, site, distribution, index_digest = _installation(tmp_path)
    monkeypatch.syspath_prepend(str(site))
    expected_package = site / "poke_engine" / "__init__.py"
    original_find_spec = importlib.machinery.PathFinder.find_spec
    original_resolve = Path.resolve
    post_spec = False
    expected_resolve_count = 0

    def mark_post_spec(
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        nonlocal post_spec
        spec = original_find_spec(fullname, path, target)
        if fullname == "poke_engine":
            post_spec = True
        return spec

    def fail_second_expected_resolution(path: Path, *, strict: bool = False) -> Path:
        nonlocal expected_resolve_count
        if post_spec and path == expected_package:
            expected_resolve_count += 1
            if expected_resolve_count == 2:
                raise error_type(private_detail)
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(importlib.machinery.PathFinder, "find_spec", mark_post_spec)
    monkeypatch.setattr(Path, "resolve", fail_second_expected_resolution)

    with pytest.raises(EngineArtifactError) as caught:
        verify_installed_artifact(
            data_root=data_root,
            expected_index_digest=index_digest,
            environment=_environment(),
            distribution=distribution,
        )

    assert expected_resolve_count == 2
    assert caught.value.failure_class is EngineFailureClass.ARTIFACT_MISMATCH
    assert str(caught.value) == "artifact_mismatch"
    assert private_detail not in str(caught.value)
    assert str(tmp_path) not in str(caught.value)


def test_missing_extra_is_classified_without_raw_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root, _site, _distribution, index_digest = _installation(tmp_path)

    def missing(_name: str) -> importlib.metadata.Distribution:
        raise importlib.metadata.PackageNotFoundError("private local detail")

    monkeypatch.setattr(importlib.metadata, "distribution", missing)
    with pytest.raises(EngineArtifactError) as caught:
        verify_installed_artifact(
            data_root=data_root,
            expected_index_digest=index_digest,
            environment=_environment(),
        )

    assert caught.value.failure_class is EngineFailureClass.EXTRA_UNAVAILABLE
    assert str(caught.value) == "extra_unavailable"


@pytest.mark.parametrize(
    ("mutation", "expected_failure"),
    [
        ("index_digest", EngineFailureClass.ARTIFACT_MISMATCH),
        ("source_digest", EngineFailureClass.ARTIFACT_MISMATCH),
        ("build_digest", EngineFailureClass.ARTIFACT_MISMATCH),
        ("features", EngineFailureClass.ARTIFACT_MISMATCH),
        ("release_url", EngineFailureClass.ARTIFACT_MISMATCH),
        ("record", EngineFailureClass.ARTIFACT_MISMATCH),
        ("installed_file", EngineFailureClass.ARTIFACT_MISMATCH),
        ("shadow", EngineFailureClass.ARTIFACT_MISMATCH),
    ],
)
def test_artifact_verification_fails_closed_on_provenance_or_installation_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    expected_failure: EngineFailureClass,
) -> None:
    data_root, site, distribution, index_digest = _installation(tmp_path)
    monkeypatch.syspath_prepend(str(site))
    if mutation == "index_digest":
        index_digest = DIGEST
    elif mutation == "source_digest":
        source = json.loads((data_root / "engine-source.json").read_bytes())
        source["commit"] = "0" * 40
        _write_canonical(data_root / "engine-source.json", source)
    elif mutation in {"build_digest", "features", "release_url"}:
        index_path = data_root / "engine-artifact-index.json"
        index = json.loads(index_path.read_bytes())
        selected = next(cell for cell in index["cells"] if cell["cell_id"] == CELL_ID)
        if mutation == "build_digest":
            selected["build_manifest_digest"] = DIGEST
        elif mutation == "features":
            selected["features"] = ["poke-engine/gen4"]
        else:
            selected["release_asset_url"] = "https://example.invalid/latest.whl"
        _write_canonical(index_path, index)
        index_digest = manifest_digest(index)
    elif mutation == "record":
        record = site / "poke_engine-0.0.48.dist-info" / "RECORD"
        record.write_bytes(record.read_bytes() + b"extra,,\n")
    elif mutation == "installed_file":
        (site / "poke_engine" / "__init__.py").write_bytes(b"tampered\n")
    else:
        shadow = tmp_path / "shadow"
        (shadow / "poke_engine").mkdir(parents=True)
        (shadow / "poke_engine" / "__init__.py").write_bytes(b"fake\n")
        monkeypatch.syspath_prepend(str(shadow))

    with pytest.raises(EngineArtifactError) as caught:
        verify_installed_artifact(
            data_root=data_root,
            expected_index_digest=index_digest,
            environment=_environment(),
            distribution=distribution,
        )

    assert caught.value.failure_class is expected_failure


def test_unsupported_environment_fails_before_distribution_lookup(tmp_path: Path) -> None:
    data_root, _site, distribution, index_digest = _installation(tmp_path)
    unsupported = RuntimeEnvironment(
        operating_system="unsupported",
        architecture="x86_64",
        python_tag="cp314",
        abi_tag="cp314",
        platform_tag="linux_x86_64",
    )

    with pytest.raises(EngineArtifactError) as caught:
        verify_installed_artifact(
            data_root=data_root,
            expected_index_digest=index_digest,
            environment=unsupported,
            distribution=distribution,
        )

    assert caught.value.failure_class is EngineFailureClass.UNSUPPORTED_ENVIRONMENT
