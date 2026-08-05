"""Injected, bounded lifecycle runner for one Showdown simulator process.

The runner deliberately knows nothing about fixtures, files, or the public
runtime.  It owns only a single stdio child process and preserves the strict
message semantics provided by :mod:`battlebelief_lab.oracle.showdown.protocol`.
"""

from __future__ import annotations

import asyncio
import contextlib
import ctypes
import getpass
import os
import re
import signal
import socket
import subprocess
from collections.abc import Awaitable, Callable, Mapping
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol, cast

from battlebelief_lab.oracle.showdown.errors import OracleFailureClass
from battlebelief_lab.oracle.showdown.network import classify_network_marker
from battlebelief_lab.oracle.showdown.protocol import (
    EndMessage,
    OracleProtocolError,
    PlayerSide,
    ProtocolMessage,
    ShowdownProtocolDecoder,
    SideErrorMessage,
    SideUpdateMessage,
)

DEFAULT_READ_CHUNK_BYTES = 64 * 1024
_JOB_SETUP_REAP_TIMEOUT_SECONDS = 5.0
_CREATE_SUSPENDED = 0x00000004
_TH32CS_SNAPTHREAD = 0x00000004
_THREAD_SUSPEND_RESUME = 0x0002
_INVALID_DWORD = 0xFFFFFFFF


class _Readable(Protocol):
    async def read(self, size: int = -1) -> bytes: ...


class _Writable(Protocol):
    def write(self, data: bytes) -> None: ...

    async def drain(self) -> None: ...

    def close(self) -> None: ...

    async def wait_closed(self) -> None: ...


class ManagedProcess(Protocol):
    """Minimal async child-process surface, intentionally easy to fake."""

    @property
    def stdin(self) -> _Writable | None: ...

    @property
    def stdout(self) -> _Readable | None: ...

    @property
    def stderr(self) -> _Readable | None: ...

    @property
    def returncode(self) -> int | None: ...

    async def wait(self) -> int: ...


type ProcessLauncher = Callable[
    [tuple[str, ...], Path, Mapping[str, str], bool], Awaitable[ManagedProcess]
]
type ProcessTerminator = Callable[..., Awaitable[None]]
type OrphanVerifier = Callable[[ManagedProcess], Awaitable[bool]]


class _WindowsJob(Protocol):
    def active_process_count(self) -> int: ...

    def terminate(self) -> None: ...

    def close(self) -> None: ...


class _WindowsJobError(RuntimeError):
    """Native Job Object setup or cleanup failed; raw system detail is omitted."""

    def __init__(self, message: str, *, cleanup_failed: bool = False) -> None:
        self.cleanup_failed = cleanup_failed
        super().__init__(message)


class _WindowsBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("per_process_user_time_limit", ctypes.c_longlong),
        ("per_job_user_time_limit", ctypes.c_longlong),
        ("limit_flags", wintypes.DWORD),
        ("minimum_working_set_size", ctypes.c_size_t),
        ("maximum_working_set_size", ctypes.c_size_t),
        ("active_process_limit", wintypes.DWORD),
        ("affinity", ctypes.c_size_t),
        ("priority_class", wintypes.DWORD),
        ("scheduling_class", wintypes.DWORD),
    ]


class _WindowsIoCounters(ctypes.Structure):
    _fields_ = [
        ("read_operation_count", ctypes.c_ulonglong),
        ("write_operation_count", ctypes.c_ulonglong),
        ("other_operation_count", ctypes.c_ulonglong),
        ("read_transfer_count", ctypes.c_ulonglong),
        ("write_transfer_count", ctypes.c_ulonglong),
        ("other_transfer_count", ctypes.c_ulonglong),
    ]


class _WindowsExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("basic_limit_information", _WindowsBasicLimitInformation),
        ("io_info", _WindowsIoCounters),
        ("process_memory_limit", ctypes.c_size_t),
        ("job_memory_limit", ctypes.c_size_t),
        ("peak_process_memory_used", ctypes.c_size_t),
        ("peak_job_memory_used", ctypes.c_size_t),
    ]


class _WindowsBasicAccountingInformation(ctypes.Structure):
    _fields_ = [
        ("total_user_time", ctypes.c_longlong),
        ("total_kernel_time", ctypes.c_longlong),
        ("this_period_total_user_time", ctypes.c_longlong),
        ("this_period_total_kernel_time", ctypes.c_longlong),
        ("total_page_fault_count", wintypes.DWORD),
        ("total_processes", wintypes.DWORD),
        ("active_processes", wintypes.DWORD),
        ("total_terminated_processes", wintypes.DWORD),
    ]


class _WindowsThreadEntry32(ctypes.Structure):
    _fields_ = [
        ("dw_size", wintypes.DWORD),
        ("cnt_usage", wintypes.DWORD),
        ("thread_id", wintypes.DWORD),
        ("owner_process_id", wintypes.DWORD),
        ("base_priority", ctypes.c_long),
        ("delta_priority", ctypes.c_long),
        ("flags", wintypes.DWORD),
    ]


