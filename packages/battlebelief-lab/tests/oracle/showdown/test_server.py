"""Unit tests for the non-authoritative loopback server lifecycle smoke."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import cast

import pytest

from battlebelief_lab.oracle.showdown.errors import OracleFailureClass
from battlebelief_lab.oracle.showdown.process import OracleProcessError
from battlebelief_lab.oracle.showdown.server import (
    LoopbackServerConfig,
    LoopbackServerLimits,
    LoopbackServerSmoke,
    _controlled_config_bytes,
    _remove_generated_log_index,
    _ServerDrain,
)


class _Reader:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    async def read(self, _size: int) -> bytes:
        await asyncio.sleep(0)
        return self._chunks.pop(0) if self._chunks else b""


class _Writer:
    def close(self) -> None:
        return None

    async def wait_closed(self) -> None:
        return None


class _Process:
    def __init__(self) -> None:
        self.stdin = _Writer()
        self.stdout = _Reader([b"server operational noise\n"])
        self.stderr = _Reader([b"BATTLEBELIEF_ORACLE_LOOPBACK_LISTEN\n"])
        self.returncode: int | None = None
        self._exited = asyncio.Event()

    async def wait(self) -> int:
        await self._exited.wait()
        self.returncode = 0
        return 0


def _limits() -> LoopbackServerLimits:
    return LoopbackServerLimits(
        start_timeout_seconds=0.1,
        readiness_timeout_seconds=0.1,
        graceful_shutdown_timeout_seconds=0.1,
        forced_shutdown_timeout_seconds=0.1,
        max_stdout_bytes=1024,
        max_stderr_bytes=1024,
    )


def test_server_config_rejects_every_non_literal_loopback_target() -> None:
    for target in ("localhost", "0.0.0.0", "192.0.2.7", "example.test", "::"):
        with pytest.raises(ValueError, match="literal loopback"):
            LoopbackServerConfig(
                source_directory=Path("C:/source with spaces"),
                node_executable=Path("C:/node/node.exe"),
                environment={"SYSTEMROOT": "C:/Windows"},
                bind_address=target,
            )


def test_server_config_uses_only_an_os_assigned_port() -> None:
    with pytest.raises(ValueError, match="port 0"):
        LoopbackServerConfig(
            source_directory=Path("C:/source with spaces"),
            node_executable=Path("C:/node/node.exe"),
            environment={"SYSTEMROOT": "C:/Windows"},
            port=8000,
        )


def test_server_smoke_rejects_a_preexisting_upstream_log_index(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "config").mkdir(parents=True)
    log_index = source / "logs" / ".gitindex"
    log_index.parent.mkdir()
    log_index.write_bytes(b"preexisting")

    with pytest.raises(OracleProcessError) as raised:
        asyncio.run(
            LoopbackServerSmoke().run(
                LoopbackServerConfig(
                    source_directory=source,
                    node_executable=Path("C:/node/node.exe"),
                    environment={"SYSTEMROOT": "C:/Windows"},
                ),
                _limits(),
            )
        )

    assert raised.value.failure_class is OracleFailureClass.SOURCE_DIRTY
    assert log_index.read_bytes() == b"preexisting"


def test_generated_log_index_must_exactly_match_the_current_git_index(tmp_path: Path) -> None:
    source = tmp_path / "source"
    git = source / ".git"
    logs = source / "logs"
    git.mkdir(parents=True)
    logs.mkdir()
    (git / "index").write_bytes(b"current-git-index")
    generated = logs / ".gitindex"
    generated.write_bytes(b"different-bytes")

    with pytest.raises(OracleProcessError) as raised:
        _remove_generated_log_index(generated)

    assert raised.value.failure_class is OracleFailureClass.SOURCE_DIRTY
    assert generated.read_bytes() == b"different-bytes"
    generated.write_bytes(b"current-git-index")
    _remove_generated_log_index(generated)
    assert not generated.exists()


def test_server_stderr_markers_are_detected_across_read_chunks() -> None:
    state = _ServerDrain()
    split_external = b"BATTLEBELIEF_ORACLE_EXTERNAL_NETWORK_ATTEMPT"
    split_ready = b"BATTLEBELIEF_ORACLE_LOOPBACK_LISTEN"

    asyncio.run(
        LoopbackServerSmoke._drain_stderr(
            _Reader(
                [
                    split_external[:19],
                    split_external[19:] + b"\nnoise\n" + split_ready[:14],
                    split_ready[14:] + b"\n",
                ]
            ),
            state,
            _limits(),
        )
    )

    assert state.external_network_attempt is True
    assert state.ready is True


def test_controlled_server_config_disables_upstream_artemis_children() -> None:
    config = _controlled_config_bytes("127.0.0.1")

    subprocesses = re.search(rb"^exports\.subprocesses = \{(.+)\};$", config, re.MULTILINE)

    assert subprocesses is not None
    assert dict(item.split(b": ", maxsplit=1) for item in subprocesses.group(1).split(b", ")) == {
        b"localartemis": b"0",
        b"remoteartemis": b"0",
        b"battlesearch": b"0",
        b"datasearch": b"0",
        b"friends": b"0",
        b"chatdb": b"0",
        b"pm": b"0",
        b"modlog": b"0",
        b"network": b"1",
        b"simulator": b"0",
        b"validator": b"0",
        b"verifier": b"0",
    }


def test_server_smoke_uses_the_guard_creates_then_removes_controlled_config(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source with spaces"
    (source / "config").mkdir(parents=True)
    process = _Process()
    captured: list[object] = []

    async def launcher(
        argv: tuple[str, ...], cwd: Path, environment: object, new_group: bool
    ) -> _Process:
        captured.extend([argv, cwd, dict(cast(dict[str, str], environment)), new_group])
        assert (source / "config" / "config.js").is_file()
        git = source / ".git"
        git.mkdir()
        (git / "index").write_bytes(b"upstream-generated-index")
        logs = source / "logs"
        logs.mkdir()
        (logs / ".gitindex").write_bytes(b"upstream-generated-index")
        return process

    async def terminate(target: _Process, *, force: bool) -> None:
        assert force is False
        target._exited.set()

    async def no_orphan(_process: _Process) -> bool:
        return False

    result = asyncio.run(
        LoopbackServerSmoke(
            launcher=launcher,
            terminator=terminate,
            orphan_verifier=no_orphan,
        ).run(
            LoopbackServerConfig(
                source_directory=source,
                node_executable=Path("C:/node/node.exe"),
                environment={"SYSTEMROOT": "C:/Windows", "NODE_OPTIONS": "--inspect"},
            ),
            _limits(),
        )
    )

    assert result.ready is True
    assert result.forced_shutdown is False
    assert b"BATTLEBELIEF_ORACLE_LOOPBACK_LISTEN" not in result.canonical_profile_bytes()
    assert not (source / "config" / "config.js").exists()
    assert not (source / "logs" / ".gitindex").exists()
    assert captured[0][-3:] == ("--skip-build", "start", "0")
    assert captured[1] == source
    assert captured[3] is True
    assert captured[2]["NODE_OPTIONS"].startswith("--require ")
    assert "--inspect" not in captured[2]["NODE_OPTIONS"]


def test_external_marker_split_across_chunks_overrides_readiness_timeout_after_cleanup(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    (source / "config").mkdir(parents=True)
    process = _Process()
    marker = b"BATTLEBELIEF_ORACLE_EXTERNAL_NETWORK_ATTEMPT"
    process.stderr = _Reader([marker[:21], marker[21:] + b"\n"])

    async def launcher(
        _argv: tuple[str, ...], _cwd: Path, _environment: object, _new_group: bool
    ) -> _Process:
        git = source / ".git"
        git.mkdir()
        (git / "index").write_bytes(b"generated-index")
        logs = source / "logs"
        logs.mkdir()
        (logs / ".gitindex").write_bytes(b"generated-index")
        return process

    async def terminate(target: _Process, *, force: bool) -> None:
        assert force is False
        target._exited.set()

    async def no_orphan(_process: _Process) -> bool:
        return False

    with pytest.raises(OracleProcessError) as raised:
        asyncio.run(
            LoopbackServerSmoke(
                launcher=launcher,
                terminator=terminate,
                orphan_verifier=no_orphan,
            ).run(
                LoopbackServerConfig(
                    source_directory=source,
                    node_executable=Path("C:/node/node.exe"),
                    environment={"SYSTEMROOT": "C:/Windows"},
                ),
                _limits(),
            )
        )

    assert raised.value.failure_class is OracleFailureClass.EXTERNAL_NETWORK_ATTEMPT
    assert not (source / "config" / "config.js").exists()
    assert not (source / "logs" / ".gitindex").exists()
