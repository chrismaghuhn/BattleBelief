from __future__ import annotations

from fractions import Fraction
from typing import assert_type

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
from battlebelief_core.ports.transition_model import TransitionModel


def _digest(letter: str) -> str:
    return f"sha256:{letter * 64}"


class FakeTransitionModel:
    backend_identity_digest = _digest("a")
    backend_health = "healthy"

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
        self, world: dict[str, object], root_identity: PreparedRootIdentity
    ) -> PreparedWorld[dict[str, object]]:
        return PreparedWorld(
            world=world, root_identity=root_identity, required_capabilities=self.required
        )

    def player_view(self, world: PreparedWorld[dict[str, object]], player: str) -> PlayerView:
        del world
        if player not in {"p1", "p2"}:
            raise ValueError("invalid player")
        return PlayerView(player=player, view_digest=_digest("c" if player == "p1" else "d"))

    def information_state_key(self, view: PlayerView) -> InformationStateKey:
        return InformationStateKey(player=view.player, information_state_digest=view.view_digest)

    def legal_actions(
        self, world: PreparedWorld[dict[str, object]], player: str
    ) -> tuple[SearchAction, ...]:
        del world
        if player not in {"p1", "p2"}:
            raise ValueError("invalid player")
        return (
            SearchAction(
                action_id=f"{player}.move", kind="move", required_capabilities=self.required
            ),
        )

    def transition(
        self,
        world: PreparedWorld[dict[str, object]],
        p1_action: SearchAction,
        p2_action: SearchAction,
    ) -> TransitionOutcome[dict[str, object]]:
        assert p1_action.kind == "move" and p2_action.kind == "move"
        return TransitionOutcome(
            successors=(TransitionSuccessor("only.outcome", world, 1),),
            probability_denominator=1,
            work=TransitionWork(units=1),
            required_capabilities=self.required,
        )

    def is_terminal(self, world: PreparedWorld[dict[str, object]]) -> bool:
        return bool(world.world.get("terminal"))

    def terminal_value(
        self, world: PreparedWorld[dict[str, object]], player: str
    ) -> Fraction | None:
        if player not in {"p1", "p2"}:
            raise ValueError("invalid player")
        if not self.is_terminal(world):
            return None
        if world.world.get("tie"):
            return Fraction(0)
        if player == "p1":
            return Fraction(1)
        return Fraction(-1)


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


def test_fake_conforms_and_requires_joint_actions() -> None:
    model = FakeTransitionModel()
    assert_type(model, TransitionModel[dict[str, object], SearchAction])
    root = _root()
    prepared = model.prepare_root({"terminal": False}, root)
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
    assert model.terminal_value(model.prepare_root({"terminal": True}, root), "p2") == Fraction(-1)
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
    first = model.prepare_root({"private_opponent_world": "alpha"}, root)
    second = model.prepare_root({"private_opponent_world": "beta"}, root)

    first_view = model.player_view(first, "p1")
    second_view = model.player_view(second, "p1")

    assert first_view == second_view
    assert model.information_state_key(first_view) == model.information_state_key(second_view)
    assert model.legal_actions(first, "p1") == model.legal_actions(second, "p1")


@pytest.mark.parametrize(
    ("world", "player", "expected"),
    [
        ({"terminal": True}, "p1", Fraction(1)),
        ({"terminal": True}, "p2", Fraction(-1)),
        ({"terminal": True, "tie": True}, "p1", Fraction(0)),
        ({"terminal": False}, "p1", None),
    ],
)
def test_terminal_values_are_defined_only_for_terminal_worlds(
    world: dict[str, object], player: str, expected: Fraction | None
) -> None:
    model = FakeTransitionModel()
    prepared = model.prepare_root(world, _root())

    assert model.terminal_value(prepared, player) == expected