@dataclass(slots=True)
class _JobBoundProcess:
    """Internal wrapper that retains the Windows Job Object through cleanup."""

    process: ManagedProcess
    job: _WindowsJob

    @property
    def stdin(self) -> _Writable | None:
        return self.process.stdin

    @property
    def stdout(self) -> _Readable | None:
        return self.process.stdout

    @property
    def stderr(self) -> _Readable | None:
        return self.process.stderr

    @property
    def returncode(self) -> int | None:
        return self.process.returncode

    async def wait(self) -> int:
        return await self.process.wait()


class _NativeWindowsJob:
    """Kill-on-close Job Object bound by PID without asyncio private handles."""

    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    _JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION = 1
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    _PROCESS_SET_QUOTA = 0x0100
    _PROCESS_TERMINATE = 0x0001

    def __init__(self, handle: int) -> None:
        self._handle = handle

    @classmethod
    def create_and_assign(cls, pid: int) -> _NativeWindowsJob:
        if os.name != "nt":
            raise _WindowsJobError("Windows Job Object is unavailable")
        kernel32 = cls._kernel32()
        job_handle = kernel32.CreateJobObjectW(None, None)
        if not job_handle:
            raise _WindowsJobError("could not create Windows Job Object")
        job = cls(int(job_handle))
        process_handle = 0
        try:
            limits = _WindowsExtendedLimitInformation()
            limits.basic_limit_information.limit_flags = cls._JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not kernel32.SetInformationJobObject(
                job._handle,
                cls._JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(limits),
                ctypes.sizeof(limits),
            ):
                raise _WindowsJobError("could not configure Windows Job Object")
            process_handle = kernel32.OpenProcess(
                cls._PROCESS_SET_QUOTA | cls._PROCESS_TERMINATE, False, pid
            )
            if not process_handle:
                raise _WindowsJobError("could not open child for Windows Job assignment")
            if not kernel32.AssignProcessToJobObject(job._handle, process_handle):
                raise _WindowsJobError("could not assign child to Windows Job Object")
        except BaseException:
            job.close()
            raise
        finally:
            if process_handle:
                kernel32.CloseHandle(process_handle)
        return job

    @classmethod
    def _kernel32(cls) -> Any:
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.LPVOID,
        ]
        kernel32.QueryInformationJobObject.restype = wintypes.BOOL
        kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.TerminateJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        return kernel32

    def active_process_count(self) -> int:
        kernel32 = self._kernel32()
        info = _WindowsBasicAccountingInformation()
        if not kernel32.QueryInformationJobObject(
            self._handle,
            self._JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION,
            ctypes.byref(info),
            ctypes.sizeof(info),
            None,
        ):
            raise _WindowsJobError("could not query Windows Job Object")
        return int(info.active_processes)

    def terminate(self) -> None:
        if self._handle and not self._kernel32().TerminateJobObject(self._handle, 1):
            raise _WindowsJobError("could not terminate Windows Job Object")

    def close(self) -> None:
        if self._handle:
            handle = self._handle
            if not self._kernel32().CloseHandle(handle):
                raise _WindowsJobError("could not close Windows Job Object")
            self._handle = 0


class OracleProcessError(RuntimeError):
    """Stable failure class with a bounded, evidence-safe diagnostic."""

    def __init__(self, failure_class: OracleFailureClass, diagnostic: str) -> None:
        self.failure_class = failure_class
        self.diagnostic = diagnostic
        super().__init__(f"{failure_class.value}: {diagnostic}")


@dataclass(frozen=True, slots=True)
class ProcessResponseBarrier:
    """The exact response condition that unlocks the next write batch."""

    request_sides: frozenset[PlayerSide] = frozenset()
    end: bool = False

    def __post_init__(self) -> None:
        if not self.request_sides and not self.end:
            raise ValueError("a process response barrier must require a response")

    def is_satisfied_by(self, messages: tuple[ProtocolMessage, ...]) -> bool:
        observed_sides = frozenset(
            message.side for message in messages if isinstance(message, SideUpdateMessage)
        )
        observed_end = any(isinstance(message, EndMessage) for message in messages)
        return self.request_sides.issubset(observed_sides) and (not self.end or observed_end)


@dataclass(frozen=True, slots=True)
class ProcessInteractionStep:
    """One immutable input batch followed by one required response barrier."""

    input_bytes: bytes
    barrier: ProcessResponseBarrier

    def __post_init__(self) -> None:
        if type(self.input_bytes) is not bytes:
            raise TypeError("a process interaction batch must be bytes")
        if not self.input_bytes or not self.input_bytes.endswith(b"\n"):
            raise ValueError("a process interaction batch must be non-empty and newline terminated")


