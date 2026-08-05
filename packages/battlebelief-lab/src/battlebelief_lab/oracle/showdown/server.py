"""The local loopback server smoke; it is never the mechanics oracle."""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from battlebelief_core.canonicalization import canonicalize
from battlebelief_lab.oracle.showdown.errors import OracleFailureClass
from battlebelief_lab.oracle.showdown.network import (
    EXTERNAL_NETWORK_MARKER,
    LOOPBACK_LISTEN_MARKER,
    guarded_node_environment,
    network_guard_digest,
)
from battlebelief_lab.oracle.showdown.process import (
    DEFAULT_READ_CHUNK_BYTES,
    ManagedProcess,
    OracleProcessError,
    OrphanVerifier,
    ProcessLauncher,
    ProcessTerminator,
    _default_launcher,
    _default_orphan_verifier,
    _default_terminate,
    _job_for,
)

_LOOPBACK_ADDRESSES = frozenset({"127.0.0.1", "::1"})
_SERVER_CONFIG_NAME = "config.js"
_UPSTREAM_LOG_INDEX = Path("logs") / ".gitindex"
_GIT_TREE_OID = re.compile(r"[0-9a-f]{40}")
_GIT_INDEX_CHECK_TIMEOUT_SECONDS = 5.0
# The complete ``ProcessType`` list in server/config-loader.ts at the bound
# Showdown commit.  Do not use a partial config here: config-loader preserves
# omitted keys and upstream modules commonly default them to one child.
_SERVER_SUBPROCESS_COUNTS = (
    ("localartemis", 0),
    ("remoteartemis", 0),
    ("battlesearch", 0),
    ("datasearch", 0),
    ("friends", 0),
    ("chatdb", 0),
    ("pm", 0),
    ("modlog", 0),
    ("network", 1),
    ("simulator", 0),
    ("validator", 0),
    ("verifier", 0),
)


@dataclass(frozen=True, slots=True)
class LoopbackServerLimits:
    """Bounded operational lifecycle settings, excluded from canonical evidence."""

    start_timeout_seconds: float
    readiness_timeout_seconds: float
    graceful_shutdown_timeout_seconds: float
    forced_shutdown_timeout_seconds: float
    max_stdout_bytes: int
    max_stderr_bytes: int

    def __post_init__(self) -> None:
        if any(
            value <= 0
            for value in (
                self.start_timeout_seconds,
                self.readiness_timeout_seconds,
                self.graceful_shutdown_timeout_seconds,
                self.forced_shutdown_timeout_seconds,
            )
        ):
            raise ValueError("all server time limits must be positive")
        if self.max_stdout_bytes <= 0 or self.max_stderr_bytes <= 0:
            raise ValueError("all server stream limits must be positive")


@dataclass(frozen=True, slots=True)
class LoopbackServerConfig:
    """Operational-only server configuration with no evidence-bearing port."""

    source_directory: Path
    node_executable: Path
    environment: Mapping[str, str]
    bind_address: str = "127.0.0.1"
    port: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.source_directory, Path) or not isinstance(
            self.node_executable, Path
        ):
            raise TypeError("source_directory and node_executable must be Path values")
        if self.bind_address not in _LOOPBACK_ADDRESSES:
            raise ValueError("server bind address must be a literal loopback address")
        if self.port != 0:
            raise ValueError("server smoke must use OS-assigned port 0")
        if any(
            type(key) is not str or type(value) is not str
            for key, value in self.environment.items()
        ):
            raise TypeError("environment keys and values must be strings")
        if os.name == "nt" and not self.environment.get("SYSTEMROOT"):
            raise ValueError("Windows Node execution requires an explicit non-empty SYSTEMROOT")
        object.__setattr__(self, "environment", MappingProxyType(dict(self.environment)))


@dataclass(frozen=True, slots=True)
class LoopbackServerResult:
    """Successful lifecycle-only result; it carries no port, PID, path, or time."""

    bind_address: str
    ready: bool
    forced_shutdown: bool

    def canonical_profile_bytes(self) -> bytes:
        """Return only stable profile facts, never the ephemeral bound port."""

        return canonicalize(
            {
                "profile": "showdown-loopback-server-lifecycle-v1",
                "bind_address": self.bind_address,
                "network_guard_digest": network_guard_digest(),
            }
        )


