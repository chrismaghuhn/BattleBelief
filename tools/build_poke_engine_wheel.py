"""Acquire, verify, and build the pinned poke-engine native wheel.

This tool is the only Task-25 path allowed to invoke Git, Cargo, Rust, or
Maturin. Runtime code verifies installed artifacts but never builds them.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import threading
import tomllib
import zipfile
from collections.abc import Mapping, Sequence
from contextlib import suppress
from datetime import date
from email.parser import Parser
from io import BufferedReader
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from battlebelief_core.canonicalization import canonicalize, manifest_digest  # noqa: E402

UPSTREAM_REPOSITORY = "https://github.com/pmariglia/poke-engine"
UPSTREAM_COMMIT = "bcf13823abc162a608e187b26bbf683f759f385e"
UPSTREAM_TAG = "v0.0.48"
UPSTREAM_TREE = "74d10964d7470b2b9d92ba734550825388178d2d"
RUST_TOOLCHAIN = "1.83.0"
MATURIN_VERSION = "1.7.1"
SOURCE_DATE_EPOCH = "1784471591"
CONTROLLED_CARGO_HOME = "../battlebelief-engine-cargo-home"
FEATURES = ("poke-engine/gen9", "poke-engine/terastallization")
TARGETS = frozenset(("x86_64-unknown-linux-gnu", "x86_64-pc-windows-msvc"))
MAX_COMMAND_OUTPUT_BYTES = 16 * 1024 * 1024
COMMAND_TIMEOUT_SECONDS = 60 * 60
_COMMAND_READ_SIZE = 64 * 1024


class BuildPokeEngineError(RuntimeError):
    """A stable, path-free controlled-build failure."""


def _fail(message: str) -> NoReturn:
    raise BuildPokeEngineError(message)


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _run(
    arguments: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
) -> bytes:
    try:
        process = subprocess.Popen(
            tuple(arguments),
            cwd=cwd,
            env=None if environment is None else dict(environment),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError:
        _fail("required build command is unavailable")
    assert process.stdout is not None
    assert process.stderr is not None
    stdout = bytearray()
    stderr = bytearray()
    overflow = threading.Event()
    read_failure = threading.Event()

    def drain(stream: BufferedReader, output: bytearray) -> None:
        try:
            while chunk := stream.read(_COMMAND_READ_SIZE):
                remaining = MAX_COMMAND_OUTPUT_BYTES - len(output)
                if len(chunk) > remaining:
                    output.extend(chunk[: max(remaining, 0)])
                    overflow.set()
                    with suppress(OSError):
                        process.kill()
                    return
                output.extend(chunk)
        except (OSError, ValueError):
            read_failure.set()
            with suppress(OSError):
                process.kill()
            return

    readers = (
        threading.Thread(target=drain, args=(process.stdout, stdout), daemon=True),
        threading.Thread(target=drain, args=(process.stderr, stderr), daemon=True),
    )
    for reader in readers:
        reader.start()
    timed_out = False
    try:
        return_code = process.wait(timeout=COMMAND_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        return_code = process.wait()
    finally:
        if timed_out or overflow.is_set():
            process.stdout.close()
            process.stderr.close()
        for reader in readers:
            reader.join(timeout=5)
    if timed_out:
        _fail("controlled build command exceeded its time bound")
    if overflow.is_set():
        _fail("build command output exceeds the safety bound")
    if read_failure.is_set():
        _fail("controlled build command output is unreadable")
    if any(reader.is_alive() for reader in readers):
        _fail("controlled build command output did not close")
    if return_code != 0:
        _fail("controlled build command failed")
    return bytes(stdout)


def _controlled_build_environment(
    *, cargo_executable: Path, rustc_executable: Path
) -> dict[str, str]:
    """Construct the explicit child environment for the native build."""

    environment = {
        "CARGO_HOME": CONTROLLED_CARGO_HOME,
        "CARGO_INCREMENTAL": "false",
        "CARGO_NET_OFFLINE": "true",
        "CARGO_PROFILE_RELEASE_DEBUG": "0",
        "PYTHONUTF8": "1",
        "SOURCE_DATE_EPOCH": SOURCE_DATE_EPOCH,
    }
    for name in (
        "COMSPEC",
        "PATHEXT",
        "ProgramData",
        "ProgramFiles",
        "ProgramFiles(x86)",
        "ProgramW6432",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
    ):
        value = os.environ.get(name)
        if value:
            environment[name] = value
    tool_directories = tuple(
        dict.fromkeys((str(cargo_executable.parent), str(rustc_executable.parent)))
    )
    ambient_path = os.environ.get("PATH")
    environment["PATH"] = os.pathsep.join(
        (*tool_directories, *((ambient_path,) if ambient_path else ()))
    )
    return environment


def _success_message(command: str) -> str:
    messages = {
        "acquire": "PASS: pinned poke-engine source acquired",
        "source": "PASS: pinned poke-engine source manifest created",
        "verify-source": "PASS: pinned poke-engine source provenance verified",
        "build": "PASS: controlled poke-engine wheel built and bound",
        "source-v2": "PASS: downstream poke-engine source manifest created",
        "verify-source-v2": "PASS: downstream poke-engine source provenance verified",
        "build-v2": "PASS: controlled downstream poke-engine wheel built and bound",
        "source-v3": "PASS: ordered downstream poke-engine source manifest created",
        "verify-source-v3": "PASS: ordered downstream poke-engine source provenance verified",
        "build-v3": "PASS: controlled ordered downstream poke-engine wheel built and bound",
    }
    try:
        return messages[command]
    except KeyError:
        _fail("build subcommand differs")


def _git(checkout: Path, *arguments: str) -> bytes:
    return _run(("git", *arguments), cwd=checkout)


def _decode_line(data: bytes, *, label: str) -> str:
    try:
        value = data.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError:
        _fail(f"{label} is not UTF-8")
    if not value or "\x00" in value or "\r" in value or "\n" in value:
        _fail(f"{label} is malformed")
    return value


def _git_value(checkout: Path, *arguments: str, label: str) -> str:
    return _decode_line(_git(checkout, *arguments), label=label)


def _blob_bytes(checkout: Path, commit: str, path: str) -> bytes:
    return _git(checkout, "show", f"{commit}:{path}")


def collect_source_records(checkout: Path, commit: str) -> list[dict[str, object]]:
    """Collect a canonical full-tree closure from committed Git blob bytes."""

    raw = _git(checkout, "ls-tree", "-r", "-z", "--long", commit)
    records: list[dict[str, object]] = []
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        try:
            metadata, raw_path = entry.split(b"\t", 1)
            mode, object_type, _oid, raw_size = metadata.split(maxsplit=3)
            path = raw_path.decode("utf-8", errors="strict")
            size = int(raw_size)
        except (UnicodeDecodeError, ValueError):
            _fail("Git tree entry is malformed")
        if object_type != b"blob" or mode not in (b"100644", b"100755", b"120000"):
            _fail("Git tree contains an unsupported entry")
        if (
            not path
            or "\\" in path
            or path.startswith("/")
            or any(part in ("", ".", "..") for part in path.split("/"))
        ):
            _fail("Git tree path is unsafe")
        content = _blob_bytes(checkout, commit, path)
        if len(content) != size:
            _fail("Git blob size differs")
        records.append(
            {
                "path": path,
                "git_mode": mode.decode("ascii"),
                "size": size,
                "sha256": _sha256(content),
            }
        )
    records.sort(key=lambda record: str(record["path"]))
    if not records:
        _fail("Git tree is empty")
    return records


def _collect_materialized_source_records(checkout: Path) -> list[dict[str, object]]:
    """Collect the complete tracked source closure from the materialized tree."""

    raw = _git(checkout, "ls-files", "--stage", "-z")
    records: list[dict[str, object]] = []
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        try:
            metadata, raw_path = entry.split(b"\t", 1)
            mode, _object_id, _stage = metadata.split(maxsplit=2)
            path = raw_path.decode("utf-8", errors="strict")
            content = (checkout / Path(path)).read_bytes()
        except (OSError, UnicodeDecodeError, ValueError):
            _fail("post-patch source closure is unreadable")
        if (
            Path(path).is_absolute()
            or "\\" in path
            or any(part == ".." for part in Path(path).parts)
        ):
            _fail("post-patch source path differs")
        records.append(
            {
                "path": path,
                "git_mode": mode.decode("ascii", errors="strict"),
                "size": len(content),
                "sha256": _sha256(content),
            }
        )
    if not records:
        _fail("post-patch source closure is empty")
    return sorted(records, key=lambda record: str(record["path"]))


def _patch_paths(patch_bytes: bytes) -> list[str]:
    try:
        lines = patch_bytes.decode("utf-8", errors="strict").splitlines()
    except UnicodeDecodeError:
        _fail("downstream patch is not UTF-8")
    paths: list[str] = []
    for line in lines:
        if not line.startswith("+++ b/"):
            continue
        path = line[6:]
        if path == "/dev/null" or Path(path).is_absolute() or "\\" in path:
            _fail("downstream patch path differs")
        if any(part in ("", ".", "..") for part in PurePosixPath(path).parts):
            _fail("downstream patch path differs")
        paths.append(path)
    if not paths or len(paths) != len(set(paths)):
        _fail("downstream patch path differs")
    return sorted(paths)


def _run_patch_command(checkout: Path, arguments: Sequence[str]) -> None:
    try:
        process = subprocess.run(
            ("git", *arguments),
            cwd=checkout,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        _fail("downstream patch application differs")
    diagnostics = f"{process.stdout}\n{process.stderr}".lower()
    if process.returncode != 0 or "offset" in diagnostics or "fuzz" in diagnostics:
        _fail("downstream patch application differs")


def _normalize_materialized_base(checkout: Path, commit: str = UPSTREAM_COMMIT) -> None:
    """Make the controlled checkout byte-oriented across Windows and Linux."""

    _run(("git", "config", "core.autocrlf", "false"), cwd=checkout)
    _run(("git", "config", "core.eol", "lf"), cwd=checkout)
    entries = [entry for entry in _git(checkout, "ls-files", "--stage", "-z").split(b"\0") if entry]
    source_blobs: list[tuple[str, bytes]] = []
    for entry in entries:
        try:
            metadata, raw_path = entry.split(b"\t", 1)
            mode, _object_id, _stage = metadata.split(maxsplit=2)
            path = raw_path.decode("utf-8", errors="strict")
        except (UnicodeDecodeError, ValueError):
            _fail("source line-ending policy differs")
        if mode not in (b"100644", b"100755") or (
            not path
            or "\\" in path
            or Path(path).is_absolute()
            or any(part in ("", ".", "..") for part in PurePosixPath(path).parts)
        ):
            _fail("source line-ending policy differs")
        destination = checkout / Path(path)
        try:
            if destination.is_symlink():
                _fail("source line-ending policy differs")
            blob = _git(checkout, "show", f"{commit}:{path}")
            current = destination.read_bytes()
        except OSError:
            _fail("source line-ending policy differs")
        if current != blob and not (b"\r" not in blob and current.replace(b"\r\n", b"\n") == blob):
            _fail("base source tree is dirty")
        source_blobs.append((path, blob))
    status = _git(checkout, "status", "--porcelain=v1", "--untracked-files=all")
    if any(line and line[:1] != b" " for line in status.splitlines()):
        _fail("base source tree is dirty")
    _run(("git", "reset", "--hard", "--quiet", commit), cwd=checkout)
    for path, blob in source_blobs:
        destination = checkout / Path(path)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(blob)
        except OSError:
            _fail("source line-ending policy differs")


def apply_downstream_patch(
    checkout: Path,
    patch_path: Path,
    *,
    base_commit: str,
    base_tree: str,
    patch_sha256: str,
    expected_source_files: Sequence[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    """Apply one exact downstream patch and verify the resulting source closure."""

    if _git_value(checkout, "rev-parse", "HEAD", label="base source commit") != base_commit:
        _fail("base source commit differs")
    if _git_value(checkout, "rev-parse", "HEAD^{tree}", label="base source tree") != base_tree:
        _fail("base source tree differs")
    if _git_value(checkout, "config", "--get", "core.autocrlf", label="source line endings") != (
        "false"
    ):
        _fail("source line-ending policy differs")
    if _git(checkout, "status", "--porcelain=v1", "--untracked-files=all"):
        _fail("base source tree is dirty")
    try:
        patch_bytes = patch_path.read_bytes()
    except OSError:
        _fail("downstream patch is unreadable")
    if _sha256(patch_bytes) != patch_sha256:
        _fail("downstream patch digest differs")
    patch_paths = _patch_paths(patch_bytes)
    patch_argument = str(patch_path.resolve(strict=True))
    _run_patch_command(
        checkout,
        (
            "apply",
            "--check",
            "--unidiff-zero",
            "--whitespace=error",
            "--verbose",
            "--no-recount",
            patch_argument,
        ),
    )
    _run_patch_command(
        checkout,
        (
            "apply",
            "--unidiff-zero",
            "--whitespace=error",
            "--verbose",
            "--no-recount",
            patch_argument,
        ),
    )
    if _git(checkout, "diff", "--check"):
        _fail("downstream patch application differs")
    changed_paths = (
        _git(checkout, "diff", "--name-only", "--no-renames")
        .decode("utf-8", errors="strict")
        .splitlines()
    )
    if sorted(changed_paths) != patch_paths:
        _fail("downstream patch application differs")
    actual_records = _collect_materialized_source_records(checkout)
    if expected_source_files is not None and actual_records != sorted(
        expected_source_files, key=lambda record: str(record["path"])
    ):
        _fail("post-patch source closure differs")
    return actual_records


def apply_downstream_patch_chain(
    checkout: Path,
    *,
    patches: Sequence[tuple[int, Path, str]],
    base_commit: str,
    base_tree: str,
    expected_source_files: Sequence[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    """Apply an explicitly ordered chain of exact downstream patches once."""

    if tuple(ordinal for ordinal, _path, _digest in patches) != tuple(range(1, len(patches) + 1)):
        _fail("patch chain order differs")
    if _git_value(checkout, "rev-parse", "HEAD", label="base source commit") != base_commit:
        _fail("base source commit differs")
    if _git_value(checkout, "rev-parse", "HEAD^{tree}", label="base source tree") != base_tree:
        _fail("base source tree differs")
    if _git_value(checkout, "config", "--get", "core.autocrlf", label="source line endings") != (
        "false"
    ):
        _fail("source line-ending policy differs")
    if _git(checkout, "status", "--porcelain=v1", "--untracked-files=all"):
        _fail("base source tree is dirty")

    expected_paths: list[str] = []
    for _ordinal, patch_path, patch_sha256 in patches:
        try:
            patch_bytes = patch_path.read_bytes()
        except OSError:
            _fail("downstream patch is unreadable")
        if _sha256(patch_bytes) != patch_sha256:
            _fail("downstream patch digest differs")
        expected_paths.extend(_patch_paths(patch_bytes))
        patch_argument = str(patch_path.resolve(strict=True))
        _run_patch_command(
            checkout,
            (
                "apply",
                "--check",
                "--unidiff-zero",
                "--whitespace=error",
                "--verbose",
                "--no-recount",
                patch_argument,
            ),
        )
        _run_patch_command(
            checkout,
            (
                "apply",
                "--unidiff-zero",
                "--whitespace=error",
                "--verbose",
                "--no-recount",
                patch_argument,
            ),
        )
        if _git(checkout, "diff", "--check"):
            _fail("downstream patch application differs")

    changed_paths = (
        _git(checkout, "diff", "--name-only", "--no-renames")
        .decode("utf-8", errors="strict")
        .splitlines()
    )
    if sorted(changed_paths) != sorted(set(expected_paths)):
        _fail("downstream patch application differs")
    actual_records = _collect_materialized_source_records(checkout)
    if expected_source_files is not None and actual_records != sorted(
        expected_source_files, key=lambda record: str(record["path"])
    ):
        _fail("post-patch source closure differs")
    return actual_records


def acquire_pinned_source(checkout: Path) -> None:
    """Acquire only the accepted commit and annotated tag into a new checkout."""

    if checkout.exists():
        _fail("checkout already exists")
    checkout.parent.mkdir(parents=True, exist_ok=True)
    _run(("git", "init", "--quiet", str(checkout)), cwd=checkout.parent)
    _git(checkout, "remote", "add", "origin", UPSTREAM_REPOSITORY)
    _git(checkout, "fetch", "--no-tags", "--depth=1", "origin", UPSTREAM_COMMIT)
    _git(
        checkout,
        "fetch",
        "--no-tags",
        "--depth=1",
        "origin",
        f"refs/tags/{UPSTREAM_TAG}:refs/tags/{UPSTREAM_TAG}",
    )
    _git(checkout, "checkout", "--detach", UPSTREAM_COMMIT)
    if _git_value(checkout, "remote", "get-url", "origin", label="source remote") != (
        UPSTREAM_REPOSITORY
    ):
        _fail("source remote differs")


def _record(records: Sequence[Mapping[str, object]], path: str) -> Mapping[str, object]:
    matches = [record for record in records if record.get("path") == path]
    if len(matches) != 1:
        _fail(f"{path} source record differs")
    return matches[0]


def _workspace_members(checkout: Path, commit: str) -> list[str]:
    try:
        document = tomllib.loads(_blob_bytes(checkout, commit, "Cargo.toml").decode("utf-8"))
        members = document["workspace"]["members"]
    except (UnicodeDecodeError, KeyError, tomllib.TOMLDecodeError):
        _fail("Cargo workspace metadata is invalid")
    if (
        not isinstance(members, list)
        or not members
        or not all(isinstance(member, str) and member for member in members)
    ):
        _fail("Cargo workspace members are invalid")
    return sorted(members)


def create_source_manifest(
    checkout: Path,
    *,
    retrieved_on: str,
    repository_url: str = UPSTREAM_REPOSITORY,
    observed_tag: str = UPSTREAM_TAG,
) -> dict[str, Any]:
    """Create a source manifest from a clean, detached or branch checkout."""

    try:
        date.fromisoformat(retrieved_on)
    except ValueError:
        _fail("retrieval date is invalid")
    commit = _git_value(checkout, "rev-parse", "HEAD", label="source commit")
    tree = _git_value(checkout, "rev-parse", f"{commit}^{{tree}}", label="source tree")
    peeled = _git_value(
        checkout,
        "rev-parse",
        f"refs/tags/{observed_tag}^{{}}",
        label="peeled source tag",
    )
    if _git(checkout, "status", "--porcelain=v1", "--untracked-files=all"):
        _fail("source tree is dirty")
    records = collect_source_records(checkout, commit)
    license_record = _record(records, "LICENSE")
    cargo_lock_record = _record(records, "Cargo.lock")
    return {
        "schema_version": 1,
        "schema_id": "urn:battlebelief:schema:manifest:engine-source:v1",
        "manifest_id": f"poke-engine-source-{commit[:8]}",
        "repository_url": repository_url,
        "commit": commit,
        "observed_tag": observed_tag,
        "tag_peeled_commit": peeled,
        "git_tree_oid": tree,
        "retrieved_on": retrieved_on,
        "license": {
            "spdx_id": "MIT",
            "path": "LICENSE",
            "size": license_record["size"],
            "sha256": license_record["sha256"],
        },
        "source_scope": "full_git_tree",
        "source_files": records,
        "source_tree_digest": manifest_digest(records),
        "source_file_count": len(records),
        "cargo_lock": {
            "path": "Cargo.lock",
            "size": cargo_lock_record["size"],
            "sha256": cargo_lock_record["sha256"],
        },
        "workspace_members": _workspace_members(checkout, commit),
        "submodules": {"present": False, "entries": []},
        "clean_tree": True,
        "canonicalization_profile": "rfc8785-jcs-v1",
    }


def verify_source_checkout(checkout: Path, manifest: Mapping[str, Any]) -> None:
    """Fail closed unless a checkout exactly matches its full-tree manifest."""

    commit = manifest.get("commit")
    tag = manifest.get("observed_tag")
    if not isinstance(commit, str) or not isinstance(tag, str):
        _fail("source manifest identity is invalid")
    if _git_value(checkout, "rev-parse", "HEAD", label="source commit") != commit:
        _fail("source commit differs")
    if _git_value(checkout, "rev-parse", f"{commit}^{{tree}}", label="source tree") != (
        manifest.get("git_tree_oid")
    ):
        _fail("source tree differs")
    if _git_value(
        checkout, "rev-parse", f"refs/tags/{tag}^{{}}", label="peeled source tag"
    ) != manifest.get("tag_peeled_commit"):
        _fail("source tag differs")
    if _git(checkout, "status", "--porcelain=v1", "--untracked-files=all"):
        _fail("source tree is dirty")
    actual_records = collect_source_records(checkout, commit)
    if actual_records != manifest.get("source_files"):
        _fail("source file closure differs")
    if len(actual_records) != manifest.get("source_file_count"):
        _fail("source file count differs")
    if manifest_digest(actual_records) != manifest.get("source_tree_digest"):
        _fail("source tree digest differs")
    cargo_lock = _record(actual_records, "Cargo.lock")
    if manifest.get("cargo_lock") != {
        "path": "Cargo.lock",
        "size": cargo_lock["size"],
        "sha256": cargo_lock["sha256"],
    }:
        _fail("Cargo.lock digest differs")
    license_record = _record(actual_records, "LICENSE")
    if manifest.get("license") != {
        "spdx_id": "MIT",
        "path": "LICENSE",
        "size": license_record["size"],
        "sha256": license_record["sha256"],
    }:
        _fail("license digest differs")
    if manifest.get("workspace_members") != _workspace_members(checkout, commit):
        _fail("Cargo workspace members differ")
    if manifest.get("submodules") != {"present": False, "entries": []}:
        _fail("source submodule state differs")


def validate_pinned_source_manifest(manifest: Mapping[str, Any]) -> None:
    """Require the accepted upstream identity before any build starts."""

    expected = {
        "repository_url": UPSTREAM_REPOSITORY,
        "commit": UPSTREAM_COMMIT,
        "observed_tag": UPSTREAM_TAG,
        "tag_peeled_commit": UPSTREAM_COMMIT,
        "git_tree_oid": UPSTREAM_TREE,
        "source_scope": "full_git_tree",
        "clean_tree": True,
        "canonicalization_profile": "rfc8785-jcs-v1",
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        _fail("source manifest does not match the accepted upstream pin")


def validate_build_configuration(
    *,
    rust_toolchain: str,
    maturin_version: str,
    target_triple: str,
    features: Sequence[str],
    locked: bool,
    no_default_features: bool,
) -> None:
    """Reject any build configuration outside the six-cell contract."""

    if rust_toolchain != RUST_TOOLCHAIN:
        _fail("Rust toolchain is not pinned")
    if maturin_version != MATURIN_VERSION:
        _fail("Maturin version is not pinned")
    if target_triple not in TARGETS:
        _fail("Rust target is unsupported")
    if tuple(features) != FEATURES:
        _fail("Cargo feature identity differs")
    if not locked:
        _fail("Cargo locked mode is required")
    if not no_default_features:
        _fail("Cargo default features must be disabled")


def build_argv(target_triple: str) -> list[str]:
    """Return the canonical, path-free Maturin argv recorded in a manifest."""

    if target_triple not in TARGETS:
        _fail("Rust target is unsupported")
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
        ",".join(FEATURES),
        "--interpreter",
        "python",
        "--target",
        target_triple,
        "--out",
        "wheelhouse",
    ]
    if target_triple == "x86_64-unknown-linux-gnu":
        arguments.extend(("--compatibility", "linux"))
    return arguments


def _wheel_member_names(archive: zipfile.ZipFile) -> list[str]:
    names: list[str] = []
    for info in archive.infolist():
        path = PurePosixPath(info.filename)
        if (
            info.is_dir()
            or path.is_absolute()
            or not path.parts
            or any(part in ("", ".", "..") for part in path.parts)
            or "\\" in info.filename
        ):
            _fail("wheel contains an unsafe member")
        unix_mode = info.external_attr >> 16
        if unix_mode and unix_mode & 0o170000 == 0o120000:
            _fail("wheel contains a symbolic link")
        names.append(info.filename)
    if len(names) != len(set(names)):
        _fail("wheel contains duplicate members")
    return names


def _single_metadata_value(content: bytes, name: str, *, label: str) -> str:
    try:
        document = Parser().parsestr(content.decode("utf-8", errors="strict"))
    except UnicodeDecodeError:
        _fail(f"{label} is not UTF-8")
    values = document.get_all(name, [])
    if len(values) != 1 or not values[0]:
        _fail(f"{label} field differs")
    return values[0]


def _decode_record_digest(value: str) -> str:
    try:
        algorithm, encoded = value.split("=", 1)
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (ValueError, binascii.Error):
        _fail("wheel RECORD digest is malformed")
    if algorithm != "sha256" or len(decoded) != 32:
        _fail("wheel RECORD digest algorithm differs")
    return "sha256:" + decoded.hex()


def _wheel_record_entries(
    archive: zipfile.ZipFile, names: Sequence[str], record_path: str, record: bytes
) -> list[dict[str, object]]:
    try:
        rows = list(csv.reader(io.StringIO(record.decode("utf-8", errors="strict"))))
    except (UnicodeDecodeError, csv.Error):
        _fail("wheel RECORD is malformed")
    entries: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in rows:
        if len(row) != 3:
            _fail("wheel RECORD row is malformed")
        path, raw_digest, raw_size = row
        if path in seen or path not in names:
            _fail("wheel RECORD closure differs")
        seen.add(path)
        if path == record_path:
            if raw_digest or raw_size:
                _fail("wheel RECORD self-entry differs")
            entries.append({"path": path, "sha256": None, "size": None})
            continue
        if not raw_digest or not raw_size:
            _fail("wheel RECORD entry is unhashed")
        try:
            size = int(raw_size)
        except ValueError:
            _fail("wheel RECORD size is malformed")
        if archive.getinfo(path).file_size != size:
            _fail("wheel RECORD content differs")
        content = archive.read(path)
        digest = _decode_record_digest(raw_digest)
        if size != len(content) or digest != _sha256(content):
            _fail("wheel RECORD content differs")
        entries.append({"path": path, "sha256": digest, "size": size})
    if seen != set(names):
        _fail("wheel RECORD closure differs")
    return sorted(entries, key=lambda entry: str(entry["path"]))


def inspect_wheel(
    wheel_path: Path,
    *,
    python_tag: str,
    abi_tag: str,
    platform_tag: str,
    distribution_version: str = "0.0.48",
) -> dict[str, Any]:
    """Bind a built wheel and its security-relevant metadata."""

    if distribution_version not in SUPPORTED_WHEEL_DISTRIBUTION_VERSIONS:
        _fail("wheel distribution identity differs")
    expected_filename = (
        f"poke_engine-{distribution_version}-{python_tag}-{abi_tag}-{platform_tag}.whl"
    )
    if wheel_path.name != expected_filename or wheel_path.suffix != ".whl":
        _fail("wheel filename differs")
    try:
        wheel_bytes = wheel_path.read_bytes()
        with zipfile.ZipFile(wheel_path) as archive:
            names = _wheel_member_names(archive)
            dist_info_roots = {
                name.split("/", 1)[0]
                for name in names
                if name.split("/", 1)[0].endswith(".dist-info")
            }
            if dist_info_roots != {f"poke_engine-{distribution_version}.dist-info"}:
                _fail("wheel dist-info identity differs")
            root = next(iter(dist_info_roots))
            expected_members = {
                "metadata": f"{root}/METADATA",
                "wheel": f"{root}/WHEEL",
                "record": f"{root}/RECORD",
            }
            if any(member not in names for member in expected_members.values()):
                _fail("wheel metadata closure differs")
            metadata = archive.read(expected_members["metadata"])
            wheel_metadata = archive.read(expected_members["wheel"])
            record = archive.read(expected_members["record"])
            record_entries = _wheel_record_entries(
                archive, names, expected_members["record"], record
            )
    except (OSError, zipfile.BadZipFile, KeyError):
        _fail("wheel is unreadable")
    if (
        _single_metadata_value(metadata, "Name", label="wheel METADATA") != "poke-engine"
        or _single_metadata_value(metadata, "Version", label="wheel METADATA")
        != distribution_version
    ):
        _fail("wheel distribution identity differs")
    tag = f"{python_tag}-{abi_tag}-{platform_tag}"
    if _single_metadata_value(wheel_metadata, "Root-Is-Purelib", label="WHEEL").lower() != (
        "false"
    ):
        _fail("wheel purity metadata differs")
    try:
        parsed_wheel = Parser().parsestr(wheel_metadata.decode("utf-8", errors="strict"))
    except UnicodeDecodeError:
        _fail("WHEEL is not UTF-8")
    tags = sorted(parsed_wheel.get_all("Tag", []))
    if tags != [tag]:
        _fail("wheel compatibility tags differ")
    return {
        "filename": wheel_path.name,
        "size": len(wheel_bytes),
        "sha256": _sha256(wheel_bytes),
        "metadata_sha256": _sha256(metadata),
        "wheel_metadata_sha256": _sha256(wheel_metadata),
        "record_sha256": _sha256(record),
        "record_entries": record_entries,
        "root_is_purelib": False,
        "tags": tags,
    }


def _verify_rust_identity(rustc_vv: str, cargo_version: str, target_triple: str) -> None:
    required_rustc_lines = {
        "rustc 1.83.0 (90b35a623 2024-11-26)",
        "commit-hash: 90b35a6239c3d8bdabc530a6a0816f7ff89a0aaf",
        "commit-date: 2024-11-26",
        f"host: {target_triple}",
        "release: 1.83.0",
    }
    if not required_rustc_lines.issubset(set(rustc_vv.splitlines())):
        _fail("Rust compiler identity differs")
    if cargo_version != "cargo 1.83.0 (5ffbef321 2024-10-29)":
        _fail("Cargo identity differs")


def _python_tags(python_version: str, target_triple: str) -> tuple[str, str, str]:
    match = re.fullmatch(r"3\.(12|13|14)\.[0-9]+", python_version)
    if match is None:
        _fail("Python version is outside the approved matrix")
    python_tag = f"cp3{match.group(1)}"
    if target_triple == "x86_64-unknown-linux-gnu":
        return python_tag, python_tag, "linux_x86_64"
    return python_tag, "none", "win_amd64"


def create_build_manifest(
    *,
    source_manifest: Mapping[str, Any],
    rustc_vv: str,
    cargo_version: str,
    maturin_version: str,
    target_triple: str,
    operating_system: str,
    python_version: str,
    wheel: Mapping[str, Any],
) -> dict[str, Any]:
    """Create one canonical six-cell build record from verified inputs."""

    validate_build_configuration(
        rust_toolchain=RUST_TOOLCHAIN,
        maturin_version=maturin_version,
        target_triple=target_triple,
        features=FEATURES,
        locked=True,
        no_default_features=True,
    )
    _verify_rust_identity(rustc_vv, cargo_version, target_triple)
    expected_os = "ubuntu-24.04" if target_triple == "x86_64-unknown-linux-gnu" else "windows-2025"
    if operating_system != expected_os:
        _fail("build operating system differs")
    python_tag, abi_tag, platform_tag = _python_tags(python_version, target_triple)
    expected_wheel_identity = {
        "filename": f"poke_engine-0.0.48-{python_tag}-{abi_tag}-{platform_tag}.whl",
        "tags": [f"{python_tag}-{abi_tag}-{platform_tag}"],
        "root_is_purelib": False,
    }
    if any(wheel.get(key) != value for key, value in expected_wheel_identity.items()):
        _fail("wheel identity differs from the build cell")
    cell_id = f"{operating_system}-x86_64-{python_tag}"
    return {
        "schema_version": 1,
        "schema_id": "urn:battlebelief:schema:manifest:engine-build:v1",
        "manifest_id": f"poke-engine-build-{cell_id}",
        "cell_id": cell_id,
        "source_schema_id": "urn:battlebelief:schema:manifest:engine-source:v1",
        "source_manifest_digest": manifest_digest(source_manifest),
        "rust_toolchain": f"{RUST_TOOLCHAIN}-{target_triple}",
        "rustc_vv": rustc_vv,
        "cargo_version": cargo_version,
        "rustup_components": ["cargo", "rust-std", "rustc"],
        "rust_targets": [target_triple],
        "maturin_version": maturin_version,
        "build_backend": "maturin",
        "build_argv": build_argv(target_triple),
        "locked": True,
        "no_default_features": True,
        "features": list(FEATURES),
        "target_triple": target_triple,
        "operating_system": operating_system,
        "architecture": "x86_64",
        "python": {
            "implementation": "CPython",
            "version": python_version,
            "python_tag": python_tag,
            "abi_tag": abi_tag,
            "platform_tag": platform_tag,
        },
        "distribution": {"name": "poke-engine", "version": "0.0.48"},
        "wheel": dict(wheel),
        "build_environment": {
            "allowlist": [
                {"name": "CARGO_HOME", "value": CONTROLLED_CARGO_HOME},
                {"name": "CARGO_INCREMENTAL", "value": "false"},
                {"name": "CARGO_NET_OFFLINE", "value": "true"},
                {"name": "CARGO_PROFILE_RELEASE_DEBUG", "value": "0"},
                {"name": "PYTHONUTF8", "value": "1"},
                {"name": "SOURCE_DATE_EPOCH", "value": SOURCE_DATE_EPOCH},
            ]
        },
        "adapter_version": "battlebelief-poke-engine-v1",
        "canonicalization_profile": "rfc8785-jcs-v1",
    }


def _load_json(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                _fail("source manifest has duplicate keys")
            result[key] = value
        return result

    try:
        value = json.loads(path.read_bytes(), object_pairs_hook=reject_duplicates)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _fail("source manifest is unreadable")
    if not isinstance(value, dict):
        _fail("source manifest is not an object")
    return value


def _write_new(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as output:
            output.write(content)
    except FileExistsError:
        _fail("output already exists")


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _executable_text(executable: Path, *arguments: str, cwd: Path) -> str:
    output = _run((str(executable), *arguments), cwd=cwd)
    try:
        return output.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError:
        _fail("build tool identity is not UTF-8")


def _python_version(executable: Path, *, cwd: Path) -> str:
    output = _executable_text(
        executable,
        "-c",
        "import platform; print(platform.python_implementation()); print(platform.python_version())",
        cwd=cwd,
    ).splitlines()
    if len(output) != 2 or output[0] != "CPython":
        _fail("Python implementation differs")
    return output[1]


def build_one_wheel(
    *,
    checkout: Path,
    source_manifest: Mapping[str, Any],
    python_executable: Path,
    rustc_executable: Path,
    cargo_executable: Path,
    maturin_executable: Path,
    target_triple: str,
    operating_system: str,
    wheelhouse: Path,
) -> dict[str, Any]:
    """Build one wheel in a new directory and return its canonical manifest."""

    validate_pinned_source_manifest(source_manifest)
    verify_source_checkout(checkout, source_manifest)
    validate_build_configuration(
        rust_toolchain=RUST_TOOLCHAIN,
        maturin_version=MATURIN_VERSION,
        target_triple=target_triple,
        features=FEATURES,
        locked=True,
        no_default_features=True,
    )
    if wheelhouse.exists() or _is_within(wheelhouse, checkout):
        _fail("wheel output directory is not isolated")
    python_version = _python_version(python_executable, cwd=checkout)
    python_tag, abi_tag, platform_tag = _python_tags(python_version, target_triple)
    rustc_vv = _executable_text(rustc_executable, "--version", "--verbose", cwd=checkout)
    cargo_version = _executable_text(cargo_executable, "--version", cwd=checkout)
    _verify_rust_identity(rustc_vv, cargo_version, target_triple)
    if _executable_text(maturin_executable, "--version", cwd=checkout) != (
        f"maturin {MATURIN_VERSION}"
    ):
        _fail("Maturin executable identity differs")
    wheelhouse.parent.mkdir(parents=True, exist_ok=True)
    wheelhouse.mkdir()
    actual_arguments = build_argv(target_triple)
    actual_arguments[0] = str(maturin_executable)
    actual_arguments[actual_arguments.index("python")] = str(python_executable)
    actual_arguments[actual_arguments.index("wheelhouse")] = str(wheelhouse)
    environment = _controlled_build_environment(
        cargo_executable=cargo_executable,
        rustc_executable=rustc_executable,
    )
    _run(actual_arguments, cwd=checkout, environment=environment)
    if _git(checkout, "status", "--porcelain=v1", "--untracked-files=all"):
        _fail("source tree became dirty during build")
    wheels = sorted(wheelhouse.glob("*.whl"))
    if len(wheels) != 1 or any(path.is_dir() for path in wheelhouse.iterdir()):
        _fail("build output closure differs")
    wheel = inspect_wheel(
        wheels[0],
        python_tag=python_tag,
        abi_tag=abi_tag,
        platform_tag=platform_tag,
    )
    return create_build_manifest(
        source_manifest=source_manifest,
        rustc_vv=rustc_vv,
        cargo_version=cargo_version,
        maturin_version=MATURIN_VERSION,
        target_triple=target_triple,
        operating_system=operating_system,
        python_version=python_version,
        wheel=wheel,
    )


LEGAL_CHOICE_VERSION = "0.0.49"
LEGAL_CHOICE_SOURCE_SCHEMA_ID = "urn:battlebelief:schema:manifest:engine-source:v2"
LEGAL_CHOICE_BUILD_SCHEMA_ID = "urn:battlebelief:schema:manifest:engine-build:v2"
LEGAL_CHOICE_INDEX_SCHEMA_ID = "urn:battlebelief:schema:manifest:engine-artifact-index:v2"
LEGAL_CHOICE_ADAPTER_VERSION = "battlebelief-poke-engine-v2-legal-choices"
LEGAL_CHOICE_RELEASE_TAG = "engine-poke-engine-v0.0.49-bcf13823-v2-legal-choices-r1"
LEGAL_CHOICE_PATCH_RELATIVE_PATH = (
    "artifacts/gen9ou/m2/engine/downstream-patches/poke-engine-legal-choices-v1.patch"
)

RESOLVED_ACTION_ORDER_VERSION = "0.0.50"
RESOLVED_ACTION_ORDER_SOURCE_SCHEMA_ID = "urn:battlebelief:schema:manifest:engine-source:v3"
RESOLVED_ACTION_ORDER_BUILD_SCHEMA_ID = "urn:battlebelief:schema:manifest:engine-build:v3"
RESOLVED_ACTION_ORDER_INDEX_SCHEMA_ID = "urn:battlebelief:schema:manifest:engine-artifact-index:v3"
RESOLVED_ACTION_ORDER_ADAPTER_VERSION = "battlebelief-poke-engine-v3-resolved-action-order"
RESOLVED_ACTION_ORDER_RELEASE_TAG = "engine-poke-engine-v0.0.50-bcf13823-v3-resolved-order-r1"
SUPPORTED_WHEEL_DISTRIBUTION_VERSIONS = frozenset(
    (UPSTREAM_TAG.removeprefix("v"), LEGAL_CHOICE_VERSION, RESOLVED_ACTION_ORDER_VERSION)
)
RESOLVED_ACTION_ORDER_PATCH_CHAIN = (
    (
        "artifacts/gen9ou/m2/engine/downstream-patches/poke-engine-legal-choices-v1.patch",
        "legal-choice-binding",
    ),
    (
        "artifacts/gen9ou/m2/engine/downstream-patches/poke-engine-resolved-action-order-v1.patch",
        "resolved-action-order-binding",
    ),
)


def _materialized_workspace_members(checkout: Path) -> list[str]:
    try:
        document = tomllib.loads((checkout / "Cargo.toml").read_text(encoding="utf-8"))
        members = document["workspace"]["members"]
    except (OSError, UnicodeDecodeError, KeyError, tomllib.TOMLDecodeError):
        _fail("Cargo workspace metadata is invalid")
    if (
        not isinstance(members, list)
        or not members
        or not all(isinstance(member, str) and member for member in members)
    ):
        _fail("Cargo workspace members are invalid")
    return sorted(members)


def create_downstream_source_manifest(
    checkout: Path,
    *,
    base_manifest: Mapping[str, Any],
    patch_path: Path,
    retrieved_on: str,
) -> dict[str, Any]:
    """Create v2 provenance from one verified base and one exact patch."""

    validate_pinned_source_manifest(base_manifest)
    verify_source_checkout(checkout, base_manifest)
    _normalize_materialized_base(checkout)
    try:
        date.fromisoformat(retrieved_on)
        patch_bytes = patch_path.read_bytes()
    except (OSError, ValueError):
        _fail("downstream source inputs are unreadable")
    patch_digest = _sha256(patch_bytes)
    records = apply_downstream_patch(
        checkout,
        patch_path,
        base_commit=UPSTREAM_COMMIT,
        base_tree=UPSTREAM_TREE,
        patch_sha256=patch_digest,
    )
    license_record = _record(records, "LICENSE")
    cargo_lock_record = _record(records, "Cargo.lock")
    return {
        "schema_version": 2,
        "schema_id": LEGAL_CHOICE_SOURCE_SCHEMA_ID,
        "manifest_id": "poke-engine-source-bcf13823-downstream-legal-choices-v2",
        "repository_url": UPSTREAM_REPOSITORY,
        "base_source_manifest_id": base_manifest.get("manifest_id"),
        "base_source_manifest_digest": manifest_digest(base_manifest),
        "base_commit": UPSTREAM_COMMIT,
        "base_tag": UPSTREAM_TAG,
        "base_tag_peeled_commit": UPSTREAM_COMMIT,
        "base_git_tree_oid": UPSTREAM_TREE,
        "base_source_tree_digest": base_manifest.get("source_tree_digest"),
        "base_source_file_count": base_manifest.get("source_file_count"),
        "retrieved_on": retrieved_on,
        "license": {
            "spdx_id": "MIT",
            "path": "LICENSE",
            "size": license_record["size"],
            "sha256": license_record["sha256"],
        },
        "source_scope": "full_git_tree_with_downstream_patch",
        "source_files": records,
        "source_tree_digest": manifest_digest(records),
        "source_file_count": len(records),
        "cargo_lock": {
            "path": "Cargo.lock",
            "size": cargo_lock_record["size"],
            "sha256": cargo_lock_record["sha256"],
        },
        "workspace_members": _materialized_workspace_members(checkout),
        "submodules": {"present": False, "entries": []},
        "base_clean_tree": True,
        "resulting_source_is_committed": False,
        "downstream_patch": {
            "path": LEGAL_CHOICE_PATCH_RELATIVE_PATH,
            "role": "legal-choice-binding",
            "format": "git-diff-binary-full-index-unified-zero-v1",
            "application": "git-apply-exact-v1",
            "size": len(patch_bytes),
            "sha256": patch_digest,
        },
        "canonicalization_profile": "rfc8785-jcs-v1",
    }


def validate_downstream_source_manifest(
    manifest: Mapping[str, Any], base_manifest: Mapping[str, Any], patch_path: Path
) -> None:
    """Require the exact v2 base, patch, and downstream source contract."""

    validate_pinned_source_manifest(base_manifest)
    expected = {
        "schema_version": 2,
        "schema_id": LEGAL_CHOICE_SOURCE_SCHEMA_ID,
        "repository_url": UPSTREAM_REPOSITORY,
        "base_source_manifest_id": base_manifest.get("manifest_id"),
        "base_source_manifest_digest": manifest_digest(base_manifest),
        "base_commit": UPSTREAM_COMMIT,
        "base_tag": UPSTREAM_TAG,
        "base_tag_peeled_commit": UPSTREAM_COMMIT,
        "base_git_tree_oid": UPSTREAM_TREE,
        "base_source_tree_digest": base_manifest.get("source_tree_digest"),
        "base_source_file_count": base_manifest.get("source_file_count"),
        "source_scope": "full_git_tree_with_downstream_patch",
        "base_clean_tree": True,
        "resulting_source_is_committed": False,
        "canonicalization_profile": "rfc8785-jcs-v1",
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        _fail("downstream source manifest identity differs")
    patch = manifest.get("downstream_patch")
    if not isinstance(patch, Mapping):
        _fail("downstream patch provenance differs")
    try:
        patch_bytes = patch_path.read_bytes()
    except OSError:
        _fail("downstream patch is unreadable")
    expected_patch = {
        "path": LEGAL_CHOICE_PATCH_RELATIVE_PATH,
        "role": "legal-choice-binding",
        "format": "git-diff-binary-full-index-unified-zero-v1",
        "application": "git-apply-exact-v1",
        "size": len(patch_bytes),
        "sha256": _sha256(patch_bytes),
    }
    if dict(patch) != expected_patch:
        _fail("downstream patch provenance differs")
    source_files = manifest.get("source_files")
    if not isinstance(source_files, list) or not source_files:
        _fail("post-patch source closure differs")
    if manifest.get("source_file_count") != len(source_files):
        _fail("post-patch source closure differs")
    if manifest_digest(source_files) != manifest.get("source_tree_digest"):
        _fail("post-patch source closure differs")


def verify_downstream_source_checkout(
    checkout: Path,
    *,
    base_manifest: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    patch_path: Path,
) -> None:
    """Verify and apply the downstream patch exactly once to a clean base."""

    validate_downstream_source_manifest(source_manifest, base_manifest, patch_path)
    if _git_value(checkout, "rev-parse", "HEAD", label="base source commit") != UPSTREAM_COMMIT:
        _fail("base source commit differs")
    if _git_value(checkout, "rev-parse", "HEAD^{tree}", label="base source tree") != UPSTREAM_TREE:
        _fail("base source tree differs")
    _normalize_materialized_base(checkout)
    verify_source_checkout(checkout, base_manifest)
    try:
        patch_digest = _sha256(patch_path.read_bytes())
    except OSError:
        _fail("downstream patch is unreadable")
    records = apply_downstream_patch(
        checkout,
        patch_path,
        base_commit=UPSTREAM_COMMIT,
        base_tree=UPSTREAM_TREE,
        patch_sha256=patch_digest,
        expected_source_files=source_manifest["source_files"],
    )
    if manifest_digest(records) != source_manifest.get("source_tree_digest"):
        _fail("post-patch source closure differs")
    if _materialized_workspace_members(checkout) != source_manifest.get("workspace_members"):
        _fail("Cargo workspace members differ")


def _resolved_action_order_patch_entries(patch_paths: Sequence[Path]) -> list[dict[str, object]]:
    if len(patch_paths) != len(RESOLVED_ACTION_ORDER_PATCH_CHAIN):
        _fail("patch chain provenance differs")
    entries: list[dict[str, object]] = []
    for ordinal, (patch_path, (relative_path, role)) in enumerate(
        zip(patch_paths, RESOLVED_ACTION_ORDER_PATCH_CHAIN, strict=True), start=1
    ):
        try:
            if patch_path.resolve(strict=True) != (ROOT / relative_path).resolve(strict=True):
                _fail("patch chain provenance differs")
            patch_bytes = patch_path.read_bytes()
        except OSError:
            _fail("downstream patch is unreadable")
        entries.append(
            {
                "ordinal": ordinal,
                "path": relative_path,
                "role": role,
                "format": "git-diff-binary-full-index-unified-zero-v1",
                "application": "git-apply-exact-v1",
                "size": len(patch_bytes),
                "sha256": _sha256(patch_bytes),
            }
        )
    return entries


def _resolved_action_order_patch_arguments(
    entries: Sequence[Mapping[str, object]], patch_paths: Sequence[Path]
) -> tuple[tuple[int, Path, str], ...]:
    arguments: list[tuple[int, Path, str]] = []
    for entry, patch_path in zip(entries, patch_paths, strict=True):
        ordinal = entry.get("ordinal")
        digest = entry.get("sha256")
        if not isinstance(ordinal, int) or not isinstance(digest, str):
            _fail("patch chain provenance differs")
        arguments.append((ordinal, patch_path, digest))
    return tuple(arguments)


def create_resolved_action_order_source_manifest(
    checkout: Path,
    *,
    base_manifest: Mapping[str, Any],
    patch_paths: Sequence[Path],
    retrieved_on: str,
) -> dict[str, Any]:
    """Create v3 provenance from the base and the explicit two-patch chain."""

    validate_pinned_source_manifest(base_manifest)
    try:
        date.fromisoformat(retrieved_on)
    except ValueError:
        _fail("downstream source inputs are unreadable")
    _normalize_materialized_base(checkout)
    verify_source_checkout(checkout, base_manifest)
    patches = _resolved_action_order_patch_entries(patch_paths)
    records = apply_downstream_patch_chain(
        checkout,
        patches=_resolved_action_order_patch_arguments(patches, patch_paths),
        base_commit=UPSTREAM_COMMIT,
        base_tree=UPSTREAM_TREE,
    )
    license_record = _record(records, "LICENSE")
    cargo_lock_record = _record(records, "Cargo.lock")
    return {
        "schema_version": 3,
        "schema_id": RESOLVED_ACTION_ORDER_SOURCE_SCHEMA_ID,
        "manifest_id": "poke-engine-source-bcf13823-downstream-resolved-order-v3",
        "repository_url": UPSTREAM_REPOSITORY,
        "base_source_manifest_id": base_manifest.get("manifest_id"),
        "base_source_manifest_digest": manifest_digest(base_manifest),
        "base_commit": UPSTREAM_COMMIT,
        "base_tag": UPSTREAM_TAG,
        "base_tag_peeled_commit": UPSTREAM_COMMIT,
        "base_git_tree_oid": UPSTREAM_TREE,
        "base_source_tree_digest": base_manifest.get("source_tree_digest"),
        "base_source_file_count": base_manifest.get("source_file_count"),
        "retrieved_on": retrieved_on,
        "license": {
            "spdx_id": "MIT",
            "path": "LICENSE",
            "size": license_record["size"],
            "sha256": license_record["sha256"],
        },
        "source_scope": "full_git_tree_with_downstream_patch_chain",
        "source_files": records,
        "source_tree_digest": manifest_digest(records),
        "source_file_count": len(records),
        "cargo_lock": {
            "path": "Cargo.lock",
            "size": cargo_lock_record["size"],
            "sha256": cargo_lock_record["sha256"],
        },
        "workspace_members": _materialized_workspace_members(checkout),
        "submodules": {"present": False, "entries": []},
        "base_clean_tree": True,
        "resulting_source_is_committed": False,
        "downstream_patches": patches,
        "canonicalization_profile": "rfc8785-jcs-v1",
    }


def validate_resolved_action_order_source_manifest(
    manifest: Mapping[str, Any],
    base_manifest: Mapping[str, Any],
    patch_paths: Sequence[Path],
) -> None:
    """Require the exact v3 base, ordered chain, and resulting source closure."""

    validate_pinned_source_manifest(base_manifest)
    expected = {
        "schema_version": 3,
        "schema_id": RESOLVED_ACTION_ORDER_SOURCE_SCHEMA_ID,
        "repository_url": UPSTREAM_REPOSITORY,
        "base_source_manifest_id": base_manifest.get("manifest_id"),
        "base_source_manifest_digest": manifest_digest(base_manifest),
        "base_commit": UPSTREAM_COMMIT,
        "base_tag": UPSTREAM_TAG,
        "base_tag_peeled_commit": UPSTREAM_COMMIT,
        "base_git_tree_oid": UPSTREAM_TREE,
        "base_source_tree_digest": base_manifest.get("source_tree_digest"),
        "base_source_file_count": base_manifest.get("source_file_count"),
        "source_scope": "full_git_tree_with_downstream_patch_chain",
        "base_clean_tree": True,
        "resulting_source_is_committed": False,
        "canonicalization_profile": "rfc8785-jcs-v1",
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        _fail("downstream source manifest identity differs")
    patches = manifest.get("downstream_patches")
    if not isinstance(patches, list) or patches != _resolved_action_order_patch_entries(
        patch_paths
    ):
        _fail("patch chain provenance differs")
    source_files = manifest.get("source_files")
    if not isinstance(source_files, list) or not source_files:
        _fail("post-patch source closure differs")
    if manifest.get("source_file_count") != len(source_files):
        _fail("post-patch source closure differs")
    if manifest_digest(source_files) != manifest.get("source_tree_digest"):
        _fail("post-patch source closure differs")


def verify_resolved_action_order_source_checkout(
    checkout: Path,
    *,
    base_manifest: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    patch_paths: Sequence[Path],
) -> None:
    """Verify and apply the exact v3 patch chain from the accepted base once."""

    validate_resolved_action_order_source_manifest(source_manifest, base_manifest, patch_paths)
    _normalize_materialized_base(checkout)
    verify_source_checkout(checkout, base_manifest)
    patches = _resolved_action_order_patch_entries(patch_paths)
    records = apply_downstream_patch_chain(
        checkout,
        patches=_resolved_action_order_patch_arguments(patches, patch_paths),
        base_commit=UPSTREAM_COMMIT,
        base_tree=UPSTREAM_TREE,
        expected_source_files=source_manifest["source_files"],
    )
    if manifest_digest(records) != source_manifest.get("source_tree_digest"):
        _fail("post-patch source closure differs")
    if _materialized_workspace_members(checkout) != source_manifest.get("workspace_members"):
        _fail("Cargo workspace members differ")


def create_downstream_build_manifest(
    *,
    source_manifest: Mapping[str, Any],
    rustc_vv: str,
    cargo_version: str,
    maturin_version: str,
    target_triple: str,
    operating_system: str,
    python_version: str,
    wheel: Mapping[str, Any],
) -> dict[str, Any]:
    """Create one canonical v2 build record from verified inputs."""

    validate_build_configuration(
        rust_toolchain=RUST_TOOLCHAIN,
        maturin_version=maturin_version,
        target_triple=target_triple,
        features=FEATURES,
        locked=True,
        no_default_features=True,
    )
    _verify_rust_identity(rustc_vv, cargo_version, target_triple)
    expected_os = "ubuntu-24.04" if target_triple == "x86_64-unknown-linux-gnu" else "windows-2025"
    if operating_system != expected_os:
        _fail("build operating system differs")
    python_tag, abi_tag, platform_tag = _python_tags(python_version, target_triple)
    expected_wheel_identity = {
        "filename": f"poke_engine-{LEGAL_CHOICE_VERSION}-{python_tag}-{abi_tag}-{platform_tag}.whl",
        "tags": [f"{python_tag}-{abi_tag}-{platform_tag}"],
        "root_is_purelib": False,
    }
    if any(wheel.get(key) != value for key, value in expected_wheel_identity.items()):
        _fail("wheel identity differs from the v2 build cell")
    cell_id = f"{operating_system}-x86_64-{python_tag}"
    return {
        "schema_version": 2,
        "schema_id": LEGAL_CHOICE_BUILD_SCHEMA_ID,
        "manifest_id": f"poke-engine-build-{cell_id}-legal-choices-v2",
        "cell_id": cell_id,
        "source_schema_id": LEGAL_CHOICE_SOURCE_SCHEMA_ID,
        "source_manifest_digest": manifest_digest(source_manifest),
        "source_tree_digest": source_manifest.get("source_tree_digest"),
        "downstream_patch_digest": source_manifest["downstream_patch"]["sha256"],
        "rust_toolchain": f"{RUST_TOOLCHAIN}-{target_triple}",
        "rustc_vv": rustc_vv,
        "cargo_version": cargo_version,
        "rustup_components": ["cargo", "rust-std", "rustc"],
        "rust_targets": [target_triple],
        "maturin_version": maturin_version,
        "build_backend": "maturin",
        "build_argv": build_argv(target_triple),
        "locked": True,
        "no_default_features": True,
        "features": list(FEATURES),
        "target_triple": target_triple,
        "operating_system": operating_system,
        "architecture": "x86_64",
        "python": {
            "implementation": "CPython",
            "version": python_version,
            "python_tag": python_tag,
            "abi_tag": abi_tag,
            "platform_tag": platform_tag,
        },
        "distribution": {"name": "poke-engine", "version": LEGAL_CHOICE_VERSION},
        "wheel": dict(wheel),
        "build_environment": {
            "allowlist": [
                {"name": "CARGO_HOME", "value": CONTROLLED_CARGO_HOME},
                {"name": "CARGO_INCREMENTAL", "value": "false"},
                {"name": "CARGO_NET_OFFLINE", "value": "true"},
                {"name": "CARGO_PROFILE_RELEASE_DEBUG", "value": "0"},
                {"name": "PYTHONUTF8", "value": "1"},
                {"name": "SOURCE_DATE_EPOCH", "value": SOURCE_DATE_EPOCH},
            ]
        },
        "adapter_version": LEGAL_CHOICE_ADAPTER_VERSION,
        "canonicalization_profile": "rfc8785-jcs-v1",
    }


def build_one_downstream_wheel(
    *,
    checkout: Path,
    base_manifest: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    patch_path: Path,
    python_executable: Path,
    rustc_executable: Path,
    cargo_executable: Path,
    maturin_executable: Path,
    target_triple: str,
    operating_system: str,
    wheelhouse: Path,
) -> dict[str, Any]:
    """Apply the v2 patch and build one controlled 0.0.49 wheel."""

    verify_downstream_source_checkout(
        checkout,
        base_manifest=base_manifest,
        source_manifest=source_manifest,
        patch_path=patch_path,
    )
    validate_build_configuration(
        rust_toolchain=RUST_TOOLCHAIN,
        maturin_version=MATURIN_VERSION,
        target_triple=target_triple,
        features=FEATURES,
        locked=True,
        no_default_features=True,
    )
    if wheelhouse.exists() or _is_within(wheelhouse, checkout):
        _fail("wheel output directory is not isolated")
    python_version = _python_version(python_executable, cwd=checkout)
    python_tag, abi_tag, platform_tag = _python_tags(python_version, target_triple)
    rustc_vv = _executable_text(rustc_executable, "--version", "--verbose", cwd=checkout)
    cargo_version = _executable_text(cargo_executable, "--version", cwd=checkout)
    _verify_rust_identity(rustc_vv, cargo_version, target_triple)
    if _executable_text(maturin_executable, "--version", cwd=checkout) != (
        f"maturin {MATURIN_VERSION}"
    ):
        _fail("Maturin executable identity differs")
    wheelhouse.parent.mkdir(parents=True, exist_ok=True)
    wheelhouse.mkdir()
    actual_arguments = build_argv(target_triple)
    actual_arguments[0] = str(maturin_executable)
    actual_arguments[actual_arguments.index("python")] = str(python_executable)
    actual_arguments[actual_arguments.index("wheelhouse")] = str(wheelhouse)
    environment = _controlled_build_environment(
        cargo_executable=cargo_executable,
        rustc_executable=rustc_executable,
    )
    _run(actual_arguments, cwd=checkout, environment=environment)
    changed_paths = (
        _git(checkout, "diff", "--name-only", "--no-renames")
        .decode("utf-8", errors="strict")
        .splitlines()
    )
    patch_paths = _patch_paths(patch_path.read_bytes())
    if sorted(changed_paths) != patch_paths:
        _fail("source tree changed during downstream build")
    wheels = sorted(wheelhouse.glob("*.whl"))
    if len(wheels) != 1 or any(path.is_dir() for path in wheelhouse.iterdir()):
        _fail("build output closure differs")
    wheel = inspect_wheel(
        wheels[0],
        python_tag=python_tag,
        abi_tag=abi_tag,
        platform_tag=platform_tag,
        distribution_version=LEGAL_CHOICE_VERSION,
    )
    return create_downstream_build_manifest(
        source_manifest=source_manifest,
        rustc_vv=rustc_vv,
        cargo_version=cargo_version,
        maturin_version=MATURIN_VERSION,
        target_triple=target_triple,
        operating_system=operating_system,
        python_version=python_version,
        wheel=wheel,
    )


def create_resolved_action_order_build_manifest(
    *,
    source_manifest: Mapping[str, Any],
    rustc_vv: str,
    cargo_version: str,
    maturin_version: str,
    target_triple: str,
    operating_system: str,
    python_version: str,
    wheel: Mapping[str, Any],
) -> dict[str, Any]:
    """Create one canonical v3 build record from the verified patch chain."""

    if source_manifest.get("schema_id") != RESOLVED_ACTION_ORDER_SOURCE_SCHEMA_ID:
        _fail("downstream source manifest identity differs")
    patches = source_manifest.get("downstream_patches")
    if not isinstance(patches, list) or len(patches) != 2:
        _fail("patch chain provenance differs")
    validate_build_configuration(
        rust_toolchain=RUST_TOOLCHAIN,
        maturin_version=maturin_version,
        target_triple=target_triple,
        features=FEATURES,
        locked=True,
        no_default_features=True,
    )
    _verify_rust_identity(rustc_vv, cargo_version, target_triple)
    expected_os = "ubuntu-24.04" if target_triple == "x86_64-unknown-linux-gnu" else "windows-2025"
    if operating_system != expected_os:
        _fail("build operating system differs")
    python_tag, abi_tag, platform_tag = _python_tags(python_version, target_triple)
    expected_wheel_identity = {
        "filename": f"poke_engine-{RESOLVED_ACTION_ORDER_VERSION}-{python_tag}-{abi_tag}-{platform_tag}.whl",
        "tags": [f"{python_tag}-{abi_tag}-{platform_tag}"],
        "root_is_purelib": False,
    }
    if any(wheel.get(key) != value for key, value in expected_wheel_identity.items()):
        _fail("wheel identity differs from the v3 build cell")
    cell_id = f"{operating_system}-x86_64-{python_tag}"
    return {
        "schema_version": 3,
        "schema_id": RESOLVED_ACTION_ORDER_BUILD_SCHEMA_ID,
        "manifest_id": f"poke-engine-build-{cell_id}-resolved-order-v3",
        "cell_id": cell_id,
        "source_schema_id": RESOLVED_ACTION_ORDER_SOURCE_SCHEMA_ID,
        "source_manifest_digest": manifest_digest(source_manifest),
        "source_tree_digest": source_manifest.get("source_tree_digest"),
        "downstream_patch_chain_digest": manifest_digest(patches),
        "rust_toolchain": f"{RUST_TOOLCHAIN}-{target_triple}",
        "rustc_vv": rustc_vv,
        "cargo_version": cargo_version,
        "rustup_components": ["cargo", "rust-std", "rustc"],
        "rust_targets": [target_triple],
        "maturin_version": maturin_version,
        "build_backend": "maturin",
        "build_argv": build_argv(target_triple),
        "locked": True,
        "no_default_features": True,
        "features": list(FEATURES),
        "target_triple": target_triple,
        "operating_system": operating_system,
        "architecture": "x86_64",
        "python": {
            "implementation": "CPython",
            "version": python_version,
            "python_tag": python_tag,
            "abi_tag": abi_tag,
            "platform_tag": platform_tag,
        },
        "distribution": {"name": "poke-engine", "version": RESOLVED_ACTION_ORDER_VERSION},
        "wheel": dict(wheel),
        "build_environment": {
            "allowlist": [
                {"name": "CARGO_HOME", "value": CONTROLLED_CARGO_HOME},
                {"name": "CARGO_INCREMENTAL", "value": "false"},
                {"name": "CARGO_NET_OFFLINE", "value": "true"},
                {"name": "CARGO_PROFILE_RELEASE_DEBUG", "value": "0"},
                {"name": "PYTHONUTF8", "value": "1"},
                {"name": "SOURCE_DATE_EPOCH", "value": SOURCE_DATE_EPOCH},
            ]
        },
        "adapter_version": RESOLVED_ACTION_ORDER_ADAPTER_VERSION,
        "canonicalization_profile": "rfc8785-jcs-v1",
    }


def build_one_resolved_action_order_wheel(
    *,
    checkout: Path,
    base_manifest: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    patch_paths: Sequence[Path],
    python_executable: Path,
    rustc_executable: Path,
    cargo_executable: Path,
    maturin_executable: Path,
    target_triple: str,
    operating_system: str,
    wheelhouse: Path,
) -> dict[str, Any]:
    """Apply the v3 patch chain and build one controlled 0.0.50 wheel."""

    verify_resolved_action_order_source_checkout(
        checkout,
        base_manifest=base_manifest,
        source_manifest=source_manifest,
        patch_paths=patch_paths,
    )
    validate_build_configuration(
        rust_toolchain=RUST_TOOLCHAIN,
        maturin_version=MATURIN_VERSION,
        target_triple=target_triple,
        features=FEATURES,
        locked=True,
        no_default_features=True,
    )
    if wheelhouse.exists() or _is_within(wheelhouse, checkout):
        _fail("wheel output directory is not isolated")
    python_version = _python_version(python_executable, cwd=checkout)
    python_tag, abi_tag, platform_tag = _python_tags(python_version, target_triple)
    rustc_vv = _executable_text(rustc_executable, "--version", "--verbose", cwd=checkout)
    cargo_version = _executable_text(cargo_executable, "--version", cwd=checkout)
    _verify_rust_identity(rustc_vv, cargo_version, target_triple)
    if _executable_text(maturin_executable, "--version", cwd=checkout) != (
        f"maturin {MATURIN_VERSION}"
    ):
        _fail("Maturin executable identity differs")
    wheelhouse.parent.mkdir(parents=True, exist_ok=True)
    wheelhouse.mkdir()
    actual_arguments = build_argv(target_triple)
    actual_arguments[0] = str(maturin_executable)
    actual_arguments[actual_arguments.index("python")] = str(python_executable)
    actual_arguments[actual_arguments.index("wheelhouse")] = str(wheelhouse)
    environment = _controlled_build_environment(
        cargo_executable=cargo_executable,
        rustc_executable=rustc_executable,
    )
    _run(actual_arguments, cwd=checkout, environment=environment)
    changed_paths = (
        _git(checkout, "diff", "--name-only", "--no-renames")
        .decode("utf-8", errors="strict")
        .splitlines()
    )
    expected_paths = sorted(
        {path for patch_path in patch_paths for path in _patch_paths(patch_path.read_bytes())}
    )
    if sorted(changed_paths) != expected_paths:
        _fail("source tree changed during downstream build")
    wheels = sorted(wheelhouse.glob("*.whl"))
    if len(wheels) != 1 or any(path.is_dir() for path in wheelhouse.iterdir()):
        _fail("build output closure differs")
    wheel = inspect_wheel(
        wheels[0],
        python_tag=python_tag,
        abi_tag=abi_tag,
        platform_tag=platform_tag,
        distribution_version=RESOLVED_ACTION_ORDER_VERSION,
    )
    return create_resolved_action_order_build_manifest(
        source_manifest=source_manifest,
        rustc_vv=rustc_vv,
        cargo_version=cargo_version,
        maturin_version=MATURIN_VERSION,
        target_triple=target_triple,
        operating_system=operating_system,
        python_version=python_version,
        wheel=wheel,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    source = subparsers.add_parser("source", help="create a canonical source manifest")
    source.add_argument("--checkout", type=Path, required=True)
    source.add_argument("--retrieved-on", required=True)
    source.add_argument("--output", type=Path, required=True)
    acquire = subparsers.add_parser("acquire", help="acquire the exact accepted source")
    acquire.add_argument("--checkout", type=Path, required=True)
    verify = subparsers.add_parser("verify-source", help="verify the pinned source checkout")
    verify.add_argument("--checkout", type=Path, required=True)
    verify.add_argument("--source-manifest", type=Path, required=True)
    build = subparsers.add_parser("build", help="build one controlled wheel cell")
    build.add_argument("--checkout", type=Path, required=True)
    build.add_argument("--source-manifest", type=Path, required=True)
    build.add_argument("--python", type=Path, required=True)
    build.add_argument("--rustc", type=Path, required=True)
    build.add_argument("--cargo", type=Path, required=True)
    build.add_argument("--maturin", type=Path, required=True)
    build.add_argument("--target", choices=sorted(TARGETS), required=True)
    build.add_argument(
        "--operating-system", choices=("ubuntu-24.04", "windows-2025"), required=True
    )
    build.add_argument("--wheelhouse", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    source_v2 = subparsers.add_parser(
        "source-v2", help="create a downstream-patched source manifest"
    )
    source_v2.add_argument("--checkout", type=Path, required=True)
    source_v2.add_argument("--base-source-manifest", type=Path, required=True)
    source_v2.add_argument("--patch", type=Path, required=True)
    source_v2.add_argument("--retrieved-on", required=True)
    source_v2.add_argument("--output", type=Path, required=True)
    verify_v2 = subparsers.add_parser(
        "verify-source-v2", help="verify a downstream-patched source checkout"
    )
    verify_v2.add_argument("--checkout", type=Path, required=True)
    verify_v2.add_argument("--base-source-manifest", type=Path, required=True)
    verify_v2.add_argument("--source-manifest", type=Path, required=True)
    verify_v2.add_argument("--patch", type=Path, required=True)
    build_v2 = subparsers.add_parser("build-v2", help="build one downstream-patched wheel cell")
    build_v2.add_argument("--checkout", type=Path, required=True)
    build_v2.add_argument("--base-source-manifest", type=Path, required=True)
    build_v2.add_argument("--source-manifest", type=Path, required=True)
    build_v2.add_argument("--patch", type=Path, required=True)
    build_v2.add_argument("--python", type=Path, required=True)
    build_v2.add_argument("--rustc", type=Path, required=True)
    build_v2.add_argument("--cargo", type=Path, required=True)
    build_v2.add_argument("--maturin", type=Path, required=True)
    build_v2.add_argument("--target", choices=sorted(TARGETS), required=True)
    build_v2.add_argument(
        "--operating-system", choices=("ubuntu-24.04", "windows-2025"), required=True
    )
    build_v2.add_argument("--wheelhouse", type=Path, required=True)
    build_v2.add_argument("--output", type=Path, required=True)
    source_v3 = subparsers.add_parser(
        "source-v3", help="create an ordered downstream-patch source manifest"
    )
    source_v3.add_argument("--checkout", type=Path, required=True)
    source_v3.add_argument("--base-source-manifest", type=Path, required=True)
    source_v3.add_argument("--legal-choice-patch", type=Path, required=True)
    source_v3.add_argument("--resolved-action-order-patch", type=Path, required=True)
    source_v3.add_argument("--retrieved-on", required=True)
    source_v3.add_argument("--output", type=Path, required=True)
    verify_v3 = subparsers.add_parser(
        "verify-source-v3", help="verify an ordered downstream-patch source checkout"
    )
    verify_v3.add_argument("--checkout", type=Path, required=True)
    verify_v3.add_argument("--base-source-manifest", type=Path, required=True)
    verify_v3.add_argument("--source-manifest", type=Path, required=True)
    verify_v3.add_argument("--legal-choice-patch", type=Path, required=True)
    verify_v3.add_argument("--resolved-action-order-patch", type=Path, required=True)
    build_v3 = subparsers.add_parser(
        "build-v3", help="build one ordered downstream-patch wheel cell"
    )
    build_v3.add_argument("--checkout", type=Path, required=True)
    build_v3.add_argument("--base-source-manifest", type=Path, required=True)
    build_v3.add_argument("--source-manifest", type=Path, required=True)
    build_v3.add_argument("--legal-choice-patch", type=Path, required=True)
    build_v3.add_argument("--resolved-action-order-patch", type=Path, required=True)
    build_v3.add_argument("--python", type=Path, required=True)
    build_v3.add_argument("--rustc", type=Path, required=True)
    build_v3.add_argument("--cargo", type=Path, required=True)
    build_v3.add_argument("--maturin", type=Path, required=True)
    build_v3.add_argument("--target", choices=sorted(TARGETS), required=True)
    build_v3.add_argument(
        "--operating-system", choices=("ubuntu-24.04", "windows-2025"), required=True
    )
    build_v3.add_argument("--wheelhouse", type=Path, required=True)
    build_v3.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "acquire":
            acquire_pinned_source(args.checkout)
        elif args.command == "source":
            manifest = create_source_manifest(args.checkout, retrieved_on=args.retrieved_on)
            validate_pinned_source_manifest(manifest)
            _write_new(args.output, canonicalize(manifest) + b"\n")
        elif args.command == "verify-source":
            manifest = _load_json(args.source_manifest)
            validate_pinned_source_manifest(manifest)
            verify_source_checkout(args.checkout, manifest)
        elif args.command == "source-v2":
            base_manifest = _load_json(args.base_source_manifest)
            manifest = create_downstream_source_manifest(
                args.checkout,
                base_manifest=base_manifest,
                patch_path=args.patch,
                retrieved_on=args.retrieved_on,
            )
            _write_new(args.output, canonicalize(manifest) + b"\n")
        elif args.command == "verify-source-v2":
            base_manifest = _load_json(args.base_source_manifest)
            manifest = _load_json(args.source_manifest)
            verify_downstream_source_checkout(
                args.checkout,
                base_manifest=base_manifest,
                source_manifest=manifest,
                patch_path=args.patch,
            )
        elif args.command == "source-v3":
            base_manifest = _load_json(args.base_source_manifest)
            manifest = create_resolved_action_order_source_manifest(
                args.checkout,
                base_manifest=base_manifest,
                patch_paths=(args.legal_choice_patch, args.resolved_action_order_patch),
                retrieved_on=args.retrieved_on,
            )
            _write_new(args.output, canonicalize(manifest) + b"\n")
        elif args.command == "verify-source-v3":
            base_manifest = _load_json(args.base_source_manifest)
            manifest = _load_json(args.source_manifest)
            verify_resolved_action_order_source_checkout(
                args.checkout,
                base_manifest=base_manifest,
                source_manifest=manifest,
                patch_paths=(args.legal_choice_patch, args.resolved_action_order_patch),
            )
        else:
            manifest = _load_json(args.source_manifest)
            if _is_within(args.output, args.checkout) or _is_within(args.output, args.wheelhouse):
                _fail("build manifest output aliases controlled inputs")
            if args.command == "build-v2":
                base_manifest = _load_json(args.base_source_manifest)
                build_manifest = build_one_downstream_wheel(
                    checkout=args.checkout,
                    base_manifest=base_manifest,
                    source_manifest=manifest,
                    patch_path=args.patch,
                    python_executable=args.python,
                    rustc_executable=args.rustc,
                    cargo_executable=args.cargo,
                    maturin_executable=args.maturin,
                    target_triple=args.target,
                    operating_system=args.operating_system,
                    wheelhouse=args.wheelhouse,
                )
            elif args.command == "build-v3":
                base_manifest = _load_json(args.base_source_manifest)
                build_manifest = build_one_resolved_action_order_wheel(
                    checkout=args.checkout,
                    base_manifest=base_manifest,
                    source_manifest=manifest,
                    patch_paths=(args.legal_choice_patch, args.resolved_action_order_patch),
                    python_executable=args.python,
                    rustc_executable=args.rustc,
                    cargo_executable=args.cargo,
                    maturin_executable=args.maturin,
                    target_triple=args.target,
                    operating_system=args.operating_system,
                    wheelhouse=args.wheelhouse,
                )
            else:
                build_manifest = build_one_wheel(
                    checkout=args.checkout,
                    source_manifest=manifest,
                    python_executable=args.python,
                    rustc_executable=args.rustc,
                    cargo_executable=args.cargo,
                    maturin_executable=args.maturin,
                    target_triple=args.target,
                    operating_system=args.operating_system,
                    wheelhouse=args.wheelhouse,
                )
            _write_new(args.output, canonicalize(build_manifest) + b"\n")
    except BuildPokeEngineError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(_success_message(args.command))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