@dataclass(frozen=True, slots=True)
class ShowdownProcessLimits:
    """Operational limits; none enter a canonical oracle result."""

    start_timeout_seconds: float
    write_timeout_seconds: float
    response_timeout_seconds: float
    fixture_timeout_seconds: float
    graceful_shutdown_timeout_seconds: float
    forced_shutdown_timeout_seconds: float
    max_stdout_bytes: int
    max_messages: int
    max_input_bytes: int
    max_stderr_bytes: int

    def __post_init__(self) -> None:
        timeout_values = (
            self.start_timeout_seconds,
            self.write_timeout_seconds,
            self.response_timeout_seconds,
            self.fixture_timeout_seconds,
            self.graceful_shutdown_timeout_seconds,
            self.forced_shutdown_timeout_seconds,
        )
        if any(value <= 0 for value in timeout_values):
            raise ValueError("all process time limits must be positive")
        if (
            self.max_stdout_bytes <= 0
            or self.max_messages <= 0
            or self.max_input_bytes <= 0
            or self.max_stderr_bytes <= 0
        ):
            raise ValueError("all process size limits must be positive")


@dataclass(frozen=True, slots=True)
class ShowdownProcessSpec:
    """Explicit argv, cwd, environment and staged protocol interaction."""

    argv: tuple[str, ...]
    cwd: Path
    env: Mapping[str, str]
    steps: tuple[ProcessInteractionStep, ...]

    def __post_init__(self) -> None:
        if not self.argv or any(not value for value in self.argv):
            raise ValueError("process argv must contain non-empty arguments")
        if not self.steps:
            raise ValueError("a Showdown process requires at least one interaction step")
        if any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in self.env.items()
        ):
            raise TypeError("process environment keys and values must be strings")
        object.__setattr__(self, "env", MappingProxyType(dict(self.env)))


@dataclass(frozen=True, slots=True)
class OracleProcessResult:
    """Non-canonical process result; diagnostics never become public evidence."""

    messages: tuple[ProtocolMessage, ...]
    returncode: int
    sanitized_stderr: str
    forced_shutdown: bool
    completed_barriers: bool
    terminal_side_error: SideErrorMessage | None


@dataclass(slots=True)
class _DrainState:
    messages: list[ProtocolMessage] = field(default_factory=list)
    stdout_bytes: int = 0
    stderr_bytes: int = 0
    stderr: bytearray = field(default_factory=bytearray)
    activity: asyncio.Event = field(default_factory=asyncio.Event)


def sanitize_stderr(raw: bytes, *, max_bytes: int) -> str:
    """Return bounded stderr with values and local identities removed."""

    if max_bytes <= 0:
        raise ValueError("stderr limit must be positive")
    text = raw.decode("utf-8", errors="replace").replace("\x00", "")
    text = re.sub(r"(?im)^\s*(authorization|cookie)\s*:\s*[^\r\n]*", r"\1: <redacted>", text)
    text = re.sub(
        r"(?i)\b(token|password|api[_-]?key|authorization|cookie|secret)\s*[:=]\s*"
        r"(?:\"[^\"]*\"|'[^']*'|[^,;\r\n]+)",
        r"\1=<redacted>",
        text,
    )
    text = re.sub(r"(?i)\b(hostname|host|user(?:name)?)\s*[:=]\s*[^\s]+", r"\1=<redacted>", text)
    for local_identity in (getpass.getuser(), socket.gethostname()):
        if local_identity:
            text = re.sub(re.escape(local_identity), "<redacted>", text, flags=re.IGNORECASE)
    text = re.sub(r"(?i)(?:[a-z]:[\\/]|\\\\)[^\r\n]*", "<path>", text)
    text = re.sub(r"(?<![A-Za-z0-9._-])/[^\r\n]*", "<path>", text)
    text = re.sub(
        r"\b(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})(?:\.(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})){3}\b",
        "<ip>",
        text,
    )
    text = re.sub(r"(?i)\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", "<host>", text)
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    suffix = "...[truncated]"
    if max_bytes <= len(suffix.encode("utf-8")):
        return suffix.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
    permitted = max_bytes - len(suffix.encode("utf-8"))
    truncated = encoded[:permitted].decode("utf-8", errors="ignore")
    return truncated + suffix


async def _default_launcher(
    argv: tuple[str, ...], cwd: Path, env: Mapping[str, str], new_process_group: bool
) -> ManagedProcess:
    """Start through exec only; shells are deliberately not involved."""

    kwargs: dict[str, object] = {
        "cwd": str(cwd),
        "env": dict(env),
        "stdin": asyncio.subprocess.PIPE,
        "stdout": asyncio.subprocess.PIPE,
        "stderr": asyncio.subprocess.PIPE,
    }
    if os.name == "nt":
        del new_process_group
        kwargs["creationflags"] = _windows_creation_flags()
    elif new_process_group:
        kwargs["start_new_session"] = True
    child = await asyncio.create_subprocess_exec(*argv, **kwargs)  # type: ignore[arg-type]
    if os.name != "nt":
        return cast(ManagedProcess, child)
    job: _WindowsJob | None = None
    try:
        if child.pid is None:
            raise _WindowsJobError("Windows child process did not expose a PID")
        job = _NativeWindowsJob.create_and_assign(child.pid)
        _resume_suspended_windows_threads(child.pid)
        return _JobBoundProcess(child, job)
    except BaseException:
        cleanup_succeeded = await _reap_windows_setup_failure(child, job)
        if not cleanup_succeeded:
            raise _WindowsJobError(
                "Windows Job setup cleanup could not be proven", cleanup_failed=True
            ) from None
        raise


