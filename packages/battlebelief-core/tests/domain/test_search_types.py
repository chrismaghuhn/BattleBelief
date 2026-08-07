from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import pytest

from battlebelief_core.canonicalization import manifest_digest
from battlebelief_core.domain.engine_capabilities import (
    CapabilityCatalog,
    CapabilityDefinition,
)
from battlebelief_core.domain.search import (
    InformationStateKey,
    PlayerView,
    PreparedRootIdentity,
    PreparedWorld,
    SearchAction,
    TransitionOutcome,
    TransitionSuccessor,
    TransitionWork,
    WorldDistributionIdentity,
)


@dataclass(frozen=True, slots=True)
class _FrozenWorld:
    terminal: bool = False
    private_marker: str = "hidden-opponent-set"


def _digest(letter: str) -> str:
    return f"sha256:{letter * 64}"


def _catalog(version: str = "1") -> CapabilityCatalog:
    return CapabilityCatalog.create(
        catalog_id="gen9-ou-v1",
        catalog_version=version,
        capability_contract_digest=_digest("0"),
        canonicalization_contract_digest=_digest("e"),
        definitions=(
            CapabilityDefinition(value="gen9.battle.damage", description="Damage resolution."),
            CapabilityDefinition(
                value="gen9.transition.order.speed", description="Speed-based ordering."
            ),
        ),
    )


def _root() -> PreparedRootIdentity:
    return PreparedRootIdentity.create(
        request_identity_digest=_digest("1"),
        safe_submission_set_digest=_digest("2"),
        observed_state_digest=_digest("3"),
        root_player="p1",
        ruleset_digest=_digest("4"),
        backend_identity_digest=_digest("5"),
        capability_catalog_digest=_catalog().catalog_digest,
    )


