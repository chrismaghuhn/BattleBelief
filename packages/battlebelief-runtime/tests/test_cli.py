from __future__ import annotations

import asyncio
import dataclasses
import json
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_core.errors import (
    LocalActionGateRejection,
    NoLegalActionError,
    StaleRequestIdentity,
)
from battlebelief_runtime.adapters.team_files.loader import load_packed_team
from battlebelief_runtime.adapters.team_files.packed_team import PackedTeam
from battlebelief_runtime.cli import ChallengeRunner, main
from battlebelief_runtime.composition.battle_session import BattleSessionResult
from battlebelief_runtime.config import (
    DEFAULT_CHALLENGE_SETUP_TIMEOUT_SECONDS,
    DEFAULT_SERVER_URL,
    ChallengeConfig,
)
from battlebelief_runtime.errors import ChallengeSetupError, Disconnect
from battlebelief_runtime.public_api import runtime_status

_PASSWORD_ENV = "BATTLEBELIEF_SHOWDOWN_PASSWORD"
_PASSWORD = "correct horse battery staple"
_PACKED_TEAM = (
    "Garchomp||rockyhelmet|roughskin|earthquake|jolly|0,252,0,0,4,252|M|,0,,,,|S|50|,,,,,Ground\n"
)


def _result(primary_error: BaseException | None = None) -> BattleSessionResult:
    return BattleSessionResult(
        state=ObservedState.initial("ash"),
        primary_error=primary_error,
        room_control_or_chat_count=0,
        explicit_request_submissions=0,
        default_submissions=0,
    )


