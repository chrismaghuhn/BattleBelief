"""Build and verify one locally installed, pinned Pokemon Showdown oracle.

This module is the single implementation of Showdown source/build verification.
The thin ``tools/build_showdown_oracle.py`` command delegates to it, while the
Lab session invokes :func:`verify_build_manifest` immediately before every
simulator process.  Verification is read-only: it never runs npm, performs a
build, or contacts the network.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from battlebelief_core.canonicalization import manifest_digest
from battlebelief_lab.oracle.showdown.errors import OracleFailureClass
from battlebelief_lab.oracle.showdown.manifests import (
    ShowdownBuildManifest,
    ShowdownSourceManifest,
)

UPSTREAM_URL = "https://github.com/smogon/pokemon-showdown"
SHOWDOWN_COMMIT = "6a1836dd71c0718e923206f3d089e61074410868"
NPM_CI_ARGV = ("npm", "ci", "--no-audit", "--no-fund")
NPM_BUILD_ARGV = ("npm", "run", "build")
SIMULATOR_ARGV = ("node", "pokemon-showdown", "--skip-build", "simulate-battle")
NPM_CONFIG = {
    "audit": "false",
    "fund": "false",
    "ignore-scripts": "false",
    "package-lock": "true",
    "update-notifier": "false",
}
RULESET_EXTRACTOR_DIGEST = "sha256:82ae637f73a81aa9bafeab27fc0bc057d1fc281660985898a9c0006159e56f58"
# The selected historical source tree has a 3.8 MiB tracked blob.  The cap is
# intentionally finite but must admit that manifest-bound blob for `git cat-file`.
MAX_COMMAND_OUTPUT_BYTES = 16 * 1024 * 1024


class BuildOracleError(RuntimeError):
    """A stable failure class plus non-canonical diagnostic detail."""

    def __init__(self, failure_class: OracleFailureClass, detail: str) -> None:
        self.failure_class = failure_class
        super().__init__(detail)


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Bounded result returned by the injected process launcher."""

    returncode: int
    stdout: bytes
    stderr: bytes


CommandRunner = Callable[[Sequence[str], Path, Mapping[str, str]], CommandResult]
BlobReader = Callable[[str], bytes]


def _ruleset_extractor_resource() -> resources.abc.Traversable:
    return resources.files("battlebelief_lab.oracle.showdown").joinpath(
        "assets", "showdown_ruleset_snapshot.cjs"
    )


def ruleset_extractor_bytes() -> bytes:
    """Return the fixed, wheel-packaged ruleset extractor source bytes."""

    try:
        source = _ruleset_extractor_resource().read_bytes()
    except (FileNotFoundError, ModuleNotFoundError) as error:
        raise BuildOracleError(
            OracleFailureClass.BUILD_FAILED, "ruleset extractor is missing"
        ) from error
    if _sha256(source) != RULESET_EXTRACTOR_DIGEST:
        raise BuildOracleError(OracleFailureClass.BUILD_FAILED, "ruleset extractor digest differs")
    return source


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _strict_json(data: bytes, *, label: str) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite value {value}")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key {key}")
            result[key] = value
        return result

    try:
        decoded = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise BuildOracleError(
            OracleFailureClass.BUILD_FAILED, f"{label} is not strict JSON"
        ) from error
    if not isinstance(decoded, dict):
        raise BuildOracleError(OracleFailureClass.BUILD_FAILED, f"{label} must be an object")
    return decoded


def _safe_relative(path: Path, root: Path) -> str:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise BuildOracleError(
            OracleFailureClass.BUILD_OUTPUT_MISSING, "path escapes root"
        ) from error
    return relative.as_posix()