@dataclass(slots=True)
class _ServerDrain:
    stdout_bytes: int = 0
    stderr_bytes: int = 0
    stderr: bytearray = field(default_factory=bytearray)
    ready: bool = False
    external_network_attempt: bool = False
    activity: asyncio.Event = field(default_factory=asyncio.Event)


def _controlled_config_bytes(bind_address: str) -> bytes:
    """Render the project-authored minimal server config, with no public route."""

    if bind_address not in _LOOPBACK_ADDRESSES:
        raise ValueError("server bind address must be a literal loopback address")
    subprocesses = ", ".join(
        f"{process_type}: {count}" for process_type, count in _SERVER_SUBPROCESS_COUNTS
    )
    return (
        "'use strict';\n"
        "exports.port = 0;\n"
        f"exports.bindaddress = '{bind_address}';\n"
        "exports.ssl = null;\n"
        "exports.lazysockets = false;\n"
        f"exports.subprocesses = {{{subprocesses}}};\n"
        "exports.noNetRequests = true;\n"
        "exports.nofswriting = true;\n"
        "exports.watchconfig = false;\n"
        "exports.repl = false;\n"
        "exports.logchat = false;\n"
        "exports.loguserstats = 0;\n"
        "exports.reportjoins = false;\n"
        "exports.reportbattles = false;\n"
        "exports.loginserver = 'http://127.0.0.1:9/';\n"
        "exports.serverid = '';\n"
        "exports.servertoken = '';\n"
    ).encode()


def _write_controlled_config(config: LoopbackServerConfig) -> tuple[Path, bytes]:
    config_path = config.source_directory / "config" / _SERVER_CONFIG_NAME
    expected = _controlled_config_bytes(config.bind_address)
    if config_path.exists() or config_path.is_symlink():
        raise OracleProcessError(
            OracleFailureClass.SOURCE_DIRTY, "server config must be absent before the smoke"
        )
    try:
        with config_path.open("xb") as handle:
            handle.write(expected)
        if config_path.read_bytes() != expected:
            raise OSError("server config bytes differ")
    except OSError as error:
        with contextlib.suppress(OSError):
            config_path.unlink()
        raise OracleProcessError(
            OracleFailureClass.SOURCE_DIRTY, "controlled server config could not be written"
        ) from error
    return config_path, expected


def _ensure_upstream_log_index_absent(config: LoopbackServerConfig) -> Path:
    """Require an unmodified checkout before the server creates its log index."""

    log_index = config.source_directory / _UPSTREAM_LOG_INDEX
    if log_index.exists() or log_index.is_symlink():
        raise OracleProcessError(
            OracleFailureClass.SOURCE_DIRTY,
            "upstream server log index must be absent before the smoke",
        )
    return log_index