class TestPreparedSearchValues:
    def test_root_digest_is_canonical_and_contains_no_world(self) -> None:
        root = _root()
        same = _root()

        assert root == same
        assert "capability_catalog_digest" not in repr(root)
        assert root.prepared_root_digest == same.prepared_root_digest
        with pytest.raises(TypeError):
            PreparedRootIdentity()  # type: ignore[call-arg]
        for field, replacement in {
            "request_identity_digest": _digest("f"),
            "safe_submission_set_digest": _digest("f"),
            "observed_state_digest": _digest("f"),
            "root_player": "p2",
            "ruleset_digest": _digest("f"),
            "backend_identity_digest": _digest("f"),
            "capability_catalog_digest": _catalog("2").catalog_digest,
        }.items():
            kwargs = {
                "request_identity_digest": _digest("1"),
                "safe_submission_set_digest": _digest("2"),
                "observed_state_digest": _digest("3"),
                "root_player": "p1",
                "ruleset_digest": _digest("4"),
                "backend_identity_digest": _digest("5"),
                "capability_catalog_digest": _catalog().catalog_digest,
            }
            kwargs[field] = replacement
            assert (
                PreparedRootIdentity.create(**kwargs).prepared_root_digest
                != root.prepared_root_digest
            )  # type: ignore[arg-type]

    def test_root_world_and_root_action_preserve_identity(self) -> None:
        catalog = _catalog()
        root = _root()
        required = (catalog.id_for("gen9.battle.damage"),)
        action = SearchAction(
            action_id="private.native-choice",
            kind="move",
            required_capabilities=required,
            root_submission_index=0,
            root_identity=root,
        )
        prepared = PreparedWorld(
            _opaque=_FrozenWorld(private_marker="secret"),
            root_identity=root,
            root_actions=(action,),
            required_capabilities=required,
        )

        assert prepared.root_identity is root
        assert "secret" not in repr(prepared)
        assert not hasattr(prepared, "world")
        assert "secret" not in str(prepared.public_summary())
        assert "secret" not in manifest_digest(prepared.public_summary())
        assert "private.native-choice" not in repr(action)
        assert "private.native-choice" not in str(action.public_summary())
        assert (
            SearchAction(
                action_id="hidden.deep", kind="move", required_capabilities=required
            ).root_identity
            is None
        )
        with pytest.raises(ValueError):
            SearchAction(
                action_id="private marker",
                kind="move",
                required_capabilities=required,
                root_submission_index=0,
            )

    def test_prepared_world_is_an_opaque_identity_handle(self) -> None:
        root = _root()
        private_a = _FrozenWorld(private_marker="alpha")
        private_b = _FrozenWorld(private_marker="beta")
        first = PreparedWorld(
            _opaque=private_a, root_identity=root, root_actions=(), required_capabilities=()
        )
        second = PreparedWorld(
            _opaque=private_b, root_identity=root, root_actions=(), required_capabilities=()
        )

        assert first != second
        assert hash(first) != hash(second)
        assert "alpha" not in repr(first)
        with pytest.raises(ValueError) as error:
            PreparedWorld(
                _opaque={"hidden": "x"},
                root_identity=root,
                root_actions=(),
                required_capabilities=(),
            )
        assert "hidden" not in str(error.value)
        with pytest.raises(ValueError):
            PreparedWorld(
                _opaque=["hidden"], root_identity=root, root_actions=(), required_capabilities=()
            )
        with pytest.raises(ValueError):
            PreparedWorld(
                _opaque={"hidden"}, root_identity=root, root_actions=(), required_capabilities=()
            )
        with pytest.raises(ValueError):
            PreparedWorld(
                _opaque=bytearray(b"hidden"),
                root_identity=root,
                root_actions=(),
                required_capabilities=(),
            )
        nested_private = ["hidden"]
        with pytest.raises(ValueError) as error:
            PreparedWorld(
                _opaque=(nested_private,),
                root_identity=root,
                root_actions=(),
                required_capabilities=(),
            )
        assert "hidden" not in str(error.value)
        with pytest.raises(ValueError):
            other_root = PreparedRootIdentity.create(
                request_identity_digest=_digest("f"),
                safe_submission_set_digest=_digest("2"),
                observed_state_digest=_digest("3"),
                root_player="p1",
                ruleset_digest=_digest("4"),
                backend_identity_digest=_digest("5"),
                capability_catalog_digest=_catalog().catalog_digest,
            )
            PreparedWorld(
                _opaque=_FrozenWorld(),
                root_identity=root,
                root_actions=(SearchAction("wrong.root", "move", (), 0, other_root),),
                required_capabilities=(),
            )

    def test_root_action_set_is_immutable_contiguous_and_bound_to_the_root(self) -> None:
        catalog = _catalog()
        root = _root()
        capability = catalog.id_for("gen9.battle.damage")
        first = SearchAction("root.a", "move", (capability,), 0, root)
        second = SearchAction("root.b", "move", (capability,), 1, root)
        prepared = PreparedWorld(
            _opaque=_FrozenWorld(),
            root_identity=root,
            root_actions=(first, second),
            required_capabilities=(capability,),
        )

        assert prepared.root_actions == (first, second)
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            prepared.root_actions = ()  # type: ignore[misc]
        with pytest.raises(ValueError):
            PreparedWorld(
                _opaque=_FrozenWorld(),
                root_identity=root,
                root_actions=(second, first),
                required_capabilities=(),
            )
        with pytest.raises(ValueError):
            PreparedWorld(
                _opaque=_FrozenWorld(),
                root_identity=root,
                root_actions=(SearchAction("deep.action", "move"),),
                required_capabilities=(),
            )

    def test_player_views_and_information_keys_are_player_bound_and_private(self) -> None:
        view = PlayerView(player="p1", view_digest=_digest("b"))
        key = InformationStateKey(player="p1", information_state_digest=_digest("c"))

        assert "sha256:" not in repr(view)
        assert "sha256:" not in repr(key)
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            view.player = "p2"  # type: ignore[misc]