def _file_record(path: Path, root: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise BuildOracleError(
            OracleFailureClass.BUILD_OUTPUT_MISSING, "output must be a regular file"
        )
    content = path.read_bytes()
    return {"path": _safe_relative(path, root), "digest": _sha256(content), "size": len(content)}


def verify_historical_blob_records(
    records: Sequence[tuple[str, str, int]], read_blob: BlobReader
) -> None:
    """Validate a source manifest against Git blob bytes, never checkout filters.

    Git attributes legitimately materialize CRLF working-tree files on Windows.
    Historical blob bytes are therefore the only valid source-manifest evidence.
    """

    for relative, digest, size in records:
        blob = read_blob(relative)
        if len(blob) != size:
            raise BuildOracleError(
                OracleFailureClass.SOURCE_COMMIT_MISMATCH, "historical source size differs"
            )
        if _sha256(blob) != digest:
            raise BuildOracleError(
                OracleFailureClass.SOURCE_COMMIT_MISMATCH, "historical source digest differs"
            )


def collect_dist_records(dist_directory: Path) -> list[dict[str, object]]:
    """Return sorted complete regular-file records below the required ``dist`` root."""

    if dist_directory.name != "dist":
        raise BuildOracleError(OracleFailureClass.BUILD_OUTPUT_MISSING, "dist directory is missing")
    try:
        root_mode = dist_directory.lstat().st_mode
    except OSError as error:
        raise BuildOracleError(
            OracleFailureClass.BUILD_OUTPUT_MISSING, "dist directory is missing"
        ) from error
    if dist_directory.is_junction() or stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        raise BuildOracleError(OracleFailureClass.BUILD_OUTPUT_MISSING, "dist directory is invalid")
    root = dist_directory.parent.resolve()
    records: list[dict[str, object]] = []

    def visit(directory: Path) -> None:
        try:
            entries = sorted(directory.iterdir(), key=lambda candidate: candidate.name)
        except OSError as error:
            raise BuildOracleError(
                OracleFailureClass.BUILD_OUTPUT_MISSING, "dist directory is unreadable"
            ) from error
        for candidate in entries:
            try:
                mode = candidate.lstat().st_mode
            except OSError as error:
                raise BuildOracleError(
                    OracleFailureClass.BUILD_OUTPUT_MISSING, "dist entry is unreadable"
                ) from error
            if (
                candidate.is_junction()
                or stat.S_ISLNK(mode)
                or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode))
            ):
                raise BuildOracleError(
                    OracleFailureClass.BUILD_OUTPUT_MISSING, "dist output is not regular"
                )
            if stat.S_ISDIR(mode):
                visit(candidate)
            else:
                records.append(_file_record(candidate, root))

    visit(dist_directory)
    if not records:
        raise BuildOracleError(
            OracleFailureClass.BUILD_OUTPUT_MISSING, "dist directory has no files"
        )
    paths = [str(record["path"]) for record in records]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise BuildOracleError(
            OracleFailureClass.BUILD_OUTPUT_MISSING, "dist records are not canonical"
        )
    return records


def verify_dist_records(dist_directory: Path, expected: Sequence[Mapping[str, object]]) -> None:
    """Fail closed for missing, extra, or mutated built output bytes."""

    try:
        actual = collect_dist_records(dist_directory)
    except BuildOracleError as error:
        if error.failure_class is OracleFailureClass.BUILD_OUTPUT_MISSING:
            raise BuildOracleError(
                OracleFailureClass.BUILD_OUTPUT_MISSING, "dist output differs"
            ) from error
        raise
    if actual != [dict(record) for record in expected]:
        raise BuildOracleError(OracleFailureClass.BUILD_OUTPUT_MISSING, "dist output differs")


def _dependency_relative_path(path: Path, node_modules_directory: Path) -> str:
    try:
        return path.relative_to(node_modules_directory.parent).as_posix()
    except ValueError as error:
        raise BuildOracleError(
            OracleFailureClass.BUILD_OUTPUT_MISSING, "dependency path escapes node_modules"
        ) from error


def _dependency_symlink_record(path: Path, node_modules_directory: Path) -> dict[str, object]:
    try:
        target = os.readlink(path)
    except OSError as error:
        raise BuildOracleError(
            OracleFailureClass.BUILD_OUTPUT_MISSING, "dependency symlink is unreadable"
        ) from error
    if not target or "\\" in target or Path(target).is_absolute():
        raise BuildOracleError(
            OracleFailureClass.BUILD_OUTPUT_MISSING, "dependency symlink target is unsafe"
        )
    try:
        resolved = (path.parent / target).resolve(strict=True)
        resolved.relative_to(node_modules_directory.resolve())
    except (OSError, ValueError) as error:
        raise BuildOracleError(
            OracleFailureClass.BUILD_OUTPUT_MISSING, "dependency symlink escapes node_modules"
        ) from error
    return {
        "kind": "symlink",
        "path": _dependency_relative_path(path, node_modules_directory),
        "target": target,
    }


