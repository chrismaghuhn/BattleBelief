"""Run the read-only, local Pokémon Showdown Lab-oracle smoke.

This tool never acquires source, installs dependencies, or builds Showdown.  It
only verifies a previously bound checkout/build manifest, executes deterministic
fixtures, and exercises the separate loopback-server lifecycle.  Its stdout is
canonical stable evidence; diagnostics deliberately contain only a failure
class.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from battlebelief_core.canonicalization import canonicalize, manifest_digest  # noqa: E402
from battlebelief_lab.oracle.showdown import (  # noqa: E402
    ShowdownBuildManifest,
    ShowdownOracleConfig,
    ShowdownOracleSession,
    ShowdownSourceManifest,
)
from battlebelief_lab.oracle.showdown.errors import OracleFailureClass  # noqa: E402
from battlebelief_lab.oracle.showdown.installation import (  # noqa: E402
    BuildOracleError,
    verify_build_manifest,
)
from battlebelief_lab.oracle.showdown.network import guarded_node_environment  # noqa: E402
from battlebelief_lab.oracle.showdown.process import (  # noqa: E402
    OracleProcessError,
    ShowdownProcessLimits,
    ShowdownProcessRunner,
    ShowdownProcessSpec,
)
from battlebelief_lab.oracle.showdown.protocol import EndMessage  # noqa: E402
from battlebelief_lab.oracle.showdown.server import (  # noqa: E402
    LoopbackServerConfig,
    LoopbackServerLimits,
    LoopbackServerSmoke,
)
from battlebelief_lab.oracle.showdown.session import (  # noqa: E402
    _build_steps,
    _parse_fixture,
    _transcript_document,
)

_FIXTURE_NAMES = ("minimal_gen9ou_input.json", "tera_transition_input.json")
_WINDOWS_ORACLE_ENVIRONMENT_KEYS = (
    "COMSPEC",
    "WINDIR",
    "PATHEXT",
    "TEMP",
    "TMP",
)
_PROCESS_LIMITS = ShowdownProcessLimits(
    start_timeout_seconds=20.0,
    write_timeout_seconds=10.0,
    response_timeout_seconds=20.0,
    fixture_timeout_seconds=60.0,
    graceful_shutdown_timeout_seconds=5.0,
    forced_shutdown_timeout_seconds=10.0,
    max_stdout_bytes=512 * 1024,
    max_messages=2_048,
    max_input_bytes=128 * 1024,
    max_stderr_bytes=128 * 1024,
)
_SERVER_LIMITS = LoopbackServerLimits(
    start_timeout_seconds=20.0,
    readiness_timeout_seconds=40.0,
    graceful_shutdown_timeout_seconds=5.0,
    forced_shutdown_timeout_seconds=10.0,
    max_stdout_bytes=128 * 1024,
    max_stderr_bytes=128 * 1024,
)


class OracleSmokeError(Exception):
    """A classified failure which is safe to expose on the command line."""

    def __init__(self, failure_class: OracleFailureClass) -> None:
        self.failure_class = failure_class
        super().__init__(failure_class.value)


def oracle_environment(
    node_executable: Path, source: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Return the small child environment required for the local Node oracle.

    This is intentionally a Node-process hermeticity boundary, not an OS
    firewall. Its PATH contains only the exact Node executable directory so
    upstream child-process lookups cannot reach host Python, Git, or other
    unrelated executables. Proxy, home, identity, hostname, and unrelated
    secret-bearing variables do not cross into the simulator or lifecycle
    server.
    """

    candidate = os.environ if source is None else source
    if node_executable.is_symlink() or not node_executable.name:
        raise ValueError("oracle child environment requires a concrete Node executable")
    environment: dict[str, str] = {"PATH": str(node_executable.parent)}
    if os.name == "nt":
        system_root = candidate.get("SYSTEMROOT") or candidate.get("SystemRoot")
        if type(system_root) is not str or not system_root:
            raise ValueError("Windows oracle child environment requires SystemRoot")
        environment["SYSTEMROOT"] = system_root
        for key in _WINDOWS_ORACLE_ENVIRONMENT_KEYS:
            value = candidate.get(key)
            if type(value) is str and value:
                environment[key] = value
    return environment