class _FakeRunner:
    def __init__(
        self,
        result: BattleSessionResult | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.result = result or _result()
        self.error = error
        self.calls: list[tuple[ChallengeConfig, PackedTeam]] = []

    async def run(self, config: ChallengeConfig, team: PackedTeam) -> BattleSessionResult:
        self.calls.append((config, team))
        if self.error is not None:
            raise self.error
        return self.result


class _FakeCoordinator:
    def __init__(self, result: BattleSessionResult | None = None) -> None:
        self.result = result or _result()
        self.calls = 0

    async def run(self) -> BattleSessionResult:
        self.calls += 1
        return self.result


def _challenge_args(team_path: Path, *extra: str) -> list[str]:
    return [
        "challenge",
        "--username",
        "Ash",
        "--opponent",
        "Misty",
        "--team",
        str(team_path),
        *extra,
    ]


def _write_team(tmp_path: Path, content: str = _PACKED_TEAM) -> Path:
    path = tmp_path / "team.txt"
    path.write_text(content, encoding="utf-8")
    return path


def _runner_factory(
    runner: _FakeRunner,
    calls: list[str] | None = None,
) -> Callable[[], _FakeRunner]:
    def factory() -> _FakeRunner:
        if calls is not None:
            calls.append("runner")
        return runner

    return factory


def test_runtime_status_is_m0_entrypoint_only() -> None:
    assert runtime_status() == {
        "package": "battlebelief-runtime",
        "version": "0.1.0",
        "phase": "M0",
        "entrypoint": "ready",
        "battle_capability": "absent",
    }


def test_doctor_prints_canonical_status(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["doctor"]) == 0
    output = capsys.readouterr().out
    assert json.loads(output) == runtime_status()


def test_version_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "0.1.0"


def test_challenge_help_describes_outgoing_flow_without_password(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["challenge", "--help"])

    assert raised.value.code == 0
    output = capsys.readouterr().out.lower()
    assert "outgoing direct challenge" in output
    assert "opponent must accept" in output
    assert "--password" not in output


def test_unknown_password_argument_does_not_echo_its_value(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argument_secret = "argument-secret-must-not-leak"

    with pytest.raises(SystemExit) as raised:
        main([*_challenge_args(_write_team(tmp_path)), "--password", argument_secret])

    assert raised.value.code == 2
    captured = capsys.readouterr()
    assert argument_secret not in captured.out
    assert argument_secret not in captured.err


def test_config_defaults_are_explicit_and_password_is_repr_safe(tmp_path: Path) -> None:
    assert DEFAULT_SERVER_URL == "wss://sim3.psim.us/showdown/websocket"
    assert DEFAULT_CHALLENGE_SETUP_TIMEOUT_SECONDS == 120.0
    config = ChallengeConfig(
        username="Ash",
        opponent="Misty",
        team_path=tmp_path / "team.txt",
        server_url=DEFAULT_SERVER_URL,
        setup_timeout=DEFAULT_CHALLENGE_SETUP_TIMEOUT_SECONDS,
        password=_PASSWORD,
    )

    assert _PASSWORD not in repr(config)
    with pytest.raises((AttributeError, TypeError)):
        config.password = "replacement"  # type: ignore[misc]


@pytest.mark.parametrize("environment", [{}, {_PASSWORD_ENV: ""}])
def test_missing_or_empty_secret_exits_two_before_runner_construction(
    tmp_path: Path,
    environment: Mapping[str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []

    assert (
        main(
            _challenge_args(_write_team(tmp_path)),
            environment=environment,
            runner_factory=_runner_factory(_FakeRunner(), calls),
        )
        == 2
    )

    captured = capsys.readouterr()
    assert calls == []
    assert captured.out == ""
    assert _PASSWORD not in captured.err


def test_password_environment_is_read_at_invocation_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _FakeRunner()
    monkeypatch.setenv(_PASSWORD_ENV, _PASSWORD)

    assert (
        main(
            _challenge_args(_write_team(tmp_path)),
            runner_factory=_runner_factory(runner),
        )
        == 0
    )

    assert len(runner.calls) == 1
    assert runner.calls[0][0].password == _PASSWORD


@pytest.mark.parametrize(
    ("username", "opponent"),
    [
        ("!!!", "Misty"),
        ("Ash", "..."),
        ("Ash|injected", "Misty"),
        ("Ash", "Misty, gen9anythinggoes"),
        ("123", "Misty"),
        ("A" * 19, "Misty"),
        ("A" * 18 + "\u212a", "Misty"),
        ("   ", "Misty"),
    ],
)
def test_invalid_user_values_exit_two_before_runner_construction(
    tmp_path: Path,
    username: str,
    opponent: str,
) -> None:
    calls: list[str] = []
    args = _challenge_args(_write_team(tmp_path))
    args[args.index("Ash")] = username
    args[args.index("Misty")] = opponent

    assert (
        main(
            args,
            environment={_PASSWORD_ENV: _PASSWORD},
            runner_factory=_runner_factory(_FakeRunner(), calls),
        )
        == 2
    )
    assert calls == []


@pytest.mark.parametrize(
    ("username", "opponent"),
    [
        ("@Ash", "Misty"),
        ("Ash", "@Misty"),
        ("Misty\u212a", "Ash"),
    ],
)
def test_supported_showdown_display_forms_are_accepted(
    tmp_path: Path,
    username: str,
    opponent: str,
) -> None:
    runner = _FakeRunner()
    args = _challenge_args(_write_team(tmp_path))
    args[args.index("Ash")] = username
    args[args.index("Misty")] = opponent

    assert (
        main(
            args,
            environment={_PASSWORD_ENV: _PASSWORD},
            runner_factory=_runner_factory(runner),
        )
        == 0
    )

    assert len(runner.calls) == 1


@pytest.mark.parametrize(
    "server_url",
    [
        "ws://sim3.psim.us/showdown/websocket",
        "https://sim3.psim.us/showdown/websocket",
        "wss:///showdown/websocket",
        "wss://user:password@sim3.psim.us/showdown/websocket",
        "wss://sim3.psim.us/showdown/websocket\nmalicious",
        "wss://host\\evil/showdown/websocket",
        "wss://evil.example/showdown/websocket",
        "wss://sim3.psim.us.evil.example/showdown/websocket",
        "wss://127.0.0.1/showdown/websocket",
        "wss://sim3.psim.us/wrong-path",
        "wss://sim3.psim.us/showdown/websocket?x=1",
    ],
)
def test_unsafe_server_url_exits_two_before_runner_construction(
    tmp_path: Path,
    server_url: str,
) -> None:
    calls: list[str] = []

    assert (
        main(
            _challenge_args(_write_team(tmp_path), "--server-url", server_url),
            environment={_PASSWORD_ENV: _PASSWORD},
            runner_factory=_runner_factory(_FakeRunner(), calls),
        )
        == 2
    )
    assert calls == []


def test_official_server_with_explicit_tls_port_is_accepted(tmp_path: Path) -> None:
    runner = _FakeRunner()
    server_url = "wss://sim3.psim.us:443/showdown/websocket"

    assert (
        main(
            _challenge_args(_write_team(tmp_path), "--server-url", server_url),
            environment={_PASSWORD_ENV: _PASSWORD},
            runner_factory=_runner_factory(runner),
        )
        == 0
    )

    assert runner.calls[0][0].server_url == server_url


def test_missing_team_exits_two_before_runner_construction(tmp_path: Path) -> None:
    calls: list[str] = []

    assert (
        main(
            _challenge_args(tmp_path / "missing.txt"),
            environment={_PASSWORD_ENV: _PASSWORD},
            runner_factory=_runner_factory(_FakeRunner(), calls),
        )
        == 2
    )
    assert calls == []


def test_unreadable_team_exits_two_before_runner_construction(tmp_path: Path) -> None:
    calls: list[str] = []

    assert (
        main(
            _challenge_args(tmp_path),
            environment={_PASSWORD_ENV: _PASSWORD},
            runner_factory=_runner_factory(_FakeRunner(), calls),
        )
        == 2
    )
    assert calls == []


def test_non_utf8_team_exits_two_before_runner_construction(tmp_path: Path) -> None:
    calls: list[str] = []
    path = tmp_path / "team.txt"
    path.write_bytes(b"\xff\xfe\x00")

    assert (
        main(
            _challenge_args(path),
            environment={_PASSWORD_ENV: _PASSWORD},
            runner_factory=_runner_factory(_FakeRunner(), calls),
        )
        == 2
    )
    assert calls == []


def test_invalid_team_is_sanitized_and_runner_is_not_constructed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []
    packed_secret = "private-packed-team-content"

    assert (
        main(
            _challenge_args(_write_team(tmp_path, packed_secret)),
            environment={_PASSWORD_ENV: _PASSWORD},
            runner_factory=_runner_factory(_FakeRunner(), calls),
        )
        == 2
    )

    captured = capsys.readouterr()
    assert calls == []
    assert captured.out == ""
    assert captured.err.strip() == "team_validation_error: selected team is invalid"
    assert packed_secret not in captured.err
    assert _PASSWORD not in captured.err


def test_success_uses_defaults_and_runs_exactly_one_coordinator(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    runner = _FakeRunner()

    assert (
        main(
            _challenge_args(_write_team(tmp_path)),
            environment={_PASSWORD_ENV: _PASSWORD},
            runner_factory=_runner_factory(runner),
        )
        == 0
    )

    assert len(runner.calls) == 1
    config, team = runner.calls[0]
    assert config.server_url == DEFAULT_SERVER_URL
    assert config.setup_timeout == DEFAULT_CHALLENGE_SETUP_TIMEOUT_SECONDS
    assert config.password == _PASSWORD
    assert team.packed == _PACKED_TEAM.rstrip("\n")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_primary_error_exits_one_with_stable_code(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assertion_secret = "assertion-must-not-leak"
    runner = _FakeRunner(result=_result(Disconnect(assertion_secret)))

    assert (
        main(
            _challenge_args(_write_team(tmp_path)),
            environment={_PASSWORD_ENV: _PASSWORD},
            runner_factory=_runner_factory(runner),
        )
        == 1
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "disconnect"
    assert assertion_secret not in captured.err
    assert _PASSWORD not in captured.err


def test_thrown_setup_error_exits_one_with_stable_subcode(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    runner = _FakeRunner(
        error=ChallengeSetupError(
            subcode="challenge_setup_timeout",
            message="secret remote response",
        )
    )

    assert (
        main(
            _challenge_args(_write_team(tmp_path)),
            environment={_PASSWORD_ENV: _PASSWORD},
            runner_factory=_runner_factory(runner),
        )
        == 1
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "challenge_setup_error:challenge_setup_timeout"
    assert "secret remote response" not in captured.err


@pytest.mark.parametrize("delivery", ["raised", "primary_error"])
@pytest.mark.parametrize(
    ("error_type", "expected_code"),
    [
        (StaleRequestIdentity, "stale_rqid"),
        (LocalActionGateRejection, "local_action_gate_rejection"),
        (NoLegalActionError, "no_legal_action_available"),
    ],
)
def test_core_safety_errors_keep_their_stable_code_without_leaking_messages(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    delivery: str,
    error_type: type[RuntimeError],
    expected_code: str,
) -> None:
    secret_message = "classified-error-secret"
    error = error_type(secret_message)
    runner = (
        _FakeRunner(error=error) if delivery == "raised" else _FakeRunner(result=_result(error))
    )

    assert (
        main(
            _challenge_args(_write_team(tmp_path)),
            environment={_PASSWORD_ENV: _PASSWORD},
            runner_factory=_runner_factory(runner),
        )
        == 1
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == expected_code
    assert secret_message not in captured.err


def test_unclassified_error_exits_one_with_opaque_code(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret_message = "unclassified-error-secret"
    runner = _FakeRunner(error=RuntimeError(secret_message))

    assert (
        main(
            _challenge_args(_write_team(tmp_path)),
            environment={_PASSWORD_ENV: _PASSWORD},
            runner_factory=_runner_factory(runner),
        )
        == 1
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "runtime_error"
    assert secret_message not in captured.err


@pytest.mark.parametrize("error_type", [KeyboardInterrupt, asyncio.CancelledError])
def test_interruption_exits_one_without_a_traceback_or_message_leak(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    error_type: type[BaseException],
) -> None:
    secret_message = "interruption-secret-must-not-leak"
    runner = _FakeRunner(error=error_type(secret_message))

    assert (
        main(
            _challenge_args(_write_team(tmp_path)),
            environment={_PASSWORD_ENV: _PASSWORD},
            runner_factory=_runner_factory(runner),
        )
        == 1
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "runtime_error"
    assert secret_message not in captured.err


def test_completed_loss_exits_zero(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lost_state = dataclasses.replace(ObservedState.initial("ash"), winner="misty")
    runner = _FakeRunner(
        result=BattleSessionResult(
            state=lost_state,
            primary_error=None,
            room_control_or_chat_count=0,
            explicit_request_submissions=0,
            default_submissions=0,
        )
    )

    assert (
        main(
            _challenge_args(_write_team(tmp_path)),
            environment={_PASSWORD_ENV: _PASSWORD},
            runner_factory=_runner_factory(runner),
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_challenge_runner_has_injectable_connection_and_coordinator_seams(
    tmp_path: Path,
) -> None:
    config = ChallengeConfig(
        username="Ash",
        opponent="Misty",
        team_path=tmp_path / "team.txt",
        server_url=DEFAULT_SERVER_URL,
        setup_timeout=DEFAULT_CHALLENGE_SETUP_TIMEOUT_SECONDS,
        password=_PASSWORD,
    )
    team = load_packed_team(_write_team(tmp_path).read_text(encoding="utf-8"))
    connection = object()
    observed: list[tuple[object, ChallengeConfig, PackedTeam]] = []
    coordinator = _FakeCoordinator()

    def connection_factory(received_config: ChallengeConfig) -> object:
        assert received_config is config
        return connection

    def coordinator_factory(
        received_connection: object,
        received_config: ChallengeConfig,
        received_team: PackedTeam,
    ) -> _FakeCoordinator:
        observed.append((received_connection, received_config, received_team))
        return coordinator

    runner = ChallengeRunner(
        connection_factory=connection_factory,
        coordinator_factory=coordinator_factory,
    )

    result = asyncio.run(runner.run(config, team))

    assert result.primary_error is None
    assert observed == [(connection, config, team)]
    assert coordinator.calls == 1
