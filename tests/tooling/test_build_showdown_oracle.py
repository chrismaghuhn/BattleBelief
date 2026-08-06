"""Focused tests for the pinned local Showdown build tool."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest
from tools import build_showdown_oracle

from battlebelief_lab.oracle.showdown import installation
from battlebelief_lab.oracle.showdown.installation import (
    BuildOracleError,
    _build_manifest_id,
    _verify_and_remove_generated_config,
    _verify_generated_checkout_paths,
    _verify_index_flags,
    _verify_installed_dependency_tree,
    _verify_manifest_platform,
    clear_verified_dist,
    collect_dependency_file_records,
    collect_dist_records,
    derive_dependency_tree,
    verify_dependency_file_records,
    verify_dist_records,
    verify_historical_blob_records,
)


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def test_dist_records_are_sorted_and_detect_single_byte_mutation(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    (dist / "sim").mkdir(parents=True)
    (dist / "z.js").write_bytes(b"z")
    (dist / "sim" / "battle.js").write_bytes(b"original")

    records = collect_dist_records(dist)

    assert records == [
        {"path": "dist/sim/battle.js", "digest": _digest(b"original"), "size": 8},
        {"path": "dist/z.js", "digest": _digest(b"z"), "size": 1},
    ]
    verify_dist_records(dist, records)
    (dist / "sim" / "battle.js").write_bytes(b"mutated!")
    with pytest.raises(BuildOracleError, match="dist output differs"):
        verify_dist_records(dist, records)


def test_dist_verifier_rejects_missing_and_extra_outputs(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "one.js").write_bytes(b"one")
    expected = collect_dist_records(dist)

    (dist / "one.js").unlink()
    with pytest.raises(BuildOracleError, match="dist output differs"):
        verify_dist_records(dist, expected)

    (dist / "one.js").write_bytes(b"one")
    (dist / "extra.js").write_bytes(b"extra")
    with pytest.raises(BuildOracleError, match="dist output differs"):
        verify_dist_records(dist, expected)


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink semantics are validated on Linux CI")
def test_dist_records_reject_a_symlink_directory_even_when_its_target_is_in_bounds(
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "main.js").write_bytes(b"main")
    target = dist / "real-output"
    target.mkdir()
    (target / "hidden.js").write_bytes(b"hidden")
    (dist / "linked-output").symlink_to(target, target_is_directory=True)

    with pytest.raises(BuildOracleError, match="dist output is not regular"):
        collect_dist_records(dist)


def _create_windows_junction(link: Path, target: Path) -> None:
    completed = subprocess.run(
        ("cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert link.is_junction()


@pytest.mark.skipif(
    os.name != "nt", reason="Windows junction semantics are validated on Windows CI"
)
def test_dist_records_reject_a_windows_junction_directory(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "main.js").write_bytes(b"main")
    target = dist / "real-output"
    target.mkdir()
    (target / "hidden.js").write_bytes(b"hidden")
    _create_windows_junction(dist / "junction-output", target)

    with pytest.raises(BuildOracleError, match="dist output is not regular"):
        collect_dist_records(dist)


@pytest.mark.skipif(
    os.name != "nt", reason="Windows junction semantics are validated on Windows CI"
)
def test_dist_records_reject_a_windows_junction_root(tmp_path: Path) -> None:
    target = tmp_path / "real-dist"
    target.mkdir()
    (target / "main.js").write_bytes(b"main")
    dist = tmp_path / "dist"
    _create_windows_junction(dist, target)

    with pytest.raises(BuildOracleError, match="dist directory is invalid"):
        collect_dist_records(dist)


@pytest.mark.skipif(
    os.name != "nt", reason="Windows junction semantics are validated on Windows CI"
)
def test_dependency_records_reject_a_windows_junction_directory(tmp_path: Path) -> None:
    root = tmp_path / "checkout" / "node_modules"
    root.mkdir(parents=True)
    target = root / "real-package"
    target.mkdir()
    (target / "index.js").write_bytes(b"runtime")
    _create_windows_junction(root / "junction-package", target)

    with pytest.raises(BuildOracleError, match="dependency entry is not regular"):
        collect_dependency_file_records(root)


@pytest.mark.skipif(
    os.name != "nt", reason="Windows junction semantics are validated on Windows CI"
)
def test_dependency_records_reject_a_windows_junction_root(tmp_path: Path) -> None:
    target = tmp_path / "real-node-modules"
    target.mkdir()
    (target / "package.json").write_bytes(b"{}")
    root = tmp_path / "node_modules"
    _create_windows_junction(root, target)

    with pytest.raises(BuildOracleError, match="node_modules directory is invalid"):
        collect_dependency_file_records(root)


def test_clear_verified_dist_refuses_paths_outside_the_verified_checkout(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    outside = tmp_path / "outside"
    checkout.mkdir()
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(BuildOracleError, match="verified checkout"):
        clear_verified_dist(checkout, outside)

    assert (outside / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_dependency_tree_is_canonical_and_excludes_operational_paths() -> None:
    package_lock = {
        "lockfileVersion": 2,
        "packages": {
            "node_modules/z": {"version": "1.0.0", "integrity": "sha512-z"},
            "": {"name": "pokemon-showdown", "version": "0.11.11"},
            "node_modules/a": {"version": "2.0.0", "resolved": "https://example.invalid/a.tgz"},
        },
    }

    tree = derive_dependency_tree(package_lock)

    assert tree == [
        {"path": "", "name": "pokemon-showdown", "version": "0.11.11"},
        {
            "path": "node_modules/a",
            "resolved": "https://example.invalid/a.tgz",
            "version": "2.0.0",
        },
        {"integrity": "sha512-z", "path": "node_modules/z", "version": "1.0.0"},
    ]
    assert "C:/" not in str(tree)


def test_historical_source_records_use_git_blob_bytes_not_checkout_line_endings() -> None:
    records = ((".editorconfig", _digest(b"line\n"), 5),)

    verify_historical_blob_records(records, lambda path: b"line\n")

    with pytest.raises(BuildOracleError, match="historical source digest differs"):
        verify_historical_blob_records(records, lambda path: b"linx\n")


def test_pinned_source_acquisition_preserves_transport_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://controlled-proxy.invalid:8080")

    assert installation._source_transport_environment()["HTTPS_PROXY"] == (
        "http://controlled-proxy.invalid:8080"
    )


def test_git_verification_preserves_host_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYSTEMROOT", "C:/Windows")
    captured: dict[str, str] = {}

    def runner(
        _argv: tuple[str, ...], _cwd: Path, environment: dict[str, str]
    ) -> installation.CommandResult:
        captured.update(environment)
        return installation.CommandResult(0, b"verified", b"")

    assert installation._git(runner, Path("C:/checkout"), "rev-parse", "HEAD") == b"verified"
    assert captured["SYSTEMROOT"] == "C:/Windows"


def test_isolated_build_path_prefers_the_exact_approved_node(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "host-node"))
    approved_node = tmp_path / "approved node" / ("node.exe" if os.name == "nt" else "node")

    environment = installation._isolated_build_environment(
        tmp_path / "cache", tmp_path / "home", approved_node
    )

    assert environment["PATH"].split(os.pathsep)[0] == str(approved_node.parent)
    assert environment["PATH"].split(os.pathsep)[1:] == [str(tmp_path / "host-node")]


def test_installed_dependency_verification_permits_lockfile_optional_platform_packages(
    tmp_path: Path,
) -> None:
    _verify_installed_dependency_tree(
        tmp_path,
        ({"path": "node_modules/optional-platform", "version": "1.0.0", "optional": True},),
    )

    with pytest.raises(BuildOracleError, match="installed dependency is missing"):
        _verify_installed_dependency_tree(
            tmp_path,
            ({"path": "node_modules/required", "version": "1.0.0"},),
        )


def test_command_output_bound_covers_the_largest_bound_historical_source_blob() -> None:
    source = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "schemas/examples/showdown-oracle-source.example.json"
        ).read_text(encoding="utf-8")
    )

    assert (
        max(record["size"] for record in source["source_files"])
        <= installation.MAX_COMMAND_OUTPUT_BYTES
    )


def test_candidate_build_manifest_id_is_schema_compatible_on_x86_64() -> None:
    assert _build_manifest_id("candidate", "windows", "x86_64", "22.23.2") == (
        "showdown-oracle-build-candidate-windows-x86-64-node-22-23-2"
    )


def test_ruleset_extractor_uses_codepoint_not_host_locale_ordering() -> None:
    source = installation.ruleset_extractor_bytes().decode("utf-8")

    assert "localeCompare" not in source


def test_index_flags_reject_assume_unchanged_and_skip_worktree_entries() -> None:
    verifier = _verify_index_flags

    verifier(b"H sim/battle.ts\0H package.json\0")

    for flagged in (b"h sim/battle.ts\0", b"S sim/battle.ts\0"):
        with pytest.raises(BuildOracleError, match="index flags differ"):
            verifier(flagged)


def test_generated_checkout_paths_are_allowlisted_by_phase() -> None:
    verifier = _verify_generated_checkout_paths

    with pytest.raises(BuildOracleError, match="generated checkout path differs"):
        verifier(b"!! node_modules/\0", phase="acquisition")

    verifier(b"!! node_modules/\0!! dist/\0", phase="post_build")
    for path in (b"?? config/config.js\0", b"!! config/config.js\0", b"?? outside.txt\0"):
        with pytest.raises(BuildOracleError, match="generated checkout path differs"):
            verifier(path, phase="post_build")


def test_generated_showdown_config_must_match_example_then_is_removed(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    config = checkout / "config"
    config.mkdir(parents=True)
    (config / "config-example.js").write_bytes(b"module.exports = {};\n")
    (checkout / ".gitignore").write_text("/config/config.js\n", encoding="utf-8")
    subprocess.run(("git", "init", "--quiet"), cwd=checkout, check=True)
    subprocess.run(("git", "add", "."), cwd=checkout, check=True)
    subprocess.run(
        (
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "initial",
        ),
        cwd=checkout,
        check=True,
    )
    commit = subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=checkout).decode().strip()
    generated = config / "config.js"
    generated.write_bytes(b"module.exports = {};\n")

    _verify_and_remove_generated_config(checkout, commit)

    assert not generated.exists()
    generated.write_bytes(b"module.exports = {changed: true};\n")
    with pytest.raises(BuildOracleError, match="generated config differs"):
        _verify_and_remove_generated_config(checkout, commit)
    assert generated.exists()


def test_dependency_file_closure_rejects_mutation_missing_and_extra_outputs(tmp_path: Path) -> None:
    root = tmp_path / "checkout" / "node_modules"
    package = root / "package"
    package.mkdir(parents=True)
    (package / "index.js").write_bytes(b"original")

    records = collect_dependency_file_records(root)
    assert records == [
        {
            "kind": "file",
            "path": "node_modules/package/index.js",
            "digest": _digest(b"original"),
            "size": 8,
        }
    ]
    verify_dependency_file_records(root, records)

    (package / "index.js").write_bytes(b"mutated!")
    with pytest.raises(BuildOracleError, match="dependency files differ"):
        verify_dependency_file_records(root, records)
    (package / "index.js").unlink()
    with pytest.raises(BuildOracleError, match="dependency files differ"):
        verify_dependency_file_records(root, records)
    (package / "index.js").write_bytes(b"original")
    (package / "extra.js").write_bytes(b"extra")
    with pytest.raises(BuildOracleError, match="dependency files differ"):
        verify_dependency_file_records(root, records)


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink semantics are validated on Linux CI")
def test_dependency_file_closure_records_safe_relative_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "checkout" / "node_modules"
    package = root / "package"
    package.mkdir(parents=True)
    (package / "index.js").write_bytes(b"runtime")
    binary = root / ".bin"
    binary.mkdir()
    (binary / "package").symlink_to("../package/index.js")

    records = collect_dependency_file_records(root)

    assert {
        "kind": "symlink",
        "path": "node_modules/.bin/package",
        "target": "../package/index.js",
    } in records


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink semantics are validated on Linux CI")
def test_dependency_file_closure_rejects_escaping_symlink(tmp_path: Path) -> None:
    root = tmp_path / "checkout" / "node_modules"
    root.mkdir(parents=True)
    (root / "escape").symlink_to("../../outside")

    with pytest.raises(BuildOracleError, match="dependency symlink escapes"):
        collect_dependency_file_records(root)


def test_manifest_platform_identity_must_match_actual_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(installation, "_platform_identity", lambda: ("linux", "arm64"))

    with pytest.raises(BuildOracleError, match="build platform differs"):
        _verify_manifest_platform("windows", "x86_64")


def test_cli_paths_reject_output_aliases_and_checkout_local_operational_paths(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    source = tmp_path / "source.json"
    source.write_text("{}", encoding="utf-8")

    for output, cache, home in (
        (source, tmp_path / "cache", tmp_path / "home"),
        (checkout / "build.json", tmp_path / "cache", tmp_path / "home"),
        (tmp_path / "build.json", checkout / "cache", tmp_path / "home"),
        (tmp_path / "build.json", tmp_path / "cache", checkout / "home"),
    ):
        with pytest.raises(BuildOracleError, match="CLI path aliases are forbidden"):
            build_showdown_oracle._validate_cli_paths(
                source_manifest_path=source,
                checkout_directory=checkout,
                cache_directory=cache,
                home_directory=home,
                output_path=output,
                allow_existing_output=True,
            )

    output = tmp_path / "build.json"
    output.write_text("old", encoding="utf-8")
    with pytest.raises(BuildOracleError, match="output already exists"):
        build_showdown_oracle._validate_cli_paths(
            source_manifest_path=source,
            checkout_directory=checkout,
            cache_directory=tmp_path / "cache",
            home_directory=tmp_path / "home",
            output_path=output,
            allow_existing_output=False,
        )
