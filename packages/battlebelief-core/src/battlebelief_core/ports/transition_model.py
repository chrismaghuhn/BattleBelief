"""Pure transition-model port for opaque hypothetical worlds."""

from __future__ import annotations

from fractions import Fraction
from typing import Literal, Protocol, TypeVar, runtime_checkable

from battlebelief_core.domain.search import (
    InformationStateKey,
    PlayerView,
    PreparedRootIdentity,
    PreparedWorld,
    TransitionOutcome,
)

WorldT = TypeVar("WorldT")
ActionT = TypeVar("ActionT")


@runtime_checkable
class TransitionModel(Protocol[WorldT, ActionT]):
    """Backend-neutral transition capabilities consumed by search."""

    @property
    def backend_identity_digest(self) -> str: ...

    @property
    def backend_health(self) -> str: ...

    def prepare_root(
        self, world: WorldT, root_identity: PreparedRootIdentity
    ) -> PreparedWorld[WorldT]: ...

    def player_view(
        self, world: PreparedWorld[WorldT], player: Literal["p1", "p2"]
    ) -> PlayerView: ...

    def information_state_key(self, view: PlayerView) -> InformationStateKey: ...

    def legal_actions(
        self, world: PreparedWorld[WorldT], player: Literal["p1", "p2"]
    ) -> tuple[ActionT, ...]: ...

    def transition(
        self, world: PreparedWorld[WorldT], p1_action: ActionT, p2_action: ActionT
    ) -> TransitionOutcome[WorldT]: ...

    def is_terminal(self, world: PreparedWorld[WorldT]) -> bool: ...

    def terminal_value(
        self, world: PreparedWorld[WorldT], player: Literal["p1", "p2"]
    ) -> Fraction | None: ...


__all__ = ["ActionT", "TransitionModel", "WorldT"]