def _resolve_git_index_trees(source_directory: Path, log_index: Path) -> tuple[str, str]:
    """Resolve HEAD and Showdown's temporary index to semantic Git tree OIDs."""

    base_environment = {
        key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")
    }

    def git_tree(arguments: tuple[str, ...], environment: Mapping[str, str]) -> str:
        try:
            result = subprocess.run(
                ("git", *arguments),
                cwd=source_directory,
                env=dict(environment),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                check=False,
                timeout=_GIT_INDEX_CHECK_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise OracleProcessError(
                OracleFailureClass.SOURCE_DIRTY,
                "upstream server log index could not be validated",
            ) from error
        try:
            tree = result.stdout.decode("ascii").strip()
        except UnicodeDecodeError as error:
            raise OracleProcessError(
                OracleFailureClass.SOURCE_DIRTY,
                "upstream server log index tree is invalid",
            ) from error
        if result.returncode != 0 or _GIT_TREE_OID.fullmatch(tree) is None:
            raise OracleProcessError(
                OracleFailureClass.SOURCE_DIRTY,
                "upstream server log index tree is invalid",
            )
        return tree

    head_tree = git_tree(("rev-parse", "HEAD^{tree}"), base_environment)
    index_environment = dict(base_environment)
    index_environment["GIT_INDEX_FILE"] = str(log_index)
    generated_tree = git_tree(("write-tree",), index_environment)
    return head_tree, generated_tree


def _remove_generated_log_index(
    log_index: Path,
    *,
    tree_resolver: Callable[[Path, Path], tuple[str, str]] = _resolve_git_index_trees,
) -> None:
    """Validate and remove only the ignored index generated by the server.

    The initial absence check means this never deletes pre-existing source.  A
    byte-identical copy can be removed directly. Showdown also runs Git against
    this temporary index, so Git may serialize equivalent index bytes
    differently across versions. In that case both indexes must resolve to the
    same HEAD tree before removal. A symlink, invalid index, divergent tree, or
    failed deletion is source dirtiness, not cleanup best effort. Other
    generated paths deliberately remain for the verifier to reject fail-closed.
    """

    if not log_index.exists() and not log_index.is_symlink():
        return
    source_directory = log_index.parent.parent
    git_index = source_directory / ".git" / "index"
    if (
        log_index.is_symlink()
        or not log_index.is_file()
        or git_index.is_symlink()
        or not git_index.is_file()
    ):
        raise OracleProcessError(
            OracleFailureClass.SOURCE_DIRTY,
            "upstream server log index differs",
        )
    try:
        bytes_match = log_index.read_bytes() == git_index.read_bytes()
        if not bytes_match:
            head_tree, generated_tree = tree_resolver(source_directory, log_index)
            if (
                _GIT_TREE_OID.fullmatch(head_tree) is None
                or _GIT_TREE_OID.fullmatch(generated_tree) is None
                or generated_tree != head_tree
            ):
                raise OSError("upstream server log index tree differs")
        log_index.unlink()
    except OracleProcessError:
        raise
    except (OSError, ValueError) as error:
        raise OracleProcessError(
            OracleFailureClass.SOURCE_DIRTY,
            "upstream server log index could not be removed",
        ) from error
    if log_index.exists() or log_index.is_symlink():
        raise OracleProcessError(
            OracleFailureClass.SOURCE_DIRTY,
            "upstream server log index remains",
        )


def _remove_controlled_config(config_path: Path, expected: bytes) -> None:
    try:
        if (
            config_path.is_symlink()
            or not config_path.is_file()
            or config_path.read_bytes() != expected
        ):
            raise OSError("server config bytes differ")
        config_path.unlink()
        if config_path.exists() or config_path.is_symlink():
            raise OSError("server config remains")
    except OSError as error:
        raise OracleProcessError(
            OracleFailureClass.SOURCE_DIRTY, "controlled server config could not be removed"
        ) from error


class LoopbackServerSmoke:
    """Start and stop one guarded Showdown server, without using it as an oracle."""

    def __init__(
        self,
        *,
        launcher: ProcessLauncher = _default_launcher,
        terminator: ProcessTerminator | None = None,
        orphan_verifier: OrphanVerifier = _default_orphan_verifier,
    ) -> None:
        self._launcher = launcher
        self._terminator = terminator
        self._orphan_verifier = orphan_verifier

    async def run(
        self, config: LoopbackServerConfig, limits: LoopbackServerLimits
    ) -> LoopbackServerResult:
        """Run the lifecycle smoke and retain only its stable profile on success."""

        config_path: Path | None = None
        log_index: Path | None = None
        expected_config = b""
        process: ManagedProcess | None = None
        return_task: asyncio.Task[int] | None = None
        stdout_task: asyncio.Task[None] | None = None
        stderr_task: asyncio.Task[None] | None = None
        state = _ServerDrain()
        pending_error: OracleProcessError | None = None
        forced_shutdown = False
        try:
            log_index = _ensure_upstream_log_index_absent(config)
            config_path, expected_config = _write_controlled_config(config)
            with guarded_node_environment(config.environment) as environment:
                try:
                    process = await asyncio.wait_for(
                        self._launcher(
                            (
                                str(config.node_executable),
                                "pokemon-showdown",
                                "--skip-build",
                                "start",
                                "0",
                            ),
                            config.source_directory,
                            environment,
                            True,
                        ),
                        timeout=limits.start_timeout_seconds,
                    )
                except FileNotFoundError as error:
                    raise OracleProcessError(
                        OracleFailureClass.NODE_NOT_FOUND, "node executable not found"
                    ) from error
                except TimeoutError as error:
                    raise OracleProcessError(
                        OracleFailureClass.START_TIMEOUT, "server process start timed out"
                    ) from error
                if process.stdout is None or process.stderr is None:
                    raise OracleProcessError(
                        OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
                        "server process did not expose stdout and stderr",
                    )
                return_task = asyncio.create_task(process.wait())
                stdout_task = asyncio.create_task(self._drain_stdout(process.stdout, state, limits))
                stderr_task = asyncio.create_task(self._drain_stderr(process.stderr, state, limits))
                await self._wait_for_ready(state, stdout_task, stderr_task, return_task, limits)
        except OracleProcessError as error:
            pending_error = error
        except Exception:
            pending_error = OracleProcessError(
                OracleFailureClass.PROCESS_CRASH, "server lifecycle raised an unexpected error"
            )
        finally:
            if process is not None:
                try:
                    forced_shutdown = await self._shutdown(process, return_task, limits)
                except OracleProcessError as error:
                    pending_error = error
                for task in (stdout_task, stderr_task):
                    if task is not None and not task.done():
                        task.cancel()
                await asyncio.gather(
                    *(task for task in (stdout_task, stderr_task) if task),
                    return_exceptions=True,
                )
            if config_path is not None:
                try:
                    _remove_controlled_config(config_path, expected_config)
                except OracleProcessError as error:
                    pending_error = error
            if log_index is not None:
                try:
                    _remove_generated_log_index(log_index)
                except OracleProcessError as error:
                    pending_error = error
        if state.external_network_attempt:
            raise OracleProcessError(
                OracleFailureClass.EXTERNAL_NETWORK_ATTEMPT,
                "Node network guard denied a non-loopback operation",
            )
        if pending_error is not None:
            raise pending_error
        if not state.ready:
            raise OracleProcessError(OracleFailureClass.START_TIMEOUT, "server never became ready")
        return LoopbackServerResult(
            bind_address=config.bind_address, ready=True, forced_shutdown=forced_shutdown
        )

    @staticmethod
    async def _drain_stdout(
        stream: object, state: _ServerDrain, limits: LoopbackServerLimits
    ) -> None:
        reader = stream
        try:
            while chunk := await reader.read(DEFAULT_READ_CHUNK_BYTES):  # type: ignore[attr-defined]
                state.stdout_bytes += len(chunk)
                if state.stdout_bytes > limits.max_stdout_bytes:
                    raise OracleProcessError(
                        OracleFailureClass.OUTPUT_TOO_LARGE,
                        "server stdout exceeded the configured byte limit",
                    )
                state.activity.set()
        finally:
            state.activity.set()

    @staticmethod
    async def _drain_stderr(
        stream: object, state: _ServerDrain, limits: LoopbackServerLimits
    ) -> None:
        marker = EXTERNAL_NETWORK_MARKER.encode("ascii")
        ready_marker = LOOPBACK_LISTEN_MARKER.encode("ascii")
        reader = stream
        try:
            while chunk := await reader.read(DEFAULT_READ_CHUNK_BYTES):  # type: ignore[attr-defined]
                state.stderr_bytes += len(chunk)
                if state.stderr_bytes > limits.max_stderr_bytes:
                    raise OracleProcessError(
                        OracleFailureClass.OUTPUT_TOO_LARGE,
                        "server stderr exceeded the configured byte limit",
                    )
                state.stderr.extend(chunk)
                state.external_network_attempt = (
                    state.external_network_attempt or marker in state.stderr
                )
                state.ready = state.ready or ready_marker in state.stderr
                state.activity.set()
        finally:
            state.activity.set()

    @staticmethod
    def _raise_reader_failure(task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except OracleProcessError:
            raise
        except Exception as error:
            raise OracleProcessError(
                OracleFailureClass.PROCESS_CRASH, "server stream reader failed"
            ) from error

    def _raise_completed_reader_failures(
        self, stdout_task: asyncio.Task[None], stderr_task: asyncio.Task[None]
    ) -> None:
        if stdout_task.done():
            self._raise_reader_failure(stdout_task)
        if stderr_task.done():
            self._raise_reader_failure(stderr_task)

    async def _wait_for_ready(
        self,
        state: _ServerDrain,
        stdout_task: asyncio.Task[None],
        stderr_task: asyncio.Task[None],
        return_task: asyncio.Task[int],
        limits: LoopbackServerLimits,
    ) -> None:
        try:
            async with asyncio.timeout(limits.readiness_timeout_seconds):
                while True:
                    if state.external_network_attempt:
                        raise OracleProcessError(
                            OracleFailureClass.EXTERNAL_NETWORK_ATTEMPT,
                            "Node network guard denied a non-loopback operation",
                        )
                    if state.ready:
                        return
                    self._raise_completed_reader_failures(stdout_task, stderr_task)
                    if return_task.done():
                        returncode = return_task.result()
                        failure = (
                            OracleFailureClass.PROCESS_CRASH
                            if returncode < 0
                            else OracleFailureClass.UNEXPECTED_EXIT_CODE
                        )
                        raise OracleProcessError(failure, "server exited before readiness")
                    state.activity.clear()
                    if state.ready or state.external_network_attempt:
                        continue
                    await state.activity.wait()
        except TimeoutError as error:
            raise OracleProcessError(
                OracleFailureClass.START_TIMEOUT, "server readiness timed out"
            ) from error

    async def _shutdown(
        self,
        process: ManagedProcess,
        return_task: asyncio.Task[int] | None,
        limits: LoopbackServerLimits,
    ) -> bool:
        if return_task is None:
            raise OracleProcessError(
                OracleFailureClass.SHUTDOWN_FAILED, "server exit watcher was not created"
            )
        if process.stdin is not None:
            process.stdin.close()
            with contextlib.suppress(TimeoutError, BrokenPipeError, ConnectionError, OSError):
                await asyncio.wait_for(
                    process.stdin.wait_closed(), limits.graceful_shutdown_timeout_seconds
                )
        if await self._wait_for_exit(return_task, limits.graceful_shutdown_timeout_seconds):
            return await self._finish_orphan_check(process, return_task, limits, forced=False)
        if not await self._terminate(
            process, force=False, timeout=limits.graceful_shutdown_timeout_seconds
        ):
            raise OracleProcessError(
                OracleFailureClass.SHUTDOWN_FAILED, "server graceful termination failed"
            )
        if await self._wait_for_exit(return_task, limits.forced_shutdown_timeout_seconds):
            return await self._finish_orphan_check(process, return_task, limits, forced=False)
        if not await self._terminate(
            process, force=True, timeout=limits.forced_shutdown_timeout_seconds
        ):
            raise OracleProcessError(
                OracleFailureClass.SHUTDOWN_FAILED, "server forced termination failed"
            )
        if not await self._wait_for_exit(return_task, limits.forced_shutdown_timeout_seconds):
            raise OracleProcessError(
                OracleFailureClass.SHUTDOWN_FAILED, "server could not be reaped"
            )
        return await self._finish_orphan_check(process, return_task, limits, forced=True)

    @staticmethod
    async def _wait_for_exit(return_task: asyncio.Task[int], timeout: float) -> bool:
        try:
            await asyncio.wait_for(asyncio.shield(return_task), timeout)
        except TimeoutError:
            return False
        return True

    async def _terminate(self, process: ManagedProcess, *, force: bool, timeout: float) -> bool:
        try:
            if self._terminator is None:
                await asyncio.wait_for(_default_terminate(process, force=force), timeout)
            else:
                await asyncio.wait_for(self._terminator(process, force=force), timeout)
        except Exception:
            return False
        return True

    async def _finish_orphan_check(
        self,
        process: ManagedProcess,
        return_task: asyncio.Task[int],
        limits: LoopbackServerLimits,
        *,
        forced: bool,
    ) -> bool:
        try:
            orphaned = await asyncio.wait_for(
                self._orphan_verifier(process), limits.forced_shutdown_timeout_seconds
            )
        except Exception as error:
            raise OracleProcessError(
                OracleFailureClass.SHUTDOWN_FAILED, "server orphan check failed"
            ) from error
        if orphaned:
            if not await self._terminate(
                process, force=True, timeout=limits.forced_shutdown_timeout_seconds
            ) or not await self._wait_for_exit(return_task, limits.forced_shutdown_timeout_seconds):
                raise OracleProcessError(
                    OracleFailureClass.SHUTDOWN_FAILED, "server orphan cleanup failed"
                )
            try:
                orphaned = await asyncio.wait_for(
                    self._orphan_verifier(process), limits.forced_shutdown_timeout_seconds
                )
            except Exception as error:
                raise OracleProcessError(
                    OracleFailureClass.SHUTDOWN_FAILED, "server final orphan check failed"
                ) from error
            if orphaned:
                raise OracleProcessError(
                    OracleFailureClass.ORPHANED_CHILD_PROCESS,
                    "server left a child process behind",
                )
            forced = True
        job = _job_for(process)
        if job is not None:
            try:
                job.close()
            except Exception as error:
                raise OracleProcessError(
                    OracleFailureClass.SHUTDOWN_FAILED, "server Job Object cleanup failed"
                ) from error
        return forced


__all__ = [
    "LoopbackServerConfig",
    "LoopbackServerLimits",
    "LoopbackServerResult",
    "LoopbackServerSmoke",
]