def collect_dependency_file_records(node_modules_directory: Path) -> list[dict[str, object]]:
    """Return complete sorted runtime records without following symlink directories."""

    root = node_modules_directory.resolve()
    try:
        root_mode = node_modules_directory.lstat().st_mode
    except OSError as error:
        raise BuildOracleError(
            OracleFailureClass.BUILD_OUTPUT_MISSING, "node_modules directory is missing"
        ) from error
    if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        raise BuildOracleError(
            OracleFailureClass.BUILD_OUTPUT_MISSING, "node_modules directory is invalid"
        )
    records: list[dict[str, object]] = []

    def visit(directory: Path) -> None:
        try:
            entries = sorted(directory.iterdir(), key=lambda candidate: candidate.name)
        except OSError as error:
            raise BuildOracleError(
                OracleFailureClass.BUILD_OUTPUT_MISSING, "dependency directory is unreadable"
            ) from error
        for candidate in entries:
            try:
                mode = candidate.lstat().st_mode
            except OSError as error:
                raise BuildOracleError(
                    OracleFailureClass.BUILD_OUTPUT_MISSING, "dependency entry is unreadable"
                ) from error
            if stat.S_ISLNK(mode):
                records.append(_dependency_symlink_record(candidate, root))
            elif stat.S_ISDIR(mode):
                visit(candidate)
            elif stat.S_ISREG(mode):
                content = candidate.read_bytes()
                records.append(
                    {
                        "kind": "file",
                        "path": _dependency_relative_path(candidate, root),
                        "digest": _sha256(content),
                        "size": len(content),
                    }
                )
            else:
                raise BuildOracleError(
                    OracleFailureClass.BUILD_OUTPUT_MISSING, "dependency entry is not regular"
                )

    visit(root)
    records.sort(key=lambda record: str(record["path"]))
    paths = [str(record["path"]) for record in records]
    if not records or paths != sorted(paths) or len(paths) != len(set(paths)):
        raise BuildOracleError(
            OracleFailureClass.BUILD_OUTPUT_MISSING, "dependency files are not canonical"
        )
    return records


def verify_dependency_file_records(
    node_modules_directory: Path, expected: Sequence[Mapping[str, object]]
) -> None:
    """Fail closed when any installed runtime file or link differs from the manifest."""

    try:
        actual = collect_dependency_file_records(node_modules_directory)
    except BuildOracleError as error:
        if error.failure_class is OracleFailureClass.BUILD_OUTPUT_MISSING:
            raise BuildOracleError(
                OracleFailureClass.BUILD_OUTPUT_MISSING, "dependency files differ"
            ) from error
        raise
    if actual != [dict(record) for record in expected]:
        raise BuildOracleError(OracleFailureClass.BUILD_OUTPUT_MISSING, "dependency files differ")


def clear_verified_dist(checkout_directory: Path, dist_directory: Path) -> None:
    """Remove stale ignored output only when it is exactly ``checkout/dist``."""

    checkout = checkout_directory.resolve()
    dist = dist_directory.resolve()
    if dist != checkout / "dist":
        raise BuildOracleError(
            OracleFailureClass.SOURCE_DIRTY,
            "refusing to remove a path outside the verified checkout dist directory",
        )
    if dist.exists():
        shutil.rmtree(dist)


def derive_dependency_tree(package_lock: Mapping[str, object]) -> list[dict[str, object]]:
    """Derive a canonical, path-free resolved dependency inventory from lock v2.

    The complete object is reconstructible from the source-bound immutable
    ``package-lock.json``.  The post-install verifier additionally checks the
    installed package versions against this inventory.
    """

    packages = package_lock.get("packages")
    if not isinstance(packages, Mapping):
        raise BuildOracleError(
            OracleFailureClass.LOCKFILE_MISMATCH, "lockfile packages are missing"
        )
    tree: list[dict[str, object]] = []
    allowed = ("name", "version", "resolved", "integrity", "link", "dev", "optional")
    for path, raw_entry in packages.items():
        if not isinstance(path, str) or not isinstance(raw_entry, Mapping):
            raise BuildOracleError(
                OracleFailureClass.LOCKFILE_MISMATCH, "lockfile package entry is invalid"
            )
        if path and (path.startswith("/") or ".." in Path(path).parts):
            raise BuildOracleError(
                OracleFailureClass.LOCKFILE_MISMATCH, "lockfile package path is unsafe"
            )
        entry: dict[str, object] = {"path": path}
        for key in allowed:
            value = raw_entry.get(key)
            if value is not None:
                if type(value) not in {str, bool}:
                    raise BuildOracleError(
                        OracleFailureClass.LOCKFILE_MISMATCH, "lockfile dependency value is invalid"
                    )
                entry[key] = value
        if path == "" and (entry.get("name") != "pokemon-showdown" or "version" not in entry):
            raise BuildOracleError(OracleFailureClass.LOCKFILE_MISMATCH, "lockfile root is invalid")
        if path and "version" not in entry and not entry.get("link", False):
            raise BuildOracleError(
                OracleFailureClass.LOCKFILE_MISMATCH, "lockfile package version is missing"
            )
        tree.append(entry)
    tree.sort(key=lambda entry: str(entry["path"]))
    if not tree or tree[0].get("path") != "":
        raise BuildOracleError(OracleFailureClass.LOCKFILE_MISMATCH, "lockfile root is missing")
    return tree


