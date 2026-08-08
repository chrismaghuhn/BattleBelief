"""Focused tests for controlled poke-engine source and build provenance."""

from __future__ import annotations

import base64
import hashlib
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
import tools.build_poke_engine_wheel as build_tool
from tools.build_poke_engine_wheel import (
    BuildPokeEngineError,
    acquire_pinned_source,
    build_argv,
    collect_source_records,
    create_build_manifest,
    create_source_manifest,
    inspect_wheel,
    validate_build_configuration,
    verify_source_checkout,
)

FEATURES = ("poke-engine/gen9", "poke-engine/terastallization")


def test_controlled_command_times_out_with_a_stable_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(build_tool, "COMMAND_TIMEOUT_SECONDS", 0.01)

    with pytest.raises(BuildPokeEngineError, match="exceeded its time bound"):
        build_tool._run(
            (sys.executable, "-c", "import time; time.sleep(1)"),
            cwd=tmp_path,
        )


def test_controlled_command_stops_at_the_output_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(build_tool, "MAX_COMMAND_OUTPUT_BYTES", 8)

    with pytest.raises(BuildPokeEngineError, match="output exceeds the safety bound"):
        build_tool._run(
            (sys.executable, "-c", "import sys; sys.stdout.write('x' * 9)"),
            cwd=tmp_path,
        )


def test_controlled_build_environment_excludes_ambient_build_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUSTFLAGS", "--cfg injected")
    monkeypatch.setenv("CARGO_BUILD_TARGET", "attacker-target")
    monkeypatch.setenv("CC", "attacker-compiler")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setenv("ProgramFiles(x86)", r"C:\Program Files (x86)")
    monkeypatch.setenv("PATH", os.pathsep.join((str(tmp_path / "ambient"), "base")))
    cargo = tmp_path / ".cargo" / "bin" / "cargo"
    rustc = tmp_path / ".rust" / "bin" / "rustc"

    environment = build_tool._controlled_build_environment(
        cargo_executable=cargo,
        rustc_executable=rustc,
    )

    assert environment["CARGO_INCREMENTAL"] == "false"
    assert environment["CARGO_HOME"] == "../battlebelief-engine-cargo-home"
    assert environment["CARGO_NET_OFFLINE"] == "true"
    assert environment["CARGO_PROFILE_RELEASE_DEBUG"] == "0"
    assert environment["PYTHONUTF8"] == "1"
    assert environment["SOURCE_DATE_EPOCH"] == "1784471591"
    assert environment["PATH"].split(os.pathsep)[:2] == [str(cargo.parent), str(rustc.parent)]
    assert environment["ProgramFiles(x86)"] == r"C:\Program Files (x86)"
    assert "RUSTFLAGS" not in environment
    assert "CARGO_BUILD_TARGET" not in environment
    assert "CC" not in environment
    assert "GITHUB_TOKEN" not in environment


@pytest.mark.parametrize(
    ("command", "message"),
    [
        ("acquire", "PASS: pinned poke-engine source acquired"),
        ("source", "PASS: pinned poke-engine source manifest created"),
        ("verify-source", "PASS: pinned poke-engine source provenance verified"),
        ("build", "PASS: controlled poke-engine wheel built and bound"),
    ],
)
def test_success_message_describes_the_completed_subcommand(command: str, message: str) -> None:
    assert build_tool._success_message(command) == message


def test_source_acquisition_refuses_an_existing_target(tmp_path: Path) -> None:
    checkout = tmp_path / "source"
    checkout.mkdir()
    marker = checkout / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(BuildPokeEngineError, match="checkout already exists"):
        acquire_pinned_source(checkout)

    assert marker.read_text(encoding="utf-8") == "keep"


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.check_output(("git", *arguments), cwd=repository).decode().strip()