class TestTransitionOutcome:
    def test_successor_root_actions_must_match_the_source_world(self) -> None:
        root = _root()
        source_action = SearchAction(
            action_id="root.source", kind="move", root_submission_index=0, root_identity=root
        )
        source = PreparedWorld(
            _opaque=_FrozenWorld(),
            root_identity=root,
            root_actions=(source_action,),
            required_capabilities=(),
        )
        matching = TransitionOutcome(
            successors=(TransitionSuccessor("outcome.match", source, 1),),
            probability_denominator=1,
            work=TransitionWork(1),
            required_capabilities=(),
        )
        matching.validate_against_source(source)

        substituted_action = SearchAction(
            action_id="root.substituted",
            kind="move",
            root_submission_index=0,
            root_identity=root,
        )
        substituted_successor = PreparedWorld(
            _opaque=_FrozenWorld(),
            root_identity=root,
            root_actions=(substituted_action,),
            required_capabilities=(),
        )
        substituted = TransitionOutcome(
            successors=(
                TransitionSuccessor("outcome.match", source, 1),
                TransitionSuccessor("outcome.substituted", substituted_successor, 1),
            ),
            probability_denominator=2,
            work=TransitionWork(1),
            required_capabilities=(),
        )

        with pytest.raises(ValueError, match="root action"):
            substituted.validate_against_source(source)

    def test_validates_canonical_probability_distribution_and_hides_ids(self) -> None:
        catalog = _catalog()
        outcome = TransitionOutcome(
            successors=(
                TransitionSuccessor(
                    outcome_id="chance.a",
                    world=PreparedWorld(_FrozenWorld(private_marker="a"), _root(), (), ()),
                    probability_numerator=1,
                ),
                TransitionSuccessor(
                    outcome_id="chance.b",
                    world=PreparedWorld(_FrozenWorld(private_marker="b"), _root(), (), ()),
                    probability_numerator=2,
                ),
            ),
            probability_denominator=3,
            work=TransitionWork(units=2),
            required_capabilities=(catalog.id_for("gen9.battle.damage"),),
        )

        assert outcome.work.units == 2
        assert "chance.a" not in repr(outcome)
        assert "hidden" not in repr(outcome)
        assert "chance.a" not in str(outcome.public_summary())
        assert "hidden" not in str(outcome.public_summary())
        with pytest.raises(ValueError) as error:
            TransitionOutcome(
                successors=(
                    TransitionSuccessor(
                        outcome_id="private.b",
                        world=PreparedWorld(None, _root(), (), ()),
                        probability_numerator=1,
                    ),
                    TransitionSuccessor(
                        outcome_id="private.a",
                        world=PreparedWorld(None, _root(), (), ()),
                        probability_numerator=1,
                    ),
                ),
                probability_denominator=2,
                work=TransitionWork(units=1),
                required_capabilities=(),
            )
        assert "private." not in str(error.value)

    def test_mixed_catalog_capabilities_fail_closed(self) -> None:
        root = _root()
        local = _catalog().id_for("gen9.battle.damage")
        foreign = _catalog("2").id_for("gen9.battle.damage")

        with pytest.raises(ValueError):
            PreparedWorld(
                _opaque=None, root_identity=root, root_actions=(), required_capabilities=(foreign,)
            )
        with pytest.raises(ValueError):
            SearchAction(
                action_id="private.action", kind="move", required_capabilities=(local, foreign)
            )
        with pytest.raises(ValueError):
            TransitionOutcome(
                successors=(
                    TransitionSuccessor("private.outcome", PreparedWorld(None, root, (), ()), 1),
                ),
                probability_denominator=1,
                work=TransitionWork(1),
                required_capabilities=(local, foreign),
            )

    def test_outcome_capabilities_must_be_preflight_subset(self) -> None:
        catalog = _catalog()
        capability = catalog.id_for("gen9.battle.damage")
        outcome = TransitionOutcome(
            successors=(TransitionSuccessor("outcome.a", PreparedWorld(None, _root(), (), ()), 1),),
            probability_denominator=1,
            work=TransitionWork(1),
            required_capabilities=(capability,),
        )

        outcome.require_preflight_subset((capability,))
        with pytest.raises(ValueError):
            outcome.require_preflight_subset(())
        with pytest.raises(ValueError):
            outcome.require_preflight_subset((_catalog("2").id_for("gen9.battle.damage"),))

    def test_successor_world_capabilities_must_be_preflight_subset(self) -> None:
        catalog = _catalog()
        preflight_capability = catalog.id_for("gen9.battle.damage")
        unpreflighted_capability = catalog.id_for("gen9.transition.order.speed")
        root = _root()
        source = PreparedWorld(
            _opaque=_FrozenWorld(),
            root_identity=root,
            root_actions=(),
            required_capabilities=(preflight_capability,),
        )
        successor = PreparedWorld(
            _opaque=_FrozenWorld(),
            root_identity=root,
            root_actions=(),
            required_capabilities=(unpreflighted_capability,),
        )
        outcome = TransitionOutcome(
            successors=(TransitionSuccessor("outcome.a", successor, 1),),
            probability_denominator=1,
            work=TransitionWork(1),
            required_capabilities=(preflight_capability,),
        )

        outcome.validate_against_source(source)
        outcome.require_preflight_subset((preflight_capability, unpreflighted_capability))
        with pytest.raises(ValueError, match="unpreflighted capability"):
            outcome.require_preflight_subset((preflight_capability,))

    def test_transition_work_addition_is_deterministic(self) -> None:
        assert TransitionWork(2) + TransitionWork(3) == TransitionWork(5)

    def test_distribution_identity_is_generic_and_has_only_approved_fields(self) -> None:
        identity = WorldDistributionIdentity(
            distribution_id="closed.world-eval",
            version="1",
            digest=_digest("1"),
            generation=9,
            format="gen9ou",
            ruleset_digest=_digest("2"),
            public_evidence_digest=_digest("3"),
            support_digest=_digest("4"),
            support_count=2,
            availability_status="available",
        )

        assert identity.support_count == 2
        assert not hasattr(identity, "worlds")
