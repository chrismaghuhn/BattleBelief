from __future__ import annotations

import textwrap
from pathlib import Path

from mypy import api as mypy_api

_VALID_FIXTURE = """
from fractions import Fraction
from typing import Literal

from battlebelief_core.domain.search import (
    InformationStateKey,
    PlayerView,
    PreparedRootIdentity,
    PreparedWorld,
    SearchAction,
    TransitionOutcome,
)
from battlebelief_core.ports.transition_model import EngineBackendHealth, TransitionModel


class ValidTransitionModel:
    @property
    def backend_identity_digest(self) -> str:
        return "sha256:" + "a" * 64

    @property
    def backend_health(self) -> EngineBackendHealth:
        return EngineBackendHealth.HEALTHY

    def prepare_root(
        self,
        world: object,
        *,
        root_identity: PreparedRootIdentity,
        root_actions: tuple[SearchAction, ...],
    ) -> PreparedWorld[object]:
        raise NotImplementedError

    def player_view(
        self, world: PreparedWorld[object], player: Literal["p1", "p2"]
    ) -> PlayerView:
        raise NotImplementedError

    def information_state_key(self, view: PlayerView) -> InformationStateKey:
        raise NotImplementedError

    def legal_actions(
        self, world: PreparedWorld[object], player: Literal["p1", "p2"]
    ) -> tuple[SearchAction, ...]:
        raise NotImplementedError

    def transition(
        self,
        world: PreparedWorld[object],
        p1_action: SearchAction,
        p2_action: SearchAction,
    ) -> TransitionOutcome[object]:
        raise NotImplementedError

    def is_terminal(self, world: PreparedWorld[object]) -> bool:
        raise NotImplementedError

    def terminal_value(
        self, world: PreparedWorld[object], player: Literal["p1", "p2"]
    ) -> Fraction | None:
        raise NotImplementedError


def accept(model: TransitionModel[object, SearchAction]) -> None:
    pass


accept(ValidTransitionModel())
"""

_INVALID_FIXTURE = (
    _VALID_FIXTURE.replace("class ValidTransitionModel:", "class InvalidTransitionModel:")
    .replace("def backend_health(self) -> EngineBackendHealth:", "def backend_health(self) -> str:")
    .replace("return EngineBackendHealth.HEALTHY", 'return "healthy"')
    .replace("root_actions: tuple[SearchAction, ...]", "root_actions: tuple[str, ...]")
    .replace(") -> tuple[SearchAction, ...]:", ") -> tuple[str, ...]:")
    .replace("p1_action: SearchAction,", "p1_action: str,")
    .replace("p2_action: SearchAction,", "p2_action: str,")
    .replace("accept(ValidTransitionModel())", "accept(InvalidTransitionModel())")
)


def _run_mypy(fixture_path: Path) -> tuple[str, str, int]:
    repository = Path(__file__).resolve().parents[2]
    return mypy_api.run(
        [
            "--config-file",
            str(repository / "pyproject.toml"),
            "--no-incremental",
            "--cache-dir",
            str(fixture_path.parent / "mypy-cache"),
            str(fixture_path),
        ]
    )


def test_transition_model_protocol_accepts_only_the_frozen_public_contract(
    tmp_path: Path,
) -> None:
    valid_fixture = tmp_path / "valid_transition_model.py"
    invalid_fixture = tmp_path / "invalid_transition_model.py"
    valid_fixture.write_text(textwrap.dedent(_VALID_FIXTURE), encoding="utf-8")
    invalid_fixture.write_text(textwrap.dedent(_INVALID_FIXTURE), encoding="utf-8")

    valid_stdout, valid_stderr, valid_status = _run_mypy(valid_fixture)
    invalid_stdout, invalid_stderr, invalid_status = _run_mypy(invalid_fixture)

    assert valid_status == 0, valid_stdout + valid_stderr
    assert invalid_status == 1
    diagnostic = invalid_stdout + invalid_stderr
    assert "InvalidTransitionModel" in diagnostic
    assert "TransitionModel" in diagnostic
    assert 'expected "EngineBackendHealth", got "str"' in diagnostic
    assert "tuple[SearchAction, ...]" in diagnostic
    assert "tuple[str, ...]" in diagnostic