def dependency_tree_digest(package_lock: Mapping[str, object]) -> str:
    return manifest_digest(derive_dependency_tree(package_lock))


def _verify_installed_dependency_tree(
    checkout_directory: Path, tree: Sequence[Mapping[str, object]]
) -> None:
    for entry in tree:
        path = entry["path"]
        if path == "" or entry.get("link") is True:
            continue
        if not isinstance(path, str):
            raise BuildOracleError(
                OracleFailureClass.LOCKFILE_MISMATCH, "lockfile package path is invalid"
            )
        package_json = checkout_directory / Path(*path.split("/")) / "package.json"
        if not package_json.is_file():
            if entry.get("optional") is True:
                continue
            raise BuildOracleError(
                OracleFailureClass.LOCKFILE_MISMATCH, "installed dependency is missing"
            )
        installed = _strict_json(
            package_json.read_bytes(), label="installed dependency package metadata"
        )
        if installed.get("version") != entry.get("version"):
            raise BuildOracleError(
                OracleFailureClass.LOCKFILE_MISMATCH, "installed dependency version differs"
            )


def _run_subprocess(
    argv: Sequence[str], cwd: Path, environment: Mapping[str, str]
) -> CommandResult:
    try:
        completed = subprocess.run(
            list(argv),
            cwd=cwd,
            env=dict(environment),
            check=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=300,
        )
    except FileNotFoundError as error:
        raise BuildOracleError(
            OracleFailureClass.NODE_NOT_FOUND, "required executable is unavailable"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise BuildOracleError(
            OracleFailureClass.BUILD_FAILED, "build command timed out"
        ) from error
    if (
        len(completed.stdout) > MAX_COMMAND_OUTPUT_BYTES
        or len(completed.stderr) > MAX_COMMAND_OUTPUT_BYTES
    ):
        raise BuildOracleError(OracleFailureClass.BUILD_FAILED, "build command output is too large")
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _require_success(result: CommandResult, failure: OracleFailureClass, label: str) -> bytes:
    if result.returncode != 0:
        raise BuildOracleError(failure, f"{label} failed")
    return result.stdout


def _run_text(
    runner: CommandRunner,
    argv: Sequence[str],
    cwd: Path,
    environment: Mapping[str, str],
    label: str,
) -> str:
    raw = _require_success(
        runner(argv, cwd, environment), OracleFailureClass.SOURCE_COMMIT_MISMATCH, label
    )
    try:
        return raw.decode("utf-8").strip()
    except UnicodeDecodeError as error:
        raise BuildOracleError(
            OracleFailureClass.SOURCE_COMMIT_MISMATCH, f"{label} is not UTF-8"
        ) from error


def _git(
    runner: CommandRunner,
    checkout: Path,
    *arguments: str,
    failure: OracleFailureClass = OracleFailureClass.SOURCE_COMMIT_MISMATCH,
) -> bytes:
    result = runner(("git", *arguments), checkout, {})
    return _require_success(result, failure, "git verification")


def _source_transport_environment() -> dict[str, str]:
    """Keep the host transport configuration for the one pinned Git fetch.

    This environment is operational only: it is never serialized into either
    manifest.  npm itself still receives the separate isolated environment.
    """

    return dict(os.environ)


_GENERATED_PATH_ALLOWLIST = {
    "acquisition": (),
    "post_npm": ("node_modules/", "dist/"),
    "post_build": ("node_modules/", "dist/"),
    "verify": ("node_modules/", "dist/"),
}


def _verify_index_flags(raw: bytes) -> None:
    """Reject any non-normal Git index entry, including hidden sparse flags."""

    for raw_entry in raw.split(b"\0"):
        if not raw_entry:
            continue
        try:
            entry = raw_entry.decode("utf-8")
        except UnicodeDecodeError as error:
            raise BuildOracleError(
                OracleFailureClass.SOURCE_DIRTY, "index flags are not UTF-8"
            ) from error
        if len(entry) < 3 or entry[1] != " " or entry[0] != "H" or not entry[2:]:
            raise BuildOracleError(OracleFailureClass.SOURCE_DIRTY, "index flags differ")


def _verify_generated_checkout_paths(raw: bytes, *, phase: str) -> None:
    """Permit only explicit build products for the current checkout phase."""

    try:
        allowed = _GENERATED_PATH_ALLOWLIST[phase]
    except KeyError as error:
        raise ValueError(f"unsupported checkout phase {phase}") from error
    for raw_entry in raw.split(b"\0"):
        if not raw_entry:
            continue
        try:
            entry = raw_entry.decode("utf-8")
        except UnicodeDecodeError as error:
            raise BuildOracleError(
                OracleFailureClass.SOURCE_DIRTY, "generated checkout path is not UTF-8"
            ) from error
        if len(entry) < 4 or entry[:2] not in {"??", "!!"} or entry[2] != " ":
            raise BuildOracleError(
                OracleFailureClass.SOURCE_DIRTY, "generated checkout path differs"
            )
        path = entry[3:]
        if not path or not any(
            path == root.rstrip("/") or path.startswith(root) for root in allowed
        ):
            raise BuildOracleError(
                OracleFailureClass.SOURCE_DIRTY, "generated checkout path differs"
            )


def _verify_and_remove_generated_config(
    checkout_directory: Path,
    commit: str,
    *,
    runner: CommandRunner = _run_subprocess,
) -> None:
    """Accept only Showdown's exact generated config copy, then remove it."""

    checkout = checkout_directory.resolve()
    generated = checkout / "config" / "config.js"
    if not generated.exists():
        return
    if generated.is_symlink() or not generated.is_file():
        raise BuildOracleError(OracleFailureClass.SOURCE_DIRTY, "generated config differs")
    expected = _git(runner, checkout, "rev-parse", f"{commit}:config/config-example.js")
    actual = _git(
        runner,
        checkout,
        "hash-object",
        "--path=config/config-example.js",
        "config/config.js",
    )
    if actual.strip() != expected.strip():
        raise BuildOracleError(OracleFailureClass.SOURCE_DIRTY, "generated config differs")
    try:
        generated.unlink()
    except OSError as error:
        raise BuildOracleError(
            OracleFailureClass.SOURCE_DIRTY, "generated config could not be removed"
        ) from error
    if generated.exists():
        raise BuildOracleError(
            OracleFailureClass.SOURCE_DIRTY, "generated config could not be removed"
        )


def verify_source_checkout(
    checkout_directory: Path,
    source_manifest: ShowdownSourceManifest,
    *,
    runner: CommandRunner = _run_subprocess,
    phase: str = "acquisition",
    verify_historical_blobs: bool = True,
) -> None:
    """Verify working-tree bytes against historical source manifest records."""

    checkout = checkout_directory.resolve()
    if not checkout.is_dir() or not (checkout / ".git").exists():
        raise BuildOracleError(OracleFailureClass.SOURCE_MISSING, "verified checkout is missing")
    head = _git(runner, checkout, "rev-parse", "HEAD").decode("utf-8").strip()
    tree = _git(runner, checkout, "rev-parse", "HEAD^{tree}").decode("utf-8").strip()
    remote = _git(runner, checkout, "remote", "get-url", "origin").decode("utf-8").strip()
    if (
        head != source_manifest.commit
        or tree != source_manifest.git_tree_oid
        or remote != source_manifest.repository_url
    ):
        raise BuildOracleError(
            OracleFailureClass.SOURCE_COMMIT_MISMATCH, "checkout identity differs"
        )
    _git(runner, checkout, "update-index", "--refresh", failure=OracleFailureClass.SOURCE_DIRTY)
    index_entries = _git(runner, checkout, "ls-files", "-v", "-z")
    _verify_index_flags(index_entries)
    tracked = _git(runner, checkout, "ls-files", "-z").split(b"\0")
    tracked_paths = tuple(value.decode("utf-8") for value in tracked[:-1])
    expected_paths = tuple(path for path, _, _ in source_manifest.source_files)
    if tracked_paths != expected_paths:
        raise BuildOracleError(
            OracleFailureClass.SOURCE_COMMIT_MISMATCH, "tracked source set differs"
        )

    def read_blob(relative: str) -> bytes:
        return _git(runner, checkout, "cat-file", "blob", f"{source_manifest.commit}:{relative}")

    if verify_historical_blobs:
        verify_historical_blob_records(source_manifest.source_files, read_blob)
    for relative, _, _ in source_manifest.source_files:
        candidate = checkout / Path(*relative.split("/"))
        try:
            candidate.resolve().relative_to(checkout)
        except ValueError as error:
            raise BuildOracleError(
                OracleFailureClass.SOURCE_COMMIT_MISMATCH, "tracked source record differs"
            ) from error
        if candidate.is_symlink() or not candidate.is_file():
            raise BuildOracleError(
                OracleFailureClass.SOURCE_COMMIT_MISMATCH, "tracked source record differs"
            )
    for arguments in (
        ("diff", "--no-ext-diff", "--quiet"),
        ("diff", "--cached", "--no-ext-diff", "--quiet"),
    ):
        if runner(("git", *arguments), checkout, {}).returncode != 0:
            raise BuildOracleError(OracleFailureClass.SOURCE_DIRTY, "tracked checkout is dirty")
    status = _git(
        runner,
        checkout,
        "status",
        "--porcelain=v1",
        "--ignored",
        "--untracked-files=all",
        "-z",
    )
    _verify_generated_checkout_paths(status, phase=phase)


def acquire_pinned_source(
    checkout_directory: Path,
    source_manifest: ShowdownSourceManifest,
    *,
    runner: CommandRunner = _run_subprocess,
) -> None:
    """Fetch exactly the approved object into an explicitly empty directory."""

    checkout = checkout_directory.resolve()
    if checkout.exists() and any(checkout.iterdir()):
        raise BuildOracleError(OracleFailureClass.SOURCE_DIRTY, "checkout target must be empty")
    checkout.mkdir(parents=True, exist_ok=True)
    environment = _source_transport_environment()
    for command in (
        ("git", "init", "--quiet"),
        ("git", "config", "core.autocrlf", "false"),
        ("git", "remote", "add", "origin", source_manifest.repository_url),
        ("git", "fetch", "--no-tags", "origin", source_manifest.commit),
        ("git", "checkout", "--detach", "--force", source_manifest.commit),
    ):
        result = runner(command, checkout, environment)
        _require_success(
            result, OracleFailureClass.SOURCE_COMMIT_MISMATCH, "pinned source acquisition"
        )
    verify_source_checkout(checkout, source_manifest, runner=runner, phase="acquisition")


def _isolated_build_environment(
    cache_directory: Path, home_directory: Path, node_executable: Path
) -> dict[str, str]:
    cache_directory.mkdir(parents=True, exist_ok=True)
    home_directory.mkdir(parents=True, exist_ok=True)
    environment: dict[str, str] = {}
    for name in ("PATH", "SystemRoot", "SYSTEMROOT", "COMSPEC", "WINDIR", "PATHEXT", "TEMP", "TMP"):
        value = os.environ.get(name)
        if value:
            environment[name] = value
    inherited_path = environment.get("PATH")
    environment["PATH"] = str(node_executable.parent)
    if inherited_path:
        environment["PATH"] += os.pathsep + inherited_path
    environment.update(
        {
            "HOME": str(home_directory),
            "USERPROFILE": str(home_directory),
            "npm_config_cache": str(cache_directory),
            "npm_config_userconfig": str(home_directory / ".npmrc"),
            "npm_config_audit": "false",
            "npm_config_fund": "false",
            "npm_config_ignore_scripts": "false",
            "npm_config_package_lock": "true",
            "npm_config_update_notifier": "false",
        }
    )
    return environment


def _version(
    executable: Path,
    runner: CommandRunner,
    checkout: Path,
    environment: Mapping[str, str],
    failure: OracleFailureClass,
) -> str:
    result = runner((str(executable), "--version"), checkout, environment)
    raw = _require_success(result, failure, "version probe")
    try:
        version = raw.decode("ascii").strip().removeprefix("v")
    except UnicodeDecodeError as error:
        raise BuildOracleError(failure, "version probe is not ASCII") from error
    if not version or any(part for part in version.split(".") if not part.isdigit()):
        raise BuildOracleError(failure, "version probe is malformed")
    return version


def _platform_identity() -> tuple[str, str]:
    operating_system = {"win32": "windows", "linux": "linux"}.get(sys.platform)
    if operating_system is None:
        raise BuildOracleError(OracleFailureClass.BUILD_FAILED, "unsupported operating system")
    machine = platform.machine().lower()
    architecture = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }.get(machine)
    if architecture is None:
        raise BuildOracleError(OracleFailureClass.BUILD_FAILED, "unsupported architecture")
    return operating_system, architecture


