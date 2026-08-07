from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal, cast

import pytest

from battlebelief_core.domain.engine_capabilities import CapabilityCatalog, CapabilityDefinition
from battlebelief_core.domain.search import (
    InformationStateKey,
    PlayerView,
    PreparedRootIdentity,
    PreparedWorld,
    SearchAction,
    TransitionOutcome,
    TransitionSuccessor,
    TransitionWork,
)
from battlebelief_core.ports.transition_model import ActionT, EngineBackendHealth, TransitionModel


def _digest(letter: str) -> str:
    return f"sha256:{letter * 64}"


@dataclass(frozen=True, slots=True)
class _FakeWorld:
    terminal: bool = False
    tie: bool = False
    private_opponent_world: str = ""


class FakeTransitionModel:
    backend_identity_digest = _digest("a")
    backend_health = EngineBackendHealth.HEALTHY

    def __init__(self) -> None:
        self.catalog = CapabilityCatalog.create(
            catalog_id="gen9-ou-v1",
            catalog_version="1",
            capability_contract_digest=_digest("0"),
            canonicalization_contract_digest=_digest("e"),
            definitions=(
                CapabilityDefinition(value="gen9.battle.damage", description="Damage resolution."),
            ),
        )
        self.required = (self.catalog.id_for("gen9.battle.damage"),)

    def prepare_root(
        self,
        world: _FakeWorld,
        *,
        root_identity: PreparedRootIdentity,
        root_actions: tuple[SearchAction, ...],
    ) -> PreparedWorld[_FakeWorld]:
        return PreparedWorld(
            _opaque=world,
            root_identity=root_identity,
            root_actions=root_actions,
            required_capabilities=self.required,
        )

    def player_view(self, world: PreparedWorld[_FakeWorld], player: str) -> PlayerView:
        del world
        if player not in {"p1", "p2"}:
            raise ValueError("invalid player")
        return PlayerView(
            player=cast(Literal["p1", "p2"], player),
            view_digest=_digest("c" if player == "p1" else "d"),
        )

    def information_state_key(self, view: PlayerView) -> InformationStateKey:
        return InformationStateKey(player=view.player, information_state_digest=view.view_digest)

    def legal_actions(
        self, world: PreparedWorld[_FakeWorld], player: str
    ) -> tuple[SearchAction, ...]:
        if player not in {"p1", "p2"}:
            raise ValueError("invalid player")
        return world.root_actions

    def transition(
        self,
        world: PreparedWorld[_FakeWorld],
        p1_action: SearchAction,
        p2_action: SearchAction,
    ) -> TransitionOutcome[_FakeWorld]:
        assert p1_action.kind == "move" and p2_action.kind == "move"
        return TransitionOutcome(
            successors=(TransitionSuccessor("only.outcome", world, 1),),
            probability_denominator=1,
            work=TransitionWork(units=1),
            required_capabilities=self.required,
        )

    def is_terminal(self, world: PreparedWorld[_FakeWorld]) -> bool:
        return world._opaque.terminal

    def terminal_value(self, world: PreparedWorld[_FakeWorld], player: str) -> Fraction | None:
        if player not in {"p1", "p2"}:
            raise ValueError("invalid player")
        if not self.is_terminal(world):
            return None
        if world._opaque.tie:
            return Fraction(0)
        if player == "p1":
            return Fraction(1)
        return Fraction(-1)


_TRANSITION_MODEL_CONFORMANCE: TransitionModel[_FakeWorld, SearchAction] = FakeTransitionModel()


def _root() -> PreparedRootIdentity:
    return PreparedRootIdentity.create(
        request_identity_digest=_digest("1"),
        safe_submission_set_digest=_digest("2"),
        observed_state_digest=_digest("3"),
        root_player="p1",
        ruleset_digest=_digest("4"),
        backend_identity_digest=_digest("a"),
        capability_catalog_digest=FakeTransitionModel().catalog.catalog_digest,
    )


def _root_actions(
    root: PreparedRootIdentity, model: FakeTransitionModel
) -> tuple[SearchAction, ...]:
    return (
        SearchAction(
            action_id="root.move",
            kind="move",
            required_capabilities=model.required,
            root_submission_index=0,
            root_identity=root,
        ),
    )


def test_fake_conforms_and_requires_joint_actions() -> None:
    model = FakeTransitionModel()
    root = _root()
    root_actions = _root_actions(root, model)
    prepared = model.prepare_root(_FakeWorld(), root_identity=root, root_actions=root_actions)
    p1_action = model.legal_actions(prepared, "p1")[0]
    p2_action = model.legal_actions(prepared, "p2")[0]
    outcome = model.transition(prepared, p1_action, p2_action)

    assert outcome.successors[0].world is prepared
    assert prepared.root_identity is root
    assert model.information_state_key(
        model.player_view(prepared, "p1")
    ) == model.information_state_key(model.player_view(prepared, "p1"))
    assert model.legal_actions(prepared, "p1") == model.legal_actions(prepared, "p1")
    assert model.terminal_value(prepared, "p1") is None
    assert model.terminal_value(
        model.prepare_root(
            _FakeWorld(terminal=True), root_identity=root, root_actions=root_actions
        ),
        "p2",
    ) == Fraction(-1)
    assert outcome.work.units > 0
    with pytest.raises(ValueError):
        model.player_view(prepared, "p3")
    with pytest.raises(ValueError):
        model.legal_actions(prepared, "p3")
    with pytest.raises(ValueError):
        model.terminal_value(prepared, "p3")


def test_player_information_alone_determines_key_and_legal_actions() -> None:
    model = FakeTransitionModel()
    root = _root()
    root_actions = _root_actions(root, model)
    first = model.prepare_root(
        _FakeWorld(private_opponent_world="alpha"), root_identity=root, root_actions=root_actions
    )
    second = model.prepare_root(
        _FakeWorld(private_opponent_world="beta"), root_identity=root, root_actions=root_actions
    )

    first_view = model.player_view(first, "p1")
    second_view = model.player_view(second, "p1")

    assert first_view == second_view
    assert model.information_state_key(first_view) == model.information_state_key(second_view)
    assert model.legal_actions(first, "p1") == model.legal_actions(second, "p1")
    assert model.legal_actions(first, "p1") is first.root_actions


@pytest.mark.parametrize(
    ("world", "player", "expected"),
    [
        (_FakeWorld(terminal=True), "p1", Fraction(1)),
        (_FakeWorld(terminal=True), "p2", Fraction(-1)),
        (_FakeWorld(terminal=True, tie=True), "p1", Fraction(0)),
        (_FakeWorld(), "p1", None),
    ],
)
def test_terminal_values_are_defined_only_for_terminal_worlds(
    world: _FakeWorld, player: str, expected: Fraction | None
) -> None:
    model = FakeTransitionModel()
    root = _root()
    prepared = model.prepare_root(
        world, root_identity=root, root_actions=_root_actions(root, model)
    )

    assert model.terminal_value(prepared, player) == expected


def test_port_rejects_free_backend_health_and_non_search_action_type() -> None:
    assert FakeTransitionModel.backend_health is EngineBackendHealth.HEALTHY
    assert EngineBackendHealth("unhealthy") is EngineBackendHealth.UNHEALTHY
    assert ActionT.__bound__ is SearchAction
    with pytest.raises(ValueError):
        EngineBackendHealth("free-form-health")