def _source_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "source"
    repository.mkdir()
    subprocess.run(("git", "init", "--quiet"), cwd=repository, check=True)
    subprocess.run(("git", "config", "user.name", "Test"), cwd=repository, check=True)
    subprocess.run(
        ("git", "config", "user.email", "test@example.invalid"),
        cwd=repository,
        check=True,
    )
    subprocess.run(("git", "config", "commit.gpgSign", "false"), cwd=repository, check=True)
    subprocess.run(("git", "config", "tag.gpgSign", "false"), cwd=repository, check=True)
    (repository / "Cargo.lock").write_bytes(b"lock\n")
    (repository / "Cargo.toml").write_text(
        '[workspace]\nmembers = ["poke-engine-py"]\n', encoding="utf-8"
    )
    (repository / "LICENSE").write_bytes(b"license\n")
    package = repository / "poke-engine-py"
    package.mkdir()
    (package / "Cargo.toml").write_text('[package]\nname = "fixture"\n', encoding="utf-8")
    subprocess.run(("git", "add", "."), cwd=repository, check=True)
    subprocess.run(("git", "commit", "--quiet", "-m", "fixture"), cwd=repository, check=True)
    subprocess.run(
        ("git", "tag", "-a", "v0.0.48", "-m", "fixture tag"),
        cwd=repository,
        check=True,
    )
    return repository


def test_source_records_are_sorted_and_use_committed_blob_bytes(tmp_path: Path) -> None:
    repository = _source_repository(tmp_path)
    commit = _git(repository, "rev-parse", "HEAD")

    records = collect_source_records(repository, commit)

    assert [record["path"] for record in records] == sorted(record["path"] for record in records)
    cargo_lock = next(record for record in records if record["path"] == "Cargo.lock")
    assert cargo_lock["size"] == 5
    assert cargo_lock["sha256"] == (
        "sha256:d8c9f2728aa278ebcd33ccedf3ad309a866870ad5fb93a03526b4b7655c9e911"
    )

    (repository / "Cargo.lock").write_bytes(b"changed working tree\n")
    assert (
        next(
            record
            for record in collect_source_records(repository, commit)
            if record["path"] == "Cargo.lock"
        )
        == cargo_lock
    )


def test_source_manifest_round_trip_rejects_dirty_tree_and_digest_changes(
    tmp_path: Path,
) -> None:
    repository = _source_repository(tmp_path)
    manifest = create_source_manifest(
        repository,
        retrieved_on="2026-08-06",
        repository_url="https://example.invalid/poke-engine",
        observed_tag="v0.0.48",
    )

    verify_source_checkout(repository, manifest)

    (repository / "Cargo.lock").write_bytes(b"changed\n")
    with pytest.raises(BuildPokeEngineError, match="source tree is dirty"):
        verify_source_checkout(repository, manifest)

    subprocess.run(("git", "restore", "Cargo.lock"), cwd=repository, check=True)
    manifest["cargo_lock"]["sha256"] = "sha256:" + "0" * 64
    with pytest.raises(BuildPokeEngineError, match=r"Cargo\.lock digest differs"):
        verify_source_checkout(repository, manifest)


@pytest.mark.parametrize(
    ("rust_toolchain", "maturin_version", "target", "features", "locked", "no_default"),
    [
        ("stable", "1.7.1", "x86_64-pc-windows-msvc", FEATURES, True, True),
        ("1.83.0", "1.7", "x86_64-pc-windows-msvc", FEATURES, True, True),
        ("1.83.0", "1.7.1", "aarch64-unknown-linux-gnu", FEATURES, True, True),
        ("1.83.0", "1.7.1", "x86_64-pc-windows-msvc", ("poke-engine/gen9",), True, True),
        (
            "1.83.0",
            "1.7.1",
            "x86_64-pc-windows-msvc",
            ("poke-engine/gen4", *FEATURES),
            True,
            True,
        ),
        ("1.83.0", "1.7.1", "x86_64-pc-windows-msvc", FEATURES, False, True),
        ("1.83.0", "1.7.1", "x86_64-pc-windows-msvc", FEATURES, True, False),
    ],
)
def test_build_configuration_fails_closed(
    rust_toolchain: str,
    maturin_version: str,
    target: str,
    features: tuple[str, ...],
    locked: bool,
    no_default: bool,
) -> None:
    with pytest.raises(BuildPokeEngineError):
        validate_build_configuration(
            rust_toolchain=rust_toolchain,
            maturin_version=maturin_version,
            target_triple=target,
            features=features,
            locked=locked,
            no_default_features=no_default,
        )