def _windows_creation_flags() -> int:
    """Contain the child before its first instruction can execute."""

    return subprocess.CREATE_NEW_PROCESS_GROUP | _CREATE_SUSPENDED


def _resume_suspended_windows_threads(pid: int) -> None:
    """Resume every suspended thread exactly once after Job assignment."""

    if os.name != "nt":
        raise _WindowsJobError("Windows thread snapshot is unavailable")
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Thread32First.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
    kernel32.Thread32First.restype = wintypes.BOOL
    kernel32.Thread32Next.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
    kernel32.Thread32Next.restype = wintypes.BOOL
    kernel32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenThread.restype = wintypes.HANDLE
    kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel32.ResumeThread.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    snapshot = kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPTHREAD, 0)
    invalid_handle = ctypes.c_void_p(-1).value
    if snapshot in (0, invalid_handle):
        raise _WindowsJobError("could not snapshot suspended Windows child threads")
    thread_ids: list[int] = []
    entry = _WindowsThreadEntry32()
    entry.dw_size = ctypes.sizeof(_WindowsThreadEntry32)
    try:
        has_entry = kernel32.Thread32First(snapshot, ctypes.byref(entry))
        while has_entry:
            if entry.owner_process_id == pid:
                thread_ids.append(int(entry.thread_id))
            entry.dw_size = ctypes.sizeof(_WindowsThreadEntry32)
            has_entry = kernel32.Thread32Next(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    if not thread_ids:
        raise _WindowsJobError("could not find a suspended Windows child thread")
    for thread_id in sorted(set(thread_ids)):
        thread_handle = kernel32.OpenThread(_THREAD_SUSPEND_RESUME, False, thread_id)
        if not thread_handle:
            raise _WindowsJobError("could not open a suspended Windows child thread")
        try:
            previous_suspend_count = int(kernel32.ResumeThread(thread_handle))
        finally:
            kernel32.CloseHandle(thread_handle)
        if previous_suspend_count != 1:
            raise _WindowsJobError("Windows child thread had an unexpected suspend count")


def _job_for(process: ManagedProcess) -> _WindowsJob | None:
    return process.job if isinstance(process, _JobBoundProcess) else None


def _native_process_for(process: ManagedProcess) -> asyncio.subprocess.Process | None:
    candidate = process.process if isinstance(process, _JobBoundProcess) else process
    return candidate if isinstance(candidate, asyncio.subprocess.Process) else None


async def _default_terminate(process: ManagedProcess, *, force: bool) -> None:
    """Terminate the owned POSIX group or Windows child-process tree."""

    job = _job_for(process)
    if os.name == "nt" and job is not None and force:
        job.terminate()
        return
    concrete = _native_process_for(process)
    if concrete is None:
        return
    kill_process_group = getattr(os, "killpg", None)
    if os.name != "nt" and concrete.pid is not None and callable(kill_process_group):
        try:
            kill_process_group(concrete.pid, 9 if force else 15)
            return
        except ProcessLookupError:
            return
    if os.name == "nt" and concrete.pid is not None:
        if not force:
            control_break = getattr(signal, "CTRL_BREAK_EVENT", None)
            if control_break is not None:
                with contextlib.suppress(ProcessLookupError, OSError):
                    concrete.send_signal(control_break)
            return
        taskkill = await asyncio.create_subprocess_exec(
            "taskkill",
            "/PID",
            str(concrete.pid),
            "/T",
            "/F",
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            await taskkill.wait()
        except BaseException:
            if taskkill.returncode is None:
                taskkill.kill()
                with contextlib.suppress(Exception):
                    await asyncio.shield(taskkill.wait())
            raise
        return
    if force:
        concrete.kill()
    else:
        concrete.terminate()


async def _reap_windows_setup_failure(child: ManagedProcess, job: _WindowsJob | None) -> bool:
    """Kill, reap, prove empty, then close every partially provisioned boundary."""

    cleanup_succeeded = True
    if job is not None:
        try:
            job.terminate()
        except Exception:
            cleanup_succeeded = False
    else:
        native_child = _native_process_for(child)
        if native_child is None:
            return False
        try:
            native_child.kill()
        except (ProcessLookupError, OSError):
            cleanup_succeeded = False
    try:
        await asyncio.wait_for(child.wait(), _JOB_SETUP_REAP_TIMEOUT_SECONDS)
    except Exception:
        cleanup_succeeded = False
    if job is not None:
        try:
            job_empty = await _wait_for_windows_job_empty(job, _JOB_SETUP_REAP_TIMEOUT_SECONDS)
            cleanup_succeeded = cleanup_succeeded and job_empty
        except Exception:
            cleanup_succeeded = False
        try:
            job.close()
        except Exception:
            cleanup_succeeded = False
    return cleanup_succeeded


async def _wait_for_windows_job_empty(job: _WindowsJob, timeout_seconds: float) -> bool:
    """Bounded setup-time polling; a terminated job must report no active process."""

    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while True:
        if job.active_process_count() == 0:
            return True
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return False
        await asyncio.sleep(min(0.01, remaining))


async def _default_orphan_verifier(process: ManagedProcess) -> bool:
    """Check for surviving children after the owned parent has exited.

    On POSIX the fresh session is the authoritative process-tree containment
    boundary. On Windows ``taskkill /T`` supplies tree removal and the native
    Toolhelp snapshot is resolved recursively through creator parent links.
    """

    job = _job_for(process)
    if job is not None:
        return job.active_process_count() > 0
    concrete = _native_process_for(process)
    if concrete is None or concrete.pid is None:
        return False
    if os.name != "nt":
        kill_process_group = getattr(os, "killpg", None)
        if not callable(kill_process_group):
            return False
        try:
            kill_process_group(concrete.pid, 0)
        except ProcessLookupError:
            return False
        return True
    return _windows_has_descendant(concrete.pid)


def _has_recursive_descendant(parent_pid: int, parent_by_pid: Mapping[int, int]) -> bool:
    """Return whether any creator-link descendant belongs to ``parent_pid``."""

    frontier = [parent_pid]
    seen = {parent_pid}
    descendants: set[int] = set()
    while frontier:
        ancestor = frontier.pop()
        for child_pid, creator_pid in parent_by_pid.items():
            if creator_pid != ancestor or child_pid in seen:
                continue
            seen.add(child_pid)
            descendants.add(child_pid)
            frontier.append(child_pid)
    return bool(descendants)


def _windows_has_descendant(parent_pid: int) -> bool:
    """Use Toolhelp32 instead of a shell or locale-dependent task listing."""

    if os.name != "nt":
        return False

    class _ProcessEntry32(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.c_ulong),
            ("cntUsage", ctypes.c_ulong),
            ("th32ProcessID", ctypes.c_ulong),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", ctypes.c_ulong),
            ("cntThreads", ctypes.c_ulong),
            ("th32ParentProcessID", ctypes.c_ulong),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", ctypes.c_ulong),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    kernel32 = ctypes.windll.kernel32
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    invalid_handle_value = ctypes.c_void_p(-1).value
    if snapshot in (0, invalid_handle_value):
        return True
    entry = _ProcessEntry32()
    entry.dwSize = ctypes.sizeof(_ProcessEntry32)
    parent_by_pid: dict[int, int] = {}
    try:
        has_entry = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while has_entry:
            parent_by_pid[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
            has_entry = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return _has_recursive_descendant(parent_pid, parent_by_pid)


class ShowdownProcessRunner:
    """Run exactly one stdio child with strict staged interaction and cleanup."""

    def __init__(
        self,
        *,
        launcher: ProcessLauncher = _default_launcher,
        terminator: ProcessTerminator | None = None,
        orphan_verifier: OrphanVerifier = _default_orphan_verifier,
    ) -> None:
        self._launcher = launcher
        self._orphan_verifier = orphan_verifier
        self._terminator = terminator

    async def run(
        self, spec: ShowdownProcessSpec, limits: ShowdownProcessLimits
    ) -> OracleProcessResult:
        """Execute all batches, closing stdin only after the final response barrier."""

        process: ManagedProcess | None = None
        return_task: asyncio.Task[int] | None = None
        stdout_task: asyncio.Task[None] | None = None
        stderr_task: asyncio.Task[None] | None = None
        state = _DrainState()
        forced_shutdown = False
        pending_error: OracleProcessError | None = None
        completed_barriers = True
        terminal_side_error: SideErrorMessage | None = None
        try:
            if sum(len(step.input_bytes) for step in spec.steps) > limits.max_input_bytes:
                raise OracleProcessError(
                    OracleFailureClass.INPUT_TOO_LARGE,
                    "process input exceeds the configured byte limit",
                )
            try:
                process = await asyncio.wait_for(
                    self._launcher(spec.argv, spec.cwd, spec.env, True),
                    timeout=limits.start_timeout_seconds,
                )
            except _WindowsJobError as exc:
                failure_class = (
                    OracleFailureClass.SHUTDOWN_FAILED
                    if exc.cleanup_failed
                    else OracleFailureClass.PROCESS_CRASH
                )
                raise OracleProcessError(
                    failure_class, "Windows Job process containment failed"
                ) from exc
            except FileNotFoundError as exc:
                raise OracleProcessError(
                    OracleFailureClass.NODE_NOT_FOUND, "node executable not found"
                ) from exc
            except TimeoutError as exc:
                raise OracleProcessError(
                    OracleFailureClass.START_TIMEOUT, "process start timed out"
                ) from exc
            return_task = asyncio.create_task(self._wait_for_exit(process, state))
            if process.stdin is None or process.stdout is None or process.stderr is None:
                raise OracleProcessError(
                    OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
                    "child process did not expose all stdio streams",
                )
            stdout_task = asyncio.create_task(self._drain_stdout(process.stdout, state, limits))
            stderr_task = asyncio.create_task(self._drain_stderr(process.stderr, state, limits))
            try:
                async with asyncio.timeout(limits.fixture_timeout_seconds):
                    for step in spec.steps:
                        message_start_index = len(state.messages)
                        await self._write(process.stdin, step.input_bytes, limits)
                        terminal_side_error = await self._wait_for_barrier(
                            step.barrier,
                            state,
                            message_start_index,
                            stdout_task,
                            stderr_task,
                            return_task,
                            limits,
                        )
                        if terminal_side_error is not None:
                            completed_barriers = False
                            break
            except TimeoutError as exc:
                raise OracleProcessError(
                    OracleFailureClass.FIXTURE_TIMEOUT, "fixture timed out"
                ) from exc
        except OracleProcessError as exc:
            pending_error = exc
        except Exception:
            pending_error = OracleProcessError(
                OracleFailureClass.PROCESS_CRASH, "process lifecycle raised an unexpected error"
            )
        finally:
            if process is not None:
                try:
                    forced_shutdown = await self._shutdown(process, return_task, limits)
                except OracleProcessError as shutdown_error:
                    if (
                        pending_error is None
                        or shutdown_error.failure_class is OracleFailureClass.SHUTDOWN_FAILED
                    ):
                        pending_error = shutdown_error
                except Exception:
                    pending_error = OracleProcessError(
                        OracleFailureClass.SHUTDOWN_FAILED,
                        "process shutdown raised an unexpected error",
                    )
                should_require_clean_drain = pending_error is None and terminal_side_error is None
                if not should_require_clean_drain:
                    for task in (stdout_task, stderr_task):
                        if task is not None and not task.done():
                            task.cancel()
                    await asyncio.gather(
                        *(task for task in (stdout_task, stderr_task) if task),
                        return_exceptions=True,
                    )
                else:
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(
                                *(task for task in (stdout_task, stderr_task) if task),
                                return_exceptions=True,
                            ),
                            timeout=limits.forced_shutdown_timeout_seconds,
                        )
                    except TimeoutError:
                        for task in (stdout_task, stderr_task):
                            if task is not None and not task.done():
                                task.cancel()
                        await asyncio.gather(
                            *(task for task in (stdout_task, stderr_task) if task),
                            return_exceptions=True,
                        )
                        pending_error = OracleProcessError(
                            OracleFailureClass.SHUTDOWN_FAILED,
                            "process streams did not close after process shutdown",
                        )
                if (
                    pending_error is None
                    and terminal_side_error is None
                    and stdout_task is not None
                    and stderr_task is not None
                ):
                    self._raise_drain_failure(stdout_task, stream_name="stdout")
                    self._raise_drain_failure(stderr_task, stream_name="stderr")
        if classify_network_marker(state.stderr) is OracleFailureClass.EXTERNAL_NETWORK_ATTEMPT:
            raise OracleProcessError(
                OracleFailureClass.EXTERNAL_NETWORK_ATTEMPT,
                "Node network guard denied a non-loopback operation",
            )
        if pending_error is not None:
            if process is not None and return_task is not None:
                pending_error = self._prefer_independent_exit_failure(
                    pending_error, return_task, forced_shutdown
                )
            raise pending_error
        if process is None or return_task is None:
            raise AssertionError("process start path returned without a process")
        returncode = process.returncode
        if returncode is None:
            returncode = await return_task
        if returncode < 0 and not forced_shutdown:
            raise OracleProcessError(
                OracleFailureClass.PROCESS_CRASH, "process terminated by signal"
            )
        if returncode > 0 and not forced_shutdown:
            raise OracleProcessError(
                OracleFailureClass.UNEXPECTED_EXIT_CODE, "process exited non-zero"
            )
        return OracleProcessResult(
            messages=tuple(state.messages),
            returncode=returncode,
            sanitized_stderr=sanitize_stderr(
                bytes(state.stderr), max_bytes=limits.max_stderr_bytes
            ),
            forced_shutdown=forced_shutdown,
            completed_barriers=completed_barriers,
            terminal_side_error=terminal_side_error,
        )

    @staticmethod
    def _prefer_independent_exit_failure(
        pending_error: OracleProcessError,
        return_task: asyncio.Task[int],
        forced_shutdown: bool,
    ) -> OracleProcessError:
        """Keep a real child crash from being hidden by its incomplete stdout."""

        generic_output_failures = frozenset(
            {
                OracleFailureClass.MALFORMED_OUTPUT,
                OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
            }
        )
        protected_failures = frozenset(
            {
                OracleFailureClass.OUTPUT_TOO_LARGE,
                OracleFailureClass.EXTERNAL_NETWORK_ATTEMPT,
            }
        )
        if (
            forced_shutdown
            or pending_error.failure_class not in generic_output_failures
            or pending_error.failure_class in protected_failures
            or not return_task.done()
        ):
            return pending_error
        try:
            returncode = return_task.result()
        except Exception:
            return pending_error
        if returncode < 0:
            return OracleProcessError(
                OracleFailureClass.PROCESS_CRASH,
                "process terminated by signal before its required response",
            )
        if returncode > 0:
            return OracleProcessError(
                OracleFailureClass.UNEXPECTED_EXIT_CODE,
                "process exited non-zero before its required response",
            )
        return pending_error

    async def _write(self, writer: _Writable, data: bytes, limits: ShowdownProcessLimits) -> None:
        try:
            writer.write(data)
            await asyncio.wait_for(writer.drain(), timeout=limits.write_timeout_seconds)
        except TimeoutError as exc:
            raise OracleProcessError(
                OracleFailureClass.WRITE_TIMEOUT, "process stdin write timed out"
            ) from exc
        except (BrokenPipeError, ConnectionError, OSError) as exc:
            raise OracleProcessError(
                OracleFailureClass.PROCESS_CRASH, "process stdin became unavailable"
            ) from exc

    @staticmethod
    async def _wait_for_exit(process: ManagedProcess, state: _DrainState) -> int:
        try:
            return await process.wait()
        finally:
            state.activity.set()

    async def _wait_for_barrier(
        self,
        barrier: ProcessResponseBarrier,
        state: _DrainState,
        message_start_index: int,
        stdout_task: asyncio.Task[None],
        stderr_task: asyncio.Task[None],
        return_task: asyncio.Task[int],
        limits: ShowdownProcessLimits,
    ) -> SideErrorMessage | None:
        try:
            async with asyncio.timeout(limits.response_timeout_seconds):
                while True:
                    self._raise_completed_drain_failures(stdout_task, stderr_task)
                    if barrier.is_satisfied_by(tuple(state.messages[message_start_index:])):
                        return None
                    side_error = next(
                        (
                            message
                            for message in state.messages[message_start_index:]
                            if isinstance(message, SideErrorMessage)
                        ),
                        None,
                    )
                    if side_error is not None:
                        return side_error
                    if return_task.done():
                        returncode = return_task.result()
                        if returncode < 0:
                            raise OracleProcessError(
                                OracleFailureClass.PROCESS_CRASH,
                                "process exited before its required response",
                            )
                        if returncode > 0:
                            raise OracleProcessError(
                                OracleFailureClass.UNEXPECTED_EXIT_CODE,
                                "process exited before its required response",
                            )
                    if stdout_task.done():
                        self._raise_drain_failure(stdout_task, stream_name="stdout")
                        raise OracleProcessError(
                            OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
                            "process output ended before its required response",
                        )
                    state.activity.clear()
                    self._raise_completed_drain_failures(stdout_task, stderr_task)
                    if barrier.is_satisfied_by(tuple(state.messages[message_start_index:])):
                        return None
                    if state.activity.is_set():
                        continue
                    await state.activity.wait()
        except TimeoutError as exc:
            raise OracleProcessError(
                OracleFailureClass.RESPONSE_TIMEOUT, "process response timed out"
            ) from exc

    @staticmethod
    def _raise_completed_drain_failures(
        stdout_task: asyncio.Task[None], stderr_task: asyncio.Task[None]
    ) -> None:
        if stdout_task.done():
            ShowdownProcessRunner._raise_drain_failure(stdout_task, stream_name="stdout")
        if stderr_task.done():
            ShowdownProcessRunner._raise_drain_failure(stderr_task, stream_name="stderr")

    @staticmethod
    def _raise_drain_failure(task: asyncio.Task[None], *, stream_name: str) -> None:
        try:
            task.result()
        except OracleProcessError:
            raise
        except OracleProtocolError as exc:
            raise OracleProcessError(
                exc.failure_class, "simulator output violated the protocol"
            ) from exc
        except Exception as exc:
            raise OracleProcessError(
                OracleFailureClass.PROCESS_CRASH, f"process {stream_name} reader failed"
            ) from exc

    @staticmethod
    async def _drain_stdout(
        stream: _Readable, state: _DrainState, limits: ShowdownProcessLimits
    ) -> None:
        decoder = ShowdownProtocolDecoder(max_buffer_bytes=limits.max_stdout_bytes)
        try:
            while chunk := await stream.read(DEFAULT_READ_CHUNK_BYTES):
                state.stdout_bytes += len(chunk)
                if state.stdout_bytes > limits.max_stdout_bytes:
                    raise OracleProcessError(
                        OracleFailureClass.OUTPUT_TOO_LARGE,
                        "process stdout exceeded the configured byte limit",
                    )
                try:
                    messages = decoder.feed(chunk)
                except OracleProtocolError as exc:
                    raise OracleProcessError(
                        exc.failure_class, "simulator output violated the protocol"
                    ) from exc
                state.messages.extend(messages)
                if len(state.messages) > limits.max_messages:
                    raise OracleProcessError(
                        OracleFailureClass.OUTPUT_TOO_LARGE,
                        "process emitted too many protocol messages",
                    )
                state.activity.set()
            try:
                decoder.finish()
            except OracleProtocolError as exc:
                raise OracleProcessError(
                    exc.failure_class, "simulator output ended outside the protocol"
                ) from exc
        finally:
            state.activity.set()

    @staticmethod
    async def _drain_stderr(
        stream: _Readable, state: _DrainState, limits: ShowdownProcessLimits
    ) -> None:
        try:
            while chunk := await stream.read(DEFAULT_READ_CHUNK_BYTES):
                state.stderr_bytes += len(chunk)
                if state.stderr_bytes > limits.max_stderr_bytes:
                    raise OracleProcessError(
                        OracleFailureClass.OUTPUT_TOO_LARGE,
                        "process stderr exceeded the configured byte limit",
                    )
                state.stderr.extend(chunk)
        finally:
            state.activity.set()

    async def _shutdown(
        self,
        process: ManagedProcess,
        return_task: asyncio.Task[int] | None,
        limits: ShowdownProcessLimits,
    ) -> bool:
        if process.stdin is not None:
            process.stdin.close()
            with contextlib.suppress(TimeoutError, BrokenPipeError, ConnectionError, OSError):
                await asyncio.wait_for(
                    process.stdin.wait_closed(), timeout=limits.graceful_shutdown_timeout_seconds
                )
        if return_task is None:
            raise OracleProcessError(
                OracleFailureClass.SHUTDOWN_FAILED, "process exit watcher was not created"
            )
        if await self._wait_for_exit_with_deadline(
            return_task, limits.graceful_shutdown_timeout_seconds
        ):
            return await self._finish_orphan_check(
                process, return_task, limits, cleanup_failed=False, forced=False
            )

        cleanup_failed = not await self._terminate_with_deadline(
            process, force=False, timeout_seconds=limits.graceful_shutdown_timeout_seconds
        )
        exited = False
        if not cleanup_failed:
            exited = await self._wait_for_exit_with_deadline(
                return_task, limits.forced_shutdown_timeout_seconds
            )
        if not exited:
            force_succeeded = await self._terminate_with_deadline(
                process, force=True, timeout_seconds=limits.forced_shutdown_timeout_seconds
            )
            cleanup_failed = cleanup_failed or not force_succeeded
            exited = await self._wait_for_exit_with_deadline(
                return_task, limits.forced_shutdown_timeout_seconds
            )
            cleanup_failed = cleanup_failed or not exited
        return await self._finish_orphan_check(
            process, return_task, limits, cleanup_failed=cleanup_failed, forced=True
        )

    @staticmethod
    async def _wait_for_exit_with_deadline(
        return_task: asyncio.Task[int], timeout_seconds: float
    ) -> bool:
        try:
            await asyncio.wait_for(asyncio.shield(return_task), timeout_seconds)
        except TimeoutError:
            return False
        return True

    async def _terminate_with_deadline(
        self, process: ManagedProcess, *, force: bool, timeout_seconds: float
    ) -> bool:
        try:
            await asyncio.wait_for(self._terminate(process, force=force), timeout_seconds)
        except Exception:
            return False
        return True

    async def _finish_orphan_check(
        self,
        process: ManagedProcess,
        return_task: asyncio.Task[int],
        limits: ShowdownProcessLimits,
        *,
        cleanup_failed: bool,
        forced: bool,
    ) -> bool:
        orphaned, verifier_failed = await self._orphan_status(process, limits)
        cleanup_failed = cleanup_failed or verifier_failed
        if orphaned or verifier_failed:
            forced = True
            containment_succeeded = await self._terminate_with_deadline(
                process, force=True, timeout_seconds=limits.forced_shutdown_timeout_seconds
            )
            cleanup_failed = cleanup_failed or not containment_succeeded
            exited = await self._wait_for_exit_with_deadline(
                return_task, limits.forced_shutdown_timeout_seconds
            )
            cleanup_failed = cleanup_failed or not exited
            orphaned, final_verifier_failed = await self._orphan_status(process, limits)
            cleanup_failed = cleanup_failed or final_verifier_failed
        job = _job_for(process)
        if job is not None:
            try:
                job.close()
            except Exception:
                cleanup_failed = True
        if cleanup_failed:
            raise OracleProcessError(
                OracleFailureClass.SHUTDOWN_FAILED, "process cleanup did not complete reliably"
            )
        if orphaned:
            raise OracleProcessError(
                OracleFailureClass.ORPHANED_CHILD_PROCESS, "process left a child process behind"
            )
        return forced

    async def _orphan_status(
        self, process: ManagedProcess, limits: ShowdownProcessLimits
    ) -> tuple[bool, bool]:
        try:
            return (
                await asyncio.wait_for(
                    self._orphan_verifier(process), limits.forced_shutdown_timeout_seconds
                ),
                False,
            )
        except Exception:
            return False, True

    async def _terminate(self, process: ManagedProcess, *, force: bool) -> None:
        if self._terminator is not None:
            await self._terminator(process, force=force)
            return
        await _default_terminate(process, force=force)


__all__ = [
    "ManagedProcess",
    "OracleProcessError",
    "OracleProcessResult",
    "ProcessInteractionStep",
    "ProcessResponseBarrier",
    "ShowdownProcessLimits",
    "ShowdownProcessRunner",
    "ShowdownProcessSpec",
    "sanitize_stderr",
]