def _build_manifest_id(
    probe_role: str, operating_system: str, architecture: str, node_version: str
) -> str:
    """Produce a restricted schema identifier from public platform identity."""

    return (
        f"showdown-oracle-build-{probe_role}-{operating_system}-"
        f"{architecture.replace('_', '-')}-node-{node_version.replace('.', '-')}"
    )


def extract_ruleset_snapshot(
    node_executable: Path,
    checkout_directory: Path,
    *,
    runner: CommandRunner = _run_subprocess,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Use the built official Dex to emit a strict, path-free Gen 9 OU closure."""

    checkout = checkout_directory.resolve()
    if not (checkout / "dist" / "sim" / "dex.js").is_file():
        raise BuildOracleError(OracleFailureClass.BUILD_OUTPUT_MISSING, "built Dex is missing")
    ruleset_extractor_bytes()
    try:
        with resources.as_file(_ruleset_extractor_resource()) as extractor_path:
            result = runner(
                (str(node_executable), str(extractor_path)), checkout, environment or {}
            )
    except (FileNotFoundError, ModuleNotFoundError) as error:
        raise BuildOracleError(
            OracleFailureClass.BUILD_FAILED, "ruleset extractor is missing"
        ) from error
    payload = _require_success(result, OracleFailureClass.BUILD_FAILED, "ruleset extraction")
    return _strict_json(payload, label="ruleset extraction")


def _verify_manifest_platform(operating_system: str, architecture: str) -> None:
    if _platform_identity() != (operating_system, architecture):
        raise BuildOracleError(OracleFailureClass.BUILD_FAILED, "build platform differs")


def create_build_manifest(
    *,
    source_manifest: ShowdownSourceManifest,
    checkout_directory: Path,
    node_executable: Path,
    npm_executable: Path,
    probe_role: str,
    cache_directory: Path,
    home_directory: Path,
    runner: CommandRunner = _run_subprocess,
) -> ShowdownBuildManifest:
    """Run the one explicit clean install and build, then seal a v1 manifest."""

    checkout = checkout_directory.resolve()
    verify_source_checkout(checkout, source_manifest, runner=runner, phase="acquisition")
    environment = _isolated_build_environment(cache_directory, home_directory, node_executable)
    node_version = _version(
        node_executable, runner, checkout, environment, OracleFailureClass.NODE_VERSION_NOT_APPROVED
    )
    npm_version = _version(
        npm_executable, runner, checkout, environment, OracleFailureClass.NPM_VERSION_MISMATCH
    )
    allowed = {
        ("candidate", "22.23.2", "10.9.8"),
        ("comparison", "18.20.8", "10.8.2"),
        ("comparison", "20.20.2", "10.8.2"),
    }
    if (probe_role, node_version, npm_version) not in allowed:
        raise BuildOracleError(
            OracleFailureClass.NODE_VERSION_NOT_APPROVED, "Node/npm pair is not approved"
        )
    clear_verified_dist(checkout, checkout / "dist")
    ci_result = runner(
        (str(npm_executable), "ci", "--no-audit", "--no-fund"), checkout, environment
    )
    _require_success(ci_result, OracleFailureClass.BUILD_FAILED, "npm ci")
    _verify_and_remove_generated_config(checkout, source_manifest.commit, runner=runner)
    verify_source_checkout(
        checkout,
        source_manifest,
        runner=runner,
        phase="post_npm",
        verify_historical_blobs=False,
    )
    package_lock = _strict_json((checkout / "package-lock.json").read_bytes(), label="package lock")
    tree = derive_dependency_tree(package_lock)
    _verify_installed_dependency_tree(checkout, tree)
    clear_verified_dist(checkout, checkout / "dist")
    build_result = runner((str(npm_executable), "run", "build"), checkout, environment)
    _require_success(build_result, OracleFailureClass.BUILD_FAILED, "npm build")
    _verify_and_remove_generated_config(checkout, source_manifest.commit, runner=runner)
    verify_source_checkout(
        checkout,
        source_manifest,
        runner=runner,
        phase="post_build",
        verify_historical_blobs=False,
    )
    dependency_files = collect_dependency_file_records(checkout / "node_modules")
    dist_files = collect_dist_records(checkout / "dist")
    snapshot = extract_ruleset_snapshot(
        node_executable, checkout, runner=runner, environment=environment
    )
    operating_system, architecture = _platform_identity()
    document: dict[str, object] = {
        "schema_version": 1,
        "manifest_id": _build_manifest_id(probe_role, operating_system, architecture, node_version),
        "source_manifest_digest": source_manifest.digest,
        "commit": source_manifest.commit,
        "node_version": node_version,
        "npm_version": npm_version,
        "probe_role": probe_role,
        "os": operating_system,
        "architecture": architecture,
        "npm_ci_argv": list(NPM_CI_ARGV),
        "npm_build_argv": list(NPM_BUILD_ARGV),
        "simulator_argv": list(SIMULATOR_ARGV),
        "npm_config": dict(NPM_CONFIG),
        "dependency_tree_digest": manifest_digest(tree),
        "dependency_files": dependency_files,
        "dependency_files_digest": manifest_digest(dependency_files),
        "dist_files": dist_files,
        "dist_tree_digest": manifest_digest(dist_files),
        "format_id": "gen9ou",
        "ruleset_snapshot": snapshot,
        "ruleset_snapshot_digest": manifest_digest(snapshot),
        "format_identity_digest": manifest_digest(snapshot["format"]),
        "adapter_version": "showdown-oracle-v1",
        "canonicalization_profile": "rfc8785-jcs-v1",
        "schema_id": "urn:battlebelief:schema:manifest:showdown-oracle-build:v1",
    }
    return ShowdownBuildManifest.from_dict(document)


def verify_build_manifest(
    *,
    source_manifest: ShowdownSourceManifest,
    build_manifest: ShowdownBuildManifest,
    checkout_directory: Path,
    node_executable: Path,
    npm_executable: Path,
    runner: CommandRunner = _run_subprocess,
) -> None:
    """Revalidate a finished build; this function never invokes npm or build."""

    checkout = checkout_directory.resolve()
    if (
        build_manifest.source_manifest_digest != source_manifest.digest
        or build_manifest.commit != source_manifest.commit
    ):
        raise BuildOracleError(
            OracleFailureClass.SOURCE_COMMIT_MISMATCH, "build does not bind source manifest"
        )
    verify_source_checkout(checkout, source_manifest, runner=runner, phase="verify")
    with tempfile.TemporaryDirectory(prefix="battlebelief-showdown-verify-") as temporary:
        temporary_root = Path(temporary)
        environment = _isolated_build_environment(
            temporary_root / "npm-cache", temporary_root / "npm-home", node_executable
        )
        if (
            _version(
                node_executable,
                runner,
                checkout,
                environment,
                OracleFailureClass.NODE_VERSION_NOT_APPROVED,
            )
            != build_manifest.node_version
        ):
            raise BuildOracleError(
                OracleFailureClass.NODE_VERSION_NOT_APPROVED, "Node version differs"
            )
        if (
            _version(
                npm_executable,
                runner,
                checkout,
                environment,
                OracleFailureClass.NPM_VERSION_MISMATCH,
            )
            != build_manifest.npm_version
        ):
            raise BuildOracleError(OracleFailureClass.NPM_VERSION_MISMATCH, "npm version differs")
        _verify_manifest_platform(build_manifest.os, build_manifest.architecture)
        package_lock = _strict_json(
            (checkout / "package-lock.json").read_bytes(), label="package lock"
        )
        tree = derive_dependency_tree(package_lock)
        if manifest_digest(tree) != build_manifest.dependency_tree_digest:
            raise BuildOracleError(OracleFailureClass.LOCKFILE_MISMATCH, "dependency tree differs")
        _verify_installed_dependency_tree(checkout, tree)
        verify_dependency_file_records(
            checkout / "node_modules",
            build_manifest.to_dict()["dependency_files"],  # type: ignore[arg-type]
        )
        verify_dist_records(checkout / "dist", build_manifest.to_dict()["dist_files"])  # type: ignore[arg-type]
        snapshot = extract_ruleset_snapshot(
            node_executable, checkout, runner=runner, environment=environment
        )
        if (
            manifest_digest(snapshot) != build_manifest.ruleset_snapshot_digest
            or snapshot != build_manifest.to_dict()["ruleset_snapshot"]
        ):
            raise BuildOracleError(
                OracleFailureClass.BUILD_OUTPUT_MISSING, "ruleset closure differs"
            )


__all__ = [
    "RULESET_EXTRACTOR_DIGEST",
    "BuildOracleError",
    "CommandResult",
    "CommandRunner",
    "acquire_pinned_source",
    "clear_verified_dist",
    "collect_dependency_file_records",
    "collect_dist_records",
    "create_build_manifest",
    "dependency_tree_digest",
    "derive_dependency_tree",
    "extract_ruleset_snapshot",
    "ruleset_extractor_bytes",
    "verify_build_manifest",
    "verify_dependency_file_records",
    "verify_dist_records",
    "verify_historical_blob_records",
    "verify_source_checkout",
]