def test_exact_build_configuration_is_accepted() -> None:
    validate_build_configuration(
        rust_toolchain="1.83.0",
        maturin_version="1.7.1",
        target_triple="x86_64-unknown-linux-gnu",
        features=FEATURES,
        locked=True,
        no_default_features=True,
    )


def test_build_argv_is_locked_feature_explicit_and_platform_truthful() -> None:
    linux = build_argv("x86_64-unknown-linux-gnu")
    windows = build_argv("x86_64-pc-windows-msvc")

    for arguments in (linux, windows):
        assert "--release" in arguments
        assert "--strip" in arguments
        assert "--locked" in arguments
        assert "--no-default-features" in arguments
        assert arguments[arguments.index("--features") + 1] == ",".join(FEATURES)
        assert "gen4" not in " ".join(arguments)
    assert linux[-2:] == ["--compatibility", "linux"]
    assert "--compatibility" not in windows


def _write_fixture_wheel(
    path: Path, *, version: str = "0.0.48", dist_info_version: str = "0.0.48"
) -> None:
    dist_info = f"poke_engine-{dist_info_version}.dist-info"
    metadata = f"Metadata-Version: 2.1\nName: poke-engine\nVersion: {version}\n".encode()
    wheel_metadata = b"Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: cp314-none-win_amd64\n"

    def record_hash(content: bytes) -> str:
        encoded = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).decode().rstrip("=")
        return f"sha256={encoded}"

    record = (
        f"{dist_info}/METADATA,{record_hash(metadata)},{len(metadata)}\n"
        f"{dist_info}/WHEEL,{record_hash(wheel_metadata)},{len(wheel_metadata)}\n"
        f"{dist_info}/RECORD,,\n"
    )
    with zipfile.ZipFile(path, "w") as wheel:
        wheel.writestr(f"{dist_info}/METADATA", metadata)
        wheel.writestr(f"{dist_info}/WHEEL", wheel_metadata)
        wheel.writestr(f"{dist_info}/RECORD", record)


def test_wheel_inspection_binds_distribution_metadata_and_record(tmp_path: Path) -> None:
    wheel_path = tmp_path / "poke_engine-0.0.48-cp314-none-win_amd64.whl"
    _write_fixture_wheel(wheel_path)

    wheel = inspect_wheel(
        wheel_path,
        python_tag="cp314",
        abi_tag="none",
        platform_tag="win_amd64",
    )

    assert wheel["filename"] == wheel_path.name
    assert wheel["root_is_purelib"] is False
    assert wheel["tags"] == ["cp314-none-win_amd64"]
    assert wheel["sha256"].startswith("sha256:")
    assert wheel["metadata_sha256"].startswith("sha256:")
    assert wheel["wheel_metadata_sha256"].startswith("sha256:")
    assert wheel["record_sha256"].startswith("sha256:")
    assert wheel["record_entries"][-1] == {
        "path": "poke_engine-0.0.48.dist-info/WHEEL",
        "sha256": "sha256:"
        + hashlib.sha256(
            b"Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: cp314-none-win_amd64\n"
        ).hexdigest(),
        "size": 68,
    }


def test_wheel_inspection_rejects_wrong_distribution_version(tmp_path: Path) -> None:
    wheel_path = tmp_path / "poke_engine-0.0.48-cp314-none-win_amd64.whl"
    _write_fixture_wheel(wheel_path, version="0.0.47")

    with pytest.raises(BuildPokeEngineError, match="wheel distribution identity differs"):
        inspect_wheel(
            wheel_path,
            python_tag="cp314",
            abi_tag="none",
            platform_tag="win_amd64",
        )