def _json_object(path: Path, *, label: str) -> dict[str, object]:
    """Load a JSON object while rejecting duplicate keys and invalid UTF-8."""

    def no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label} duplicate JSON key")
            result[key] = value
        return result

    try:
        value = json.loads(path.read_bytes().decode("utf-8"), object_pairs_hook=no_duplicates)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is not a strict UTF-8 JSON document") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def fixture_paths(directory: Path) -> tuple[Path, Path]:
    """Bind the smoke to exactly the two small project-authored fixtures."""

    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("fixture directory is invalid")
    entries = {entry.name for entry in directory.iterdir()}
    if entries != set(_FIXTURE_NAMES):
        raise ValueError("fixture set differs")
    paths = tuple(directory / name for name in _FIXTURE_NAMES)
    if any(path.is_symlink() or not path.is_file() for path in paths):
        raise ValueError("fixture path is invalid")
    return cast(tuple[Path, Path], paths)


def canonical_smoke_summary(
    *,
    probe_role: str,
    source_manifest_digest: str,
    build_manifest_digest: str,
    fixture_results: Sequence[tuple[str, str]],
    lifecycle_profile_digest: str,
) -> dict[str, object]:
    """Return the only evidence the smoke prints: stable identities and digests."""

    return {
        "probe_role": probe_role,
        "source_manifest_digest": source_manifest_digest,
        "build_manifest_digest": build_manifest_digest,
        "fixture_result_digests": dict(sorted(fixture_results)),
        "lifecycle_profile_digest": lifecycle_profile_digest,
    }


def _load_manifests(
    source_path: Path, build_path: Path
) -> tuple[ShowdownSourceManifest, ShowdownBuildManifest]:
    source = ShowdownSourceManifest.from_dict(_json_object(source_path, label="source manifest"))
    build = ShowdownBuildManifest.from_dict(_json_object(build_path, label="build manifest"))
    return source, build


def _fixture_document(path: Path) -> Mapping[str, object]:
    return _json_object(path, label="fixture")


async def _run_candidate_fixture_twice(
    config: ShowdownOracleConfig, fixture_document: Mapping[str, object]
) -> tuple[str, str]:
    """Require byte-identical canonical results from independent fixture processes."""

    session = ShowdownOracleSession(config)
    first = await session.run_fixture(fixture_document)
    second = await session.run_fixture(fixture_document)
    if first.status != "success":
        raise OracleSmokeError(cast(OracleFailureClass, first.failure_class))
    if second.status != "success":
        raise OracleSmokeError(cast(OracleFailureClass, second.failure_class))
    if first.canonical_bytes() != second.canonical_bytes():
        raise OracleSmokeError(OracleFailureClass.PROTOCOL_DESYNCHRONIZATION)
    return first.fixture_id, first.digest


async def _run_comparison_fixture(
    *,
    source: ShowdownSourceManifest,
    build: ShowdownBuildManifest,
    checkout: Path,
    node: Path,
    environment: Mapping[str, str],
    fixture_document: Mapping[str, object],
) -> tuple[str, str]:
    """Exercise stdio without pretending a comparison Node is the runtime pin."""

    fixture = _parse_fixture(fixture_document)
    if fixture.ruleset_snapshot_digest != build.ruleset_snapshot_digest:
        raise OracleSmokeError(OracleFailureClass.RULESET_REJECTED)
    input_document = {
        "fixture_id": fixture.fixture_id,
        "steps": [step.input_bytes.decode("utf-8") for step in _build_steps(fixture)],
    }
    try:
        with guarded_node_environment(environment) as guarded_environment:
            result = await ShowdownProcessRunner().run(
                ShowdownProcessSpec(
                    argv=(str(node), "pokemon-showdown", "--skip-build", "simulate-battle"),
                    cwd=checkout,
                    env=guarded_environment,
                    steps=_build_steps(fixture),
                ),
                _PROCESS_LIMITS,
            )
    except OracleProcessError as error:
        raise OracleSmokeError(error.failure_class) from error
    transcript = _transcript_document(result.messages)
    if (
        result.terminal_side_error is not None
        or not result.completed_barriers
        or not any(isinstance(message, EndMessage) for message in result.messages)
    ):
        raise OracleSmokeError(OracleFailureClass.PROTOCOL_DESYNCHRONIZATION)
    if fixture.expected_tera_line is not None and not any(
        fixture.expected_tera_line == line
        for message in transcript
        if message["kind"] == "update"
        for line in cast(list[str], message["lines"])
    ):
        raise OracleSmokeError(OracleFailureClass.RULESET_REJECTED)
    return fixture.fixture_id, manifest_digest(
        {
            "fixture_id": fixture.fixture_id,
            "source_manifest_digest": source.digest,
            "build_manifest_digest": build.digest,
            "fixture_digest": fixture.fixture_digest,
            "seed_digest": fixture.seed_digest,
            "input_digest": manifest_digest(input_document),
            "transcript_digest": manifest_digest(transcript),
        }
    )


