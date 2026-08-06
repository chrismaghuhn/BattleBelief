from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_ROOT = ROOT / "schemas/manifests"
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
DIGEST_D = "sha256:" + "d" * 64
COMMIT = "bcf13823abc162a608e187b26bbf683f759f385e"
TREE = "74d10964d7470b2b9d92ba734550825388178d2d"
FEATURES = ["poke-engine/gen9", "poke-engine/terastallization"]
RELEASE_TAG = "engine-poke-engine-v0.0.48-bcf13823-v1"


def _schema(name: str) -> dict[str, Any]:
    path = SCHEMA_ROOT / name
    assert path.is_file(), f"missing schema: {path.relative_to(ROOT)}"
    return json.loads(path.read_text(encoding="utf-8"))


def _issues(schema_name: str, instance: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(_schema(schema_name), format_checker=FormatChecker())
    return [error.message for error in validator.iter_errors(instance)]


def _source_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "schema_id": "urn:battlebelief:schema:manifest:engine-source:v1",
        "manifest_id": "poke-engine-source-bcf13823",
        "repository_url": "https://github.com/pmariglia/poke-engine",
        "commit": COMMIT,
        "observed_tag": "v0.0.48",
        "tag_peeled_commit": COMMIT,
        "git_tree_oid": TREE,
        "retrieved_on": "2026-08-06",
        "license": {
            "spdx_id": "MIT",
            "path": "LICENSE",
            "size": 1072,
            "sha256": DIGEST_A,
        },
        "source_scope": "full_git_tree",
        "source_files": [
            {"path": "Cargo.lock", "git_mode": "100644", "size": 8, "sha256": DIGEST_B},
            {"path": "LICENSE", "git_mode": "100644", "size": 1072, "sha256": DIGEST_A},
        ],
        "source_tree_digest": DIGEST_C,
        "source_file_count": 2,
        "cargo_lock": {"path": "Cargo.lock", "size": 8, "sha256": DIGEST_B},
        "workspace_members": ["poke-engine-py", "poke-engine-tests"],
        "submodules": {"present": False, "entries": []},
        "clean_tree": True,
        "canonicalization_profile": "rfc8785-jcs-v1",
    }


