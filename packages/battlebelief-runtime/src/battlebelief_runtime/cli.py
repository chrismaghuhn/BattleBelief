from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Never, Protocol

from battlebelief_core.errors import (
    LocalActionGateRejection,
    NoLegalActionError,
    StaleRequestIdentity,
)
from battlebelief_runtime.adapters.showdown_client import (
    BattleConnection,
    ShowdownAssertionProvider,
    ShowdownConnection,
)
from battlebelief_runtime.adapters.team_files.loader import load_packed_team
from battlebelief_runtime.adapters.team_files.packed_team import PackedTeam
from battlebelief_runtime.composition.battle_coordinator import BattleCoordinator
from battlebelief_runtime.composition.battle_session import BattleSessionResult
from battlebelief_runtime.config import (
    DEFAULT_SERVER_URL,
    ChallengeConfig,
    ChallengeConfigError,
    load_challenge_config,
)
from battlebelief_runtime.errors import (
    ChallengeSetupError,
    Disconnect,
    MalformedProtocolMessage,
    ReducerInvariantFailure,
    RequestStateReconciliationMismatch,
    ServerInvalidChoice,
    ServerUnavailableChoice,
    TeamValidationError,
    TimerOrForfeit,
    TransportTimeout,
    UnknownProtocolEvent,
)
from battlebelief_runtime.public_api import runtime_status


class ChallengeCommandRunner(Protocol):
    async def run(
        self,
        config: ChallengeConfig,
        team: PackedTeam,
    ) -> BattleSessionResult:
        """Run one validated outgoing direct challenge."""


class ChallengeCoordinator(Protocol):
    async def run(self) -> BattleSessionResult:
        """Run one configured challenge and battle session."""


ConnectionFactory = Callable[[ChallengeConfig], BattleConnection]
CoordinatorFactory = Callable[
    [BattleConnection, ChallengeConfig, PackedTeam],
    ChallengeCoordinator,
]
RunnerFactory = Callable[[], ChallengeCommandRunner]


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        del message
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: invalid command-line arguments\n")


class ChallengeRunner:
    """Compose the connection and coordinator after local validation."""

    def __init__(
        self,
        *,
        connection_factory: ConnectionFactory | None = None,
        coordinator_factory: CoordinatorFactory | None = None,
    ) -> None:
        self._connection_factory = connection_factory or _create_connection
        self._coordinator_factory = coordinator_factory or _create_coordinator

    async def run(
        self,
        config: ChallengeConfig,
        team: PackedTeam,
    ) -> BattleSessionResult:
        connection = self._connection_factory(config)
        coordinator = self._coordinator_factory(connection, config, team)
        return await coordinator.run()


_CLASSIFIED_RUNTIME_ERRORS = (
    Disconnect,
    LocalActionGateRejection,
    MalformedProtocolMessage,
    NoLegalActionError,
    ReducerInvariantFailure,
    RequestStateReconciliationMismatch,
    ServerInvalidChoice,
    ServerUnavailableChoice,
    StaleRequestIdentity,
    TeamValidationError,
    TimerOrForfeit,
    TransportTimeout,
    UnknownProtocolEvent,
)


def build_parser() -> argparse.ArgumentParser:
    parser = _SafeArgumentParser(prog="battlebelief")
    parser.add_argument("--version", action="store_true")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor", help="report package readiness")
    challenge = subparsers.add_parser(
        "challenge",
        help="start an outgoing direct challenge; the opponent must accept",
        description=(
            "Start an outgoing direct challenge for Gen 9 OU. "
            "The opponent must accept before the battle starts."
        ),
    )
    challenge.add_argument("--username", required=True)
    challenge.add_argument("--opponent", required=True)
    challenge.add_argument("--team", required=True, type=Path)
    challenge.add_argument("--server-url", default=DEFAULT_SERVER_URL)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    environment: Mapping[str, str] | None = None,
    runner_factory: RunnerFactory | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        print(runtime_status()["version"])
        return 0
    if args.command == "doctor":
        print(json.dumps(runtime_status(), sort_keys=True, separators=(",", ":")))
        return 0
    if args.command != "challenge":
        build_parser().print_help()
        return 0

    active_environment = os.environ if environment is None else environment
    try:
        config = load_challenge_config(
            username=args.username,
            opponent=args.opponent,
            team_path=args.team,
            server_url=args.server_url,
            environment=active_environment,
        )
        team = _read_team(config.team_path)
    except ChallengeConfigError as exc:
        print(exc.public_message, file=sys.stderr)
        return 2
    except TeamValidationError:
        print("team_validation_error: selected team is invalid", file=sys.stderr)
        return 2

    factory = runner_factory or ChallengeRunner
    try:
        result = asyncio.run(factory().run(config, team))
    except Exception as exc:
        print(_runtime_error_code(exc), file=sys.stderr)
        return 1

    if result.primary_error is not None:
        print(_runtime_error_code(result.primary_error), file=sys.stderr)
        return 1
    return 0


def _read_team(path: Path) -> PackedTeam:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        raise ChallengeConfigError("config_error: team file could not be read") from exc
    return load_packed_team(text)


def _create_connection(config: ChallengeConfig) -> BattleConnection:
    return ShowdownConnection(
        url=config.server_url,
        username=config.username,
        password=config.password,
        assertion_provider=ShowdownAssertionProvider(),
    )


def _create_coordinator(
    connection: BattleConnection,
    config: ChallengeConfig,
    team: PackedTeam,
) -> ChallengeCoordinator:
    return BattleCoordinator(
        connection=connection,
        our_user_id=config.username,
        opponent_display=config.opponent,
        team=team,
        setup_timeout=config.setup_timeout,
    )


def _runtime_error_code(error: BaseException) -> str:
    if isinstance(error, ChallengeSetupError):
        return f"{error.code}:{error.subcode}"
    if isinstance(error, _CLASSIFIED_RUNTIME_ERRORS):
        return error.code
    return "runtime_error"


if __name__ == "__main__":
    raise SystemExit(main())