async def _run_smoke(
    *,
    source: ShowdownSourceManifest,
    build: ShowdownBuildManifest,
    checkout: Path,
    node: Path,
    npm: Path,
    fixture_documents: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if build.probe_role not in {"candidate", "comparison"}:
        raise OracleSmokeError(OracleFailureClass.NODE_VERSION_NOT_APPROVED)
    try:
        await asyncio.to_thread(
            verify_build_manifest,
            source_manifest=source,
            build_manifest=build,
            checkout_directory=checkout,
            node_executable=node,
            npm_executable=npm,
        )
    except BuildOracleError as error:
        raise OracleSmokeError(error.failure_class) from error

    environment = oracle_environment(node)
    try:
        lifecycle = await LoopbackServerSmoke().run(
            LoopbackServerConfig(
                source_directory=checkout,
                node_executable=node,
                environment=environment,
            ),
            _SERVER_LIMITS,
        )
    except OracleProcessError as error:
        raise OracleSmokeError(error.failure_class) from error
    try:
        await asyncio.to_thread(
            verify_build_manifest,
            source_manifest=source,
            build_manifest=build,
            checkout_directory=checkout,
            node_executable=node,
            npm_executable=npm,
        )
    except BuildOracleError as error:
        raise OracleSmokeError(error.failure_class) from error
    try:
        if build.probe_role == "candidate":
            config = ShowdownOracleConfig(
                source_manifest=source,
                build_manifest=build,
                source_directory=checkout,
                node_executable=node,
                npm_executable=npm,
                process_limits=_PROCESS_LIMITS,
                environment=environment,
            )
            fixture_results = [
                await _run_candidate_fixture_twice(config, document)
                for document in fixture_documents
            ]
        else:
            fixture_results = [
                await _run_comparison_fixture(
                    source=source,
                    build=build,
                    checkout=checkout,
                    node=node,
                    environment=environment,
                    fixture_document=document,
                )
                for document in fixture_documents
            ]
    except OracleProcessError as error:
        raise OracleSmokeError(error.failure_class) from error
    lifecycle_profile = json.loads(lifecycle.canonical_profile_bytes().decode("utf-8"))
    return canonical_smoke_summary(
        probe_role=build.probe_role,
        source_manifest_digest=source.digest,
        build_manifest_digest=build.digest,
        fixture_results=fixture_results,
        lifecycle_profile_digest=manifest_digest(lifecycle_profile),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--build-manifest", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--npm", type=Path, required=True)
    parser.add_argument(
        "--fixtures-dir",
        "--fixtures-directory",
        dest="fixtures_directory",
        type=Path,
        required=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        source, build = _load_manifests(args.source_manifest, args.build_manifest)
        documents = tuple(
            _fixture_document(path) for path in fixture_paths(args.fixtures_directory)
        )
        summary = asyncio.run(
            _run_smoke(
                source=source,
                build=build,
                checkout=args.checkout,
                node=args.node,
                npm=args.npm,
                fixture_documents=documents,
            )
        )
    except OracleSmokeError as error:
        print(error.failure_class.value, file=sys.stderr)
        return 1
    except BuildOracleError as error:
        print(error.failure_class.value, file=sys.stderr)
        return 1
    except OracleProcessError as error:
        print(error.failure_class.value, file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        print(OracleFailureClass.TOOL_INPUT_INVALID.value, file=sys.stderr)
        return 1
    print(canonicalize(summary).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
