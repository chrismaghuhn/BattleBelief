"""Tests for the injected local Showdown stdio process lifecycle."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

from battlebelief_lab.oracle.showdown.errors import OracleFailureClass
from battlebelief_lab.oracle.showdown.network import EXTERNAL_NETWORK_MARKER
from battlebelief_lab.oracle.showdown.process import (
    OracleProcessError,
    ProcessInteractionStep,
    ProcessResponseBarrier,
    ShowdownProcessLimits,
    ShowdownProcessRunner,
    ShowdownProcessSpec,
    _default_launcher,
    _has_recursive_descendant,
    _JobBoundProcess,
    _NativeWindowsJob,
    _reap_windows_setup_failure,
    _windows_creation_flags,
    _WindowsJob,
    sanitize_stderr,
)


class _Reader:
    def __init__(self, chunks: list[bytes], *, block: bool = False) -> None:
        self._chunks = chunks
        self._block = block

    async def read(self, _size: int) -> bytes:
        if self._block:
            await asyncio.Event().wait()
        await asyncio.sleep(0)
        return self._chunks.pop(0) if self._chunks else b""


class _WriteGatedReader(_Reader):
    def __init__(self, chunks: list[bytes], writer: _Writer, minimum_writes: list[int]) -> None:
        super().__init__(chunks)
        self._writer = writer
        self._minimum_writes = minimum_writes

    async def read(self, size: int) -> bytes:
        required_writes = self._minimum_writes[0] if self._minimum_writes else 0
        while len(self._writer.writes) < required_writes:
            await asyncio.sleep(0)
        if self._minimum_writes:
            self._minimum_writes.pop(0)
        return await super().read(size)


class _TailBlockingReader(_Reader):
    async def read(self, size: int) -> bytes:
        if self._chunks:
            return await super().read(size)
        await asyncio.Event().wait()
        raise AssertionError("an unblocked tail reader must not return")


class _ExplodingReader(_Reader):
    async def read(self, _size: int) -> bytes:
        raise RuntimeError("raw stderr reader failure must not escape")


class _ExitTriggeredReader(_Reader):
    def __init__(self, exit_event: asyncio.Event, chunks: list[bytes]) -> None:
        super().__init__(chunks)
        self._exit_event = exit_event

    async def read(self, size: int) -> bytes:
        await self._exit_event.wait()
        return await super().read(size)


class _FakeWindowsJob:
    def __init__(self, *, active_processes: int, close_fails: bool = False) -> None:
        self.active_processes = active_processes
        self.close_fails = close_fails
        self.terminated = False
        self.closed = False

    def active_process_count(self) -> int:
        return self.active_processes

    def terminate(self) -> None:
        self.terminated = True
        self.active_processes = 0

    def close(self) -> None:
        self.closed = True
        if self.close_fails:
            raise RuntimeError("job close failed")


class _Writer:
    def __init__(self, *, block_drain: bool = False) -> None:
        self.writes: list[bytes] = []
        self.closed = False
        self._block_drain = block_drain

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    async def drain(self) -> None:
        if self._block_drain:
            await asyncio.Event().wait()

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


class _Process:
    def __init__(
        self,
        stdout: list[bytes],
        *,
        stderr: list[bytes] | None = None,
        returncode: int = 0,
        block_wait: bool = False,
        block_drain: bool = False,
        exit_event: asyncio.Event | None = None,
    ) -> None:
        self.stdin = _Writer(block_drain=block_drain)
        self.stdout = _Reader(stdout)
        self.stderr = _Reader(stderr or [])
        self.returncode: int | None = None
        self._final_returncode = returncode
        self._block_wait = block_wait
        self._wait_event = asyncio.Event()
        self._exit_event = exit_event

    async def wait(self) -> int:
        if self._block_wait:
            await self._wait_event.wait()
        await asyncio.sleep(0)
        self.returncode = self._final_returncode
        if self._exit_event is not None:
            self._exit_event.set()
        return self._final_returncode


def _spec(*, steps: tuple[ProcessInteractionStep, ...] | None = None) -> ShowdownProcessSpec:
    return ShowdownProcessSpec(
        argv=("C:\\Program Files\\node\\node.exe", "pokemon-showdown", "simulate-battle"),
        cwd=Path("C:/oracle source with spaces"),
        env={"PATH": "test"},
        steps=steps
        or (
            ProcessInteractionStep(
                b">start {}\n",
                ProcessResponseBarrier(request_sides=frozenset({"p1", "p2"})),
            ),
            ProcessInteractionStep(b">p1 team 1\n>p2 team 1\n", ProcessResponseBarrier(end=True)),
        ),
    )


def _limits(**changes: float | int) -> ShowdownProcessLimits:
    values: dict[str, float | int] = {
        "start_timeout_seconds": 0.05,
        "write_timeout_seconds": 0.05,
        "response_timeout_seconds": 0.05,
        "fixture_timeout_seconds": 0.5,
        "graceful_shutdown_timeout_seconds": 0.05,
        "forced_shutdown_timeout_seconds": 0.05,
        "max_stdout_bytes": 4096,
        "max_messages": 16,
        "max_input_bytes": 4096,
        "max_stderr_bytes": 128,
    }
    values.update(changes)
    return ShowdownProcessLimits(**values)  # type: ignore[arg-type]


def _runner(process: _Process, **kwargs: object) -> ShowdownProcessRunner:
    captured = kwargs.pop("captured", None)

    async def launcher(
        argv: tuple[str, ...], cwd: Path, env: Mapping[str, str], new_process_group: bool
    ) -> _Process:
        if captured is not None:
            captured.extend([argv, cwd, dict(env), new_process_group])  # type: ignore[union-attr]
        return process

    return ShowdownProcessRunner(launcher=launcher, **kwargs)  # type: ignore[arg-type]


def _stdout_for_two_steps() -> list[bytes]:
    return [
        b"update\n|start\n\nsideupdate\np1\n|request|{}\n\n",
        b"sideupdate\np2\n|request|{}\n\n",
        b"end\n{}\n\n",
    ]


def _two_step_process(*, block_wait: bool = False) -> _Process:
    process = _Process([], block_wait=block_wait)
    process.stdout = _WriteGatedReader(_stdout_for_two_steps(), process.stdin, [1, 1, 2])
    return process


def _job_bound_two_step_process(job: _FakeWindowsJob) -> _JobBoundProcess:
    return _JobBoundProcess(_two_step_process(), job)


def test_runner_stages_writes_and_keeps_stdin_open_until_final_barrier() -> None:
    process = _two_step_process()
    result = asyncio.run(_runner(process).run(_spec(), _limits()))

    assert process.stdin.writes == [b">start {}\n", b">p1 team 1\n>p2 team 1\n"]
    assert process.stdin.closed is True
    assert result.returncode == 0
    assert len(result.messages) == 4
    assert result.forced_shutdown is False


def test_runner_passes_windows_space_paths_as_argv_without_a_shell() -> None:
    process = _two_step_process()
    captured: list[object] = []
    asyncio.run(_runner(process, captured=captured).run(_spec(), _limits()))

    assert captured[0] == _spec().argv
    assert captured[1] == Path("C:/oracle source with spaces")
    assert captured[3] is True


def test_windows_creator_links_are_resolved_as_a_recursive_descendant_closure() -> None:
    assert _has_recursive_descendant(100, {200: 100, 300: 200, 400: 300})
    assert not _has_recursive_descendant(100, {300: 200, 400: 300})
    assert not _has_recursive_descendant(100, {})


def test_windows_oracle_creation_flags_suspend_before_execution() -> None:
    flags = _windows_creation_flags()

    assert flags & subprocess.CREATE_NEW_PROCESS_GROUP
    assert flags & 0x00000004


def test_windows_setup_failure_cleanup_terminates_reaps_verifies_and_closes_job() -> None:
    job = _FakeWindowsJob(active_processes=1)
    process = _JobBoundProcess(_Process([]), job)

    cleanup_succeeded = asyncio.run(_reap_windows_setup_failure(process, job))

    assert cleanup_succeeded is True
    assert job.terminated is True
    assert job.active_processes == 0
    assert job.closed is True


def test_windows_setup_failure_cleanup_reports_unprovable_close() -> None:
    job = _FakeWindowsJob(active_processes=1, close_fails=True)
    process = _JobBoundProcess(_Process([]), job)

    cleanup_succeeded = asyncio.run(_reap_windows_setup_failure(process, job))

    assert cleanup_succeeded is False
    assert job.terminated is True
    assert job.closed is True


def test_job_descendants_force_cleanup_then_final_verify_before_handle_close() -> None:
    job = _FakeWindowsJob(active_processes=1)
    bound_process = _job_bound_two_step_process(job)

    async def launcher(
        _argv: tuple[str, ...], _cwd: Path, _env: Mapping[str, str], _new_group: bool
    ) -> _JobBoundProcess:
        return bound_process

    result = asyncio.run(ShowdownProcessRunner(launcher=launcher).run(_spec(), _limits()))

    assert result.forced_shutdown is True
    assert job.terminated is True
    assert job.closed is True
    assert job.active_processes == 0


def test_windows_job_close_failure_overrides_primary_protocol_failure() -> None:
    job = _FakeWindowsJob(active_processes=0, close_fails=True)
    process = _Process([b"not-a-frame\n\n"])
    bound_process = _JobBoundProcess(process, job)

    async def launcher(
        _argv: tuple[str, ...], _cwd: Path, _env: Mapping[str, str], _new_group: bool
    ) -> _JobBoundProcess:
        return bound_process

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(ShowdownProcessRunner(launcher=launcher).run(_spec(), _limits()))

    assert error.value.failure_class is OracleFailureClass.SHUTDOWN_FAILED
    assert job.closed is True


@pytest.mark.skipif(os.name != "nt", reason="requires the Windows Job Object API")
def test_native_windows_job_terminates_a_bound_child_when_available() -> None:
    async def run_child() -> None:
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "import time; time.sleep(30)",
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        job: _NativeWindowsJob | None = None
        try:
            if child.pid is None:
                pytest.fail("Windows child has no PID")
            try:
                job = _NativeWindowsJob.create_and_assign(child.pid)
            except RuntimeError as exc:
                pytest.skip(f"nested Windows Job Object assignment unavailable: {exc}")
            assert job.active_process_count() >= 1
            job.terminate()
            await asyncio.wait_for(child.wait(), timeout=2.0)
            assert job.active_process_count() == 0
        finally:
            if job is not None:
                job.close()
            if child.returncode is None:
                child.kill()
                await child.wait()

    asyncio.run(run_child())


@pytest.mark.skipif(os.name != "nt", reason="requires Windows process creation flags")
def test_default_windows_job_provisioning_contains_root_and_grandchild_when_available() -> None:
    async def wait_for_job_to_empty(job: _WindowsJob, timeout_seconds: float) -> bool:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            if job.active_process_count() == 0:
                return True
            await asyncio.sleep(0.01)
        return False

    async def run_child_tree() -> None:
        child_script = "import time; time.sleep(30)"
        root_script = (
            "import subprocess, sys, time; "
            f"subprocess.Popen([sys.executable, '-c', {child_script!r}]); "
            "time.sleep(30)"
        )
        process = await _default_launcher(
            (sys.executable, "-c", root_script), Path.cwd(), dict(os.environ), True
        )
        assert isinstance(process, _JobBoundProcess)
        try:
            deadline = asyncio.get_running_loop().time() + 2.0
            while process.job.active_process_count() < 2:
                if asyncio.get_running_loop().time() >= deadline:
                    pytest.fail("bound root did not start its grandchild")
                await asyncio.sleep(0.01)
            process.job.terminate()
            await asyncio.wait_for(process.wait(), timeout=2.0)
            assert await wait_for_job_to_empty(process.job, timeout_seconds=2.0)
        finally:
            process.job.close()

    asyncio.run(run_child_tree())


def test_process_spec_defensively_freezes_a_string_only_environment() -> None:
    environment = {"PATH": "first"}
    spec = _spec()
    custom = ShowdownProcessSpec(
        argv=spec.argv,
        cwd=spec.cwd,
        env=environment,
        steps=spec.steps,
    )
    environment["PATH"] = "changed"

    assert custom.env["PATH"] == "first"
    with pytest.raises(TypeError):
        custom.env["PATH"] = "mutate"  # type: ignore[index]
    with pytest.raises(TypeError):
        ShowdownProcessSpec(argv=spec.argv, cwd=spec.cwd, env={"PATH": 3}, steps=spec.steps)  # type: ignore[dict-item]


@pytest.mark.parametrize("input_bytes", [bytearray(b">start {}\n"), memoryview(b">start {}\n")])
def test_process_step_requires_exact_bytes(input_bytes: object) -> None:
    with pytest.raises(TypeError):
        ProcessInteractionStep(input_bytes, ProcessResponseBarrier(end=True))  # type: ignore[arg-type]


def test_runner_decodes_partial_and_multiple_protocol_frames() -> None:
    process = _Process([])
    process.stdout = _WriteGatedReader(
        [
            b"upd",
            b"ate\n|start\n\nsideupdate\np1\n|request|{}\n\nsideupdate\np2\n|request|{}\n\n",
            b"end\n{}\n\n",
        ],
        process.stdin,
        [1, 1, 2],
    )
    result = asyncio.run(_runner(process).run(_spec(), _limits()))

    assert len(result.messages) == 4


def test_runner_allows_buffered_stdout_to_satisfy_barrier_after_clean_child_exit() -> None:
    exit_event = asyncio.Event()
    process = _Process([], exit_event=exit_event)
    process.stdout = _ExitTriggeredReader(exit_event, [b"update\n|start\n\nend\n{}\n\n"])
    steps = (ProcessInteractionStep(b">start {}\n", ProcessResponseBarrier(end=True)),)

    result = asyncio.run(_runner(process).run(_spec(steps=steps), _limits()))

    assert result.returncode == 0
    assert result.completed_barriers is True


def test_runner_does_not_reuse_previous_step_requests_for_a_later_barrier() -> None:
    process = _Process([])
    process.stdout = _WriteGatedReader(
        [
            b"update\n|start\n\nsideupdate\np1\n|request|{}\n\nsideupdate\np2\n|request|{}\n\n",
            b"sideupdate\np1\n|request|{}\n\nsideupdate\np2\n|request|{}\n\n",
            b"end\n{}\n\n",
        ],
        process.stdin,
        [1, 2, 3],
    )
    steps = (
        ProcessInteractionStep(
            b">start {}\n", ProcessResponseBarrier(request_sides=frozenset({"p1", "p2"}))
        ),
        ProcessInteractionStep(
            b">p1 team 1\n>p2 team 1\n",
            ProcessResponseBarrier(request_sides=frozenset({"p1", "p2"})),
        ),
        ProcessInteractionStep(b">forcetie\n", ProcessResponseBarrier(end=True)),
    )

    result = asyncio.run(_runner(process).run(_spec(steps=steps), _limits()))

    assert result.completed_barriers is True
    assert process.stdin.writes == [step.input_bytes for step in steps]


@pytest.mark.parametrize(
    "steps",
    [
        (ProcessInteractionStep(b">" + b"x" * 32 + b"\n", ProcessResponseBarrier(end=True)),),
        (
            ProcessInteractionStep(b">first\n", ProcessResponseBarrier(end=True)),
            ProcessInteractionStep(b">second\n", ProcessResponseBarrier(end=True)),
        ),
    ],
)
def test_runner_rejects_input_limit_before_launching_child(
    steps: tuple[ProcessInteractionStep, ...],
) -> None:
    launches = 0

    async def launcher(
        _argv: tuple[str, ...], _cwd: Path, _env: Mapping[str, str], _new_group: bool
    ) -> _Process:
        nonlocal launches
        launches += 1
        return _Process([])

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(
            ShowdownProcessRunner(launcher=launcher).run(
                _spec(steps=steps), _limits(max_input_bytes=10)
            )
        )

    assert error.value.failure_class is OracleFailureClass.INPUT_TOO_LARGE
    assert launches == 0


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("start", OracleFailureClass.START_TIMEOUT),
        ("write", OracleFailureClass.WRITE_TIMEOUT),
        ("response", OracleFailureClass.RESPONSE_TIMEOUT),
        ("fixture", OracleFailureClass.FIXTURE_TIMEOUT),
    ],
)
def test_runner_classifies_stage_timeouts(mode: str, expected: OracleFailureClass) -> None:
    process = _Process([], block_drain=mode == "write", block_wait=mode == "fixture")
    if mode in {"response", "fixture"}:
        process.stdout = _Reader([], block=True)

    async def blocked_launcher(
        _argv: tuple[str, ...], _cwd: Path, _env: Mapping[str, str], _new_group: bool
    ) -> _Process:
        if mode == "start":
            await asyncio.Event().wait()
        return process

    limits = _limits(
        response_timeout_seconds=0.02,
        fixture_timeout_seconds=0.02 if mode == "fixture" else 0.5,
    )
    steps = (
        ProcessInteractionStep(
            b">start {}\n",
            ProcessResponseBarrier(request_sides=frozenset({"p1"})),
        ),
    )

    async def terminator(target: _Process, *, force: bool) -> None:
        if mode == "fixture":
            target._wait_event.set()

    runner = ShowdownProcessRunner(launcher=blocked_launcher, terminator=terminator)

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(runner.run(_spec(steps=steps), limits))

    assert error.value.failure_class is expected


def test_runner_classifies_stdout_limit_and_malformed_protocol() -> None:
    oversized = _Process([b"x" * 32])
    with pytest.raises(OracleProcessError) as overflow:
        asyncio.run(_runner(oversized).run(_spec(), _limits(max_stdout_bytes=8)))
    assert overflow.value.failure_class is OracleFailureClass.OUTPUT_TOO_LARGE

    malformed = _Process([b"not-a-frame\n\n"])
    with pytest.raises(OracleProcessError) as decoded:
        asyncio.run(_runner(malformed).run(_spec(), _limits()))
    assert decoded.value.failure_class is OracleFailureClass.PROTOCOL_DESYNCHRONIZATION


def test_runner_classifies_message_count_overflow() -> None:
    process = _Process(
        [
            b"update\n|start\n\nsideupdate\np1\n|request|{}\n\nsideupdate\np2\n|request|{}\n\nend\n{}\n\n"
        ]
    )

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(_runner(process).run(_spec(), _limits(max_messages=3)))

    assert error.value.failure_class is OracleFailureClass.OUTPUT_TOO_LARGE


def test_runner_fails_closed_for_cumulative_stderr_overflow() -> None:
    process = _two_step_process()
    process.stderr = _Reader([b"x" * 12, b"y" * 12, b"z" * 12])

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(_runner(process).run(_spec(), _limits(max_stderr_bytes=24)))

    assert error.value.failure_class is OracleFailureClass.OUTPUT_TOO_LARGE


def test_runner_propagates_a_stderr_drain_failure_after_final_barrier() -> None:
    process = _two_step_process()
    process.stderr = _ExplodingReader([])

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(_runner(process).run(_spec(), _limits()))

    assert error.value.failure_class is OracleFailureClass.PROCESS_CRASH


def test_runner_converts_missing_executable_and_unexpected_launcher_error() -> None:
    async def missing(
        _argv: tuple[str, ...], _cwd: Path, _env: Mapping[str, str], _new_group: bool
    ) -> _Process:
        raise FileNotFoundError

    async def broken(
        _argv: tuple[str, ...], _cwd: Path, _env: Mapping[str, str], _new_group: bool
    ) -> _Process:
        raise RuntimeError("contains a C:\\Users\\Alice\\secret token=do-not-keep")

    with pytest.raises(OracleProcessError) as missing_error:
        asyncio.run(ShowdownProcessRunner(launcher=missing).run(_spec(), _limits()))
    with pytest.raises(OracleProcessError) as broken_error:
        asyncio.run(ShowdownProcessRunner(launcher=broken).run(_spec(), _limits()))

    assert missing_error.value.failure_class is OracleFailureClass.NODE_NOT_FOUND
    assert broken_error.value.failure_class is OracleFailureClass.PROCESS_CRASH
    assert "Alice" not in broken_error.value.diagnostic


def test_missing_stdio_stream_still_terminates_reaps_and_verifies_started_child() -> None:
    process = _Process([], block_wait=True)
    process.stdout = None
    terminations: list[bool] = []
    verification_calls = 0

    async def terminator(target: _Process, *, force: bool) -> None:
        terminations.append(force)
        target._wait_event.set()

    async def verifier(_process: _Process) -> bool:
        nonlocal verification_calls
        verification_calls += 1
        return False

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(
            _runner(process, terminator=terminator, orphan_verifier=verifier).run(
                _spec(), _limits()
            )
        )

    assert error.value.failure_class is OracleFailureClass.PROTOCOL_DESYNCHRONIZATION
    assert terminations == [False]
    assert verification_calls == 1


def test_runner_rejects_protocol_failure_after_final_barrier_during_final_drain() -> None:
    process = _Process(
        [
            b"update\n|start\n\nsideupdate\np1\n|request|{}\n\nsideupdate\np2\n|request|{}\n\nend\n{}\n\n",
            b"update\n|turn|2\n\n",
        ]
    )

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(_runner(process).run(_spec(), _limits()))

    assert error.value.failure_class is OracleFailureClass.PROTOCOL_DESYNCHRONIZATION


def test_runner_bounds_final_stream_drain_after_the_final_barrier() -> None:
    process = _Process([])
    process.stdout = _TailBlockingReader([b"update\n|start\n\nend\n{}\n\n"])
    steps = (ProcessInteractionStep(b">start {}\n", ProcessResponseBarrier(end=True)),)

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(_runner(process).run(_spec(steps=steps), _limits()))

    assert error.value.failure_class is OracleFailureClass.SHUTDOWN_FAILED


def test_runner_returns_promptly_for_side_error_without_assigning_fixture_semantics() -> None:
    process = _Process([b"sideupdate\np1\n|error|[Invalid choice] nope\n\n"])

    result = asyncio.run(_runner(process).run(_spec(), _limits()))

    assert result.completed_barriers is False
    assert result.terminal_side_error is not None
    assert result.terminal_side_error.side == "p1"


@pytest.mark.parametrize(
    ("returncode", "expected"),
    [(-9, OracleFailureClass.PROCESS_CRASH), (2, OracleFailureClass.UNEXPECTED_EXIT_CODE)],
)
def test_runner_classifies_crash_and_nonzero_exit(
    returncode: int, expected: OracleFailureClass
) -> None:
    process = _Process([b"update\n|start\n\nend\n{}\n\n"], returncode=returncode)
    steps = (ProcessInteractionStep(b">start {}\n", ProcessResponseBarrier(end=True)),)

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(_runner(process).run(_spec(steps=steps), _limits()))

    assert error.value.failure_class is expected


def test_network_guard_marker_overrides_a_generic_nonzero_child_exit() -> None:
    process = _Process(
        [b"update\n|start\n\nend\n{}\n\n"],
        stderr=[f"private target {EXTERNAL_NETWORK_MARKER}\n".encode("ascii")],
        returncode=7,
    )
    steps = (ProcessInteractionStep(b">start {}\n", ProcessResponseBarrier(end=True)),)

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(_runner(process).run(_spec(steps=steps), _limits()))

    assert error.value.failure_class is OracleFailureClass.EXTERNAL_NETWORK_ATTEMPT


def test_runner_classifies_exit_before_barrier_as_protocol_desynchronization() -> None:
    process = _Process([b"update\n|start\n\n"], returncode=0)
    steps = (
        ProcessInteractionStep(
            b">start {}\n", ProcessResponseBarrier(request_sides=frozenset({"p1"}))
        ),
    )

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(_runner(process).run(_spec(steps=steps), _limits()))

    assert error.value.failure_class is OracleFailureClass.PROTOCOL_DESYNCHRONIZATION


@pytest.mark.parametrize(
    ("returncode", "expected"),
    [(-9, OracleFailureClass.PROCESS_CRASH), (7, OracleFailureClass.UNEXPECTED_EXIT_CODE)],
)
def test_independent_nonzero_exit_overrides_incomplete_stdout_protocol_failure(
    returncode: int, expected: OracleFailureClass
) -> None:
    process = _Process([], returncode=returncode)
    steps = (ProcessInteractionStep(b">start {}\n", ProcessResponseBarrier(end=True)),)

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(_runner(process).run(_spec(steps=steps), _limits()))

    assert error.value.failure_class is expected


def test_independent_nonzero_exit_does_not_override_output_limit_failure() -> None:
    process = _Process([b"x" * 32], returncode=7)
    steps = (ProcessInteractionStep(b">start {}\n", ProcessResponseBarrier(end=True)),)

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(_runner(process).run(_spec(steps=steps), _limits(max_stdout_bytes=8)))

    assert error.value.failure_class is OracleFailureClass.OUTPUT_TOO_LARGE


def test_runner_induced_exit_does_not_override_pending_protocol_failure() -> None:
    process = _Process([b"not-a-frame\n\n"], block_wait=True)

    async def terminator(target: _Process, *, force: bool) -> None:
        assert force is False
        target._final_returncode = -9
        target._wait_event.set()

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(_runner(process, terminator=terminator).run(_spec(), _limits()))

    assert error.value.failure_class is OracleFailureClass.PROTOCOL_DESYNCHRONIZATION


@pytest.mark.parametrize(
    ("returncode", "expected"),
    [(-9, OracleFailureClass.PROCESS_CRASH), (3, OracleFailureClass.UNEXPECTED_EXIT_CODE)],
)
def test_runner_preserves_nonzero_exit_class_before_a_required_barrier(
    returncode: int, expected: OracleFailureClass
) -> None:
    process = _Process([b"update\n|start\n\n"], returncode=returncode)
    steps = (
        ProcessInteractionStep(
            b">start {}\n", ProcessResponseBarrier(request_sides=frozenset({"p1"}))
        ),
    )

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(_runner(process).run(_spec(steps=steps), _limits()))

    assert error.value.failure_class is expected


def test_shutdown_forces_then_rejects_orphaned_child() -> None:
    process = _two_step_process(block_wait=True)
    calls: list[bool] = []

    async def terminator(_process: _Process, *, force: bool) -> None:
        calls.append(force)
        if force:
            _process._block_wait = False
            _process._wait_event.set()

    async def verifier(_process: _Process) -> bool:
        return True

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(
            _runner(process, terminator=terminator, orphan_verifier=verifier).run(
                _spec(), _limits()
            )
        )

    assert calls == [False, True, True]
    assert error.value.failure_class is OracleFailureClass.ORPHANED_CHILD_PROCESS


def test_shutdown_fails_when_forced_termination_cannot_reap_process() -> None:
    process = _two_step_process(block_wait=True)

    async def terminator(_process: _Process, *, force: bool) -> None:
        return None

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(_runner(process, terminator=terminator).run(_spec(), _limits()))

    assert error.value.failure_class is OracleFailureClass.SHUTDOWN_FAILED


def test_shutdown_bounds_a_blocking_terminator_call() -> None:
    process = _two_step_process(block_wait=True)

    async def blocking_terminator(_process: _Process, *, force: bool) -> None:
        await asyncio.Event().wait()

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(_runner(process, terminator=blocking_terminator).run(_spec(), _limits()))

    assert error.value.failure_class is OracleFailureClass.SHUTDOWN_FAILED


def test_soft_termination_failure_still_forces_reaps_and_verifies() -> None:
    process = _two_step_process(block_wait=True)
    terminations: list[bool] = []
    verification_calls = 0

    async def terminator(target: _Process, *, force: bool) -> None:
        terminations.append(force)
        if not force:
            raise RuntimeError("soft termination failed")
        target._wait_event.set()

    async def verifier(_process: _Process) -> bool:
        nonlocal verification_calls
        verification_calls += 1
        return False

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(
            _runner(process, terminator=terminator, orphan_verifier=verifier).run(
                _spec(), _limits()
            )
        )

    assert error.value.failure_class is OracleFailureClass.SHUTDOWN_FAILED
    assert terminations == [False, True]
    assert verification_calls == 1


def test_shutdown_bounds_a_blocking_orphan_verifier() -> None:
    process = _two_step_process()

    async def blocking_verifier(_process: _Process) -> bool:
        await asyncio.Event().wait()

    with pytest.raises(OracleProcessError) as error:
        asyncio.run(_runner(process, orphan_verifier=blocking_verifier).run(_spec(), _limits()))

    assert error.value.failure_class is OracleFailureClass.SHUTDOWN_FAILED


def test_intentional_termination_preserves_induced_negative_exit_as_telemetry() -> None:
    process = _two_step_process(block_wait=True)

    async def terminator(target: _Process, *, force: bool) -> None:
        assert force is False
        target._final_returncode = -9
        target._wait_event.set()

    result = asyncio.run(_runner(process, terminator=terminator).run(_spec(), _limits()))

    assert result.returncode == -9
    assert result.forced_shutdown is True


def test_runner_contains_an_unexpected_shutdown_exception() -> None:
    process = _two_step_process()

    async def terminator(_process: _Process, *, force: bool) -> None:
        raise RuntimeError("C:\\Users\\Alice\\token=not-for-evidence")

    process._block_wait = True
    with pytest.raises(OracleProcessError) as error:
        asyncio.run(_runner(process, terminator=terminator).run(_spec(), _limits()))

    assert error.value.failure_class is OracleFailureClass.SHUTDOWN_FAILED
    assert "Alice" not in error.value.diagnostic


def test_stderr_is_sanitized_and_bounded() -> None:
    raw = (
        "token=abc password: 'bad value' api_key=\"api secret\" "
        "Authorization: Bearer auth-secret\nCookie: session=private; second=also-private\n"
        "C:\\Users\\Alice Smith\\secret.txt C:/Users/Alice Smith/x "
        "\\\\server\\share with spaces\\secret /opt/runner path/file "
        "hostname=my-box username=alice 192.0.2.4 private.example.test"
    )

    diagnostic = sanitize_stderr(raw.encode(), max_bytes=64)

    assert "abc" not in diagnostic
    assert "bad value" not in diagnostic
    assert "api secret" not in diagnostic
    assert "auth-secret" not in diagnostic
    assert "private" not in diagnostic
    assert "Alice" not in diagnostic
    assert "alice" not in diagnostic
    assert "my-box" not in diagnostic
    assert "192.0.2.4" not in diagnostic
    assert "example.test" not in diagnostic
    assert len(diagnostic.encode("utf-8")) <= 64


@pytest.mark.parametrize("max_bytes", [1, 2, 3, 4, 8])
def test_stderr_sanitizer_never_exceeds_a_tiny_byte_limit(max_bytes: int) -> None:
    diagnostic = sanitize_stderr(b"/opt/runner path/private", max_bytes=max_bytes)

    assert len(diagnostic.encode("utf-8")) <= max_bytes