@pytest.mark.parametrize("distribution_version", ["0.0.48", "0.0.49", "0.0.50"])
def test_wheel_inspection_accepts_each_approved_distribution_version(
    tmp_path: Path, distribution_version: str
) -> None:
    wheel_path = tmp_path / f"poke_engine-{distribution_version}-cp314-none-win_amd64.whl"
    _write_fixture_wheel(
        wheel_path,
        version=distribution_version,
        dist_info_version=distribution_version,
    )

    inspected = inspect_wheel(
        wheel_path,
        python_tag="cp314",
        abi_tag="none",
        platform_tag="win_amd64",
        distribution_version=distribution_version,
    )

    assert inspected["filename"] == wheel_path.name


def test_wheel_inspection_rejects_an_unapproved_distribution_version(tmp_path: Path) -> None:
    with pytest.raises(BuildPokeEngineError, match="wheel distribution identity differs"):
        inspect_wheel(
            tmp_path / "poke_engine-0.0.51-cp314-none-win_amd64.whl",
            python_tag="cp314",
            abi_tag="none",
            platform_tag="win_amd64",
            distribution_version="0.0.51",
        )


def test_build_manifest_binds_exact_cell_without_operational_paths() -> None:
    source_manifest = {
        "schema_id": "urn:battlebelief:schema:manifest:engine-source:v1",
        "commit": "bcf13823abc162a608e187b26bbf683f759f385e",
    }
    wheel = {
        "filename": "poke_engine-0.0.48-cp314-none-win_amd64.whl",
        "size": 123,
        "sha256": "sha256:" + "a" * 64,
        "metadata_sha256": "sha256:" + "b" * 64,
        "wheel_metadata_sha256": "sha256:" + "c" * 64,
        "record_sha256": "sha256:" + "d" * 64,
        "record_entries": [
            {
                "path": "poke_engine/__init__.py",
                "sha256": "sha256:" + "a" * 64,
                "size": 8,
            },
            {
                "path": "poke_engine-0.0.48.dist-info/RECORD",
                "sha256": None,
                "size": None,
            },
        ],
        "root_is_purelib": False,
        "tags": ["cp314-none-win_amd64"],
    }

    manifest = create_build_manifest(
        source_manifest=source_manifest,
        rustc_vv=(
            "rustc 1.83.0 (90b35a623 2024-11-26)\n"
            "binary: rustc\ncommit-hash: 90b35a6239c3d8bdabc530a6a0816f7ff89a0aaf\n"
            "commit-date: 2024-11-26\nhost: x86_64-pc-windows-msvc\n"
            "release: 1.83.0\nLLVM version: 19.1.1"
        ),
        cargo_version="cargo 1.83.0 (5ffbef321 2024-10-29)",
        maturin_version="1.7.1",
        target_triple="x86_64-pc-windows-msvc",
        operating_system="windows-2025",
        python_version="3.14.2",
        wheel=wheel,
    )

    assert manifest["cell_id"] == "windows-2025-x86_64-cp314"
    assert manifest["python"] == {
        "implementation": "CPython",
        "version": "3.14.2",
        "python_tag": "cp314",
        "abi_tag": "none",
        "platform_tag": "win_amd64",
    }
    assert manifest["features"] == list(FEATURES)
    assert manifest["build_environment"]["allowlist"][0] == {
        "name": "CARGO_HOME",
        "value": "../battlebelief-engine-cargo-home",
    }

    def string_values(value: object) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [item for child in value.values() for item in string_values(child)]
        if isinstance(value, list):
            return [item for child in value for item in string_values(child)]
        return []

    values = string_values(manifest)
    assert all("C:\\Users" not in value for value in values)
    assert all("/home/" not in value for value in values)
    assert all("GITHUB_TOKEN" not in value for value in values)
    assert "SOURCE_DATE_EPOCH" in values