def _build_manifest(
    *, python_minor: str = "3.12", operating_system: str = "ubuntu-24.04"
) -> dict[str, Any]:
    digits = python_minor.replace(".", "")
    python_tag = f"cp{digits}"
    windows = operating_system == "windows-2025"
    target = "x86_64-pc-windows-msvc" if windows else "x86_64-unknown-linux-gnu"
    platform_tag = "win_amd64" if windows else "linux_x86_64"
    abi_tag = "none" if windows else python_tag
    cell = f"{operating_system}-x86_64-{python_tag}"
    filename = f"poke_engine-0.0.48-{python_tag}-{abi_tag}-{platform_tag}.whl"
    return {
        "schema_version": 1,
        "schema_id": "urn:battlebelief:schema:manifest:engine-build:v1",
        "manifest_id": f"poke-engine-build-{cell}",
        "cell_id": cell,
        "source_schema_id": "urn:battlebelief:schema:manifest:engine-source:v1",
        "source_manifest_digest": DIGEST_A,
        "rust_toolchain": f"1.83.0-{target}",
        "rustc_vv": (
            "rustc 1.83.0 (90b35a623 2024-11-26)\n"
            "binary: rustc\ncommit-hash: 90b35a6239c3d8bdabc530a6a0816f7ff89a0aaf\n"
            "commit-date: 2024-11-26\nhost: "
            f"{target}\nrelease: 1.83.0\nLLVM version: 19.1.1"
        ),
        "cargo_version": "cargo 1.83.0 (5ffbef321 2024-10-29)",
        "rustup_components": ["cargo", "rust-std", "rustc"],
        "rust_targets": [target],
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
            target,
            "--out",
            "wheelhouse",
        ]
        + ([] if windows else ["--compatibility", "linux"]),
        "locked": True,
        "no_default_features": True,
        "features": FEATURES,
        "target_triple": target,
        "operating_system": operating_system,
        "architecture": "x86_64",
        "python": {
            "implementation": "CPython",
            "version": f"{python_minor}.9",
            "python_tag": python_tag,
            "abi_tag": abi_tag,
            "platform_tag": platform_tag,
        },
        "distribution": {"name": "poke-engine", "version": "0.0.48"},
        "wheel": {
            "filename": filename,
            "size": 123456,
            "sha256": DIGEST_B,
            "metadata_sha256": DIGEST_C,
            "wheel_metadata_sha256": DIGEST_D,
            "record_sha256": DIGEST_A,
            "record_entries": [
                {
                    "path": "poke_engine/__init__.py",
                    "sha256": DIGEST_B,
                    "size": 8,
                },
                {
                    "path": "poke_engine-0.0.48.dist-info/RECORD",
                    "sha256": None,
                    "size": None,
                },
            ],
            "root_is_purelib": False,
            "tags": [f"{python_tag}-{abi_tag}-{platform_tag}"],
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


def _artifact_index() -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    for operating_system in ("ubuntu-24.04", "windows-2025"):
        for python_minor in ("3.12", "3.13", "3.14"):
            build = _build_manifest(python_minor=python_minor, operating_system=operating_system)
            wheel = build["wheel"]
            python = build["python"]
            filename = wheel["filename"]
            cells.append(
                {
                    "cell_id": build["cell_id"],
                    "source_manifest_digest": DIGEST_A,
                    "build_manifest_digest": DIGEST_B,
                    "wheel_filename": filename,
                    "wheel_size": wheel["size"],
                    "wheel_sha256": wheel["sha256"],
                    "distribution_name": "poke-engine",
                    "distribution_version": "0.0.48",
                    "python_tag": python["python_tag"],
                    "abi_tag": python["abi_tag"],
                    "platform_tag": python["platform_tag"],
                    "operating_system": build["operating_system"],
                    "architecture": "x86_64",
                    "features": FEATURES,
                    "adapter_version": "battlebelief-poke-engine-v1",
                    "release_tag": RELEASE_TAG,
                    "release_asset_url": (
                        "https://github.com/chrismaghuhn/BattleBelief/releases/download/"
                        f"{RELEASE_TAG}/{filename}"
                    ),
                    "sentinel_fixture_digest": DIGEST_C,
                    "sentinel_result_digest": DIGEST_D,
                    "sentinel_configuration_digest": DIGEST_A,
                    "availability_status": "available",
                }
            )
    return {
        "schema_version": 1,
        "schema_id": "urn:battlebelief:schema:manifest:engine-artifact-index:v1",
        "manifest_id": "poke-engine-artifact-index-v1",
        "source_schema_id": "urn:battlebelief:schema:manifest:engine-source:v1",
        "build_schema_id": "urn:battlebelief:schema:manifest:engine-build:v1",
        "source_manifest_digest": DIGEST_A,
        "repository_url": "https://github.com/chrismaghuhn/BattleBelief",
        "release_tag": RELEASE_TAG,
        "release_prerelease": True,
        "release_assets_immutable": True,
        "cells": cells,
        "canonicalization_profile": "rfc8785-jcs-v1",
    }


@pytest.mark.parametrize(
    ("schema_name", "instance"),
    [
        ("engine-source.schema.json", _source_manifest()),
        ("engine-build.schema.json", _build_manifest()),
        (
            "engine-build.schema.json",
            _build_manifest(operating_system="windows-2025"),
        ),
        ("engine-artifact-index.schema.json", _artifact_index()),
    ],
)
def test_engine_manifest_schema_accepts_complete_v1_document(
    schema_name: str, instance: dict[str, Any]
) -> None:
    assert _issues(schema_name, instance) == []


@pytest.mark.parametrize("unsafe_path", ["C:/Users/alice/source", "/tmp/source", "../source"])
def test_engine_source_schema_rejects_local_or_escaping_paths(unsafe_path: str) -> None:
    instance = _source_manifest()
    instance["source_files"][0]["path"] = unsafe_path

    assert _issues("engine-source.schema.json", instance)


@pytest.mark.parametrize(
    ("mutation_path", "replacement"),
    [
        (("rust_toolchain",), "stable"),
        (("maturin_version",), "1.7"),
        (("locked",), False),
        (("no_default_features",), False),
        (("features",), ["poke-engine/gen9"]),
        (("features",), ["poke-engine/gen4", "poke-engine/gen9"]),
        (("target_triple",), "aarch64-unknown-linux-gnu"),
    ],
)
def test_engine_build_schema_rejects_unqualified_build_configuration(
    mutation_path: tuple[str, ...], replacement: object
) -> None:
    instance = _build_manifest()
    target: dict[str, Any] = instance
    for key in mutation_path[:-1]:
        target = target[key]
    target[mutation_path[-1]] = replacement

    assert _issues("engine-build.schema.json", instance)


def test_engine_build_schema_rejects_secrets_and_local_paths_in_environment() -> None:
    instance = _build_manifest()
    instance["build_environment"]["allowlist"].append({"name": "GITHUB_TOKEN", "value": "secret"})

    assert _issues("engine-build.schema.json", instance)


def test_engine_build_schema_requires_the_complete_environment_allowlist() -> None:
    instance = _build_manifest()
    instance["build_environment"]["allowlist"] = []

    assert _issues("engine-build.schema.json", instance)


def test_artifact_index_requires_exactly_six_unique_supported_cells() -> None:
    missing = _artifact_index()
    missing["cells"].pop()
    duplicate = _artifact_index()
    duplicate["cells"][-1] = copy.deepcopy(duplicate["cells"][0])

    assert _issues("engine-artifact-index.schema.json", missing)
    assert _issues("engine-artifact-index.schema.json", duplicate)


def test_available_artifact_cell_requires_release_and_sentinel_closure() -> None:
    instance = _artifact_index()
    del instance["cells"][0]["sentinel_result_digest"]

    assert _issues("engine-artifact-index.schema.json", instance)


def test_artifact_index_rejects_noncanonical_release_asset_url() -> None:
    instance = _artifact_index()
    instance["cells"][0]["release_asset_url"] = "https://example.invalid/latest.whl"

    assert _issues("engine-artifact-index.schema.json", instance)
