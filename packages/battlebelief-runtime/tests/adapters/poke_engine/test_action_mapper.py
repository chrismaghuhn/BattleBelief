from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from battlebelief_core.domain.actions import ActionKind, BattleSubmission, SafeSubmissionSet
from battlebelief_core.domain.search import PreparedRootIdentity, SearchAction
from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_runtime.adapters.poke_engine import (
    PokeEngineMappingFailure,
    PokeEngineTransitionModel,
)
from battlebelief_runtime.adapters.poke_engine.artifact import RuntimeEnvironment
from battlebelief_runtime.adapters.poke_engine.transition_model import _load_catalog

_FIXTURES = Path(__file__).parents[2] / "fixtures" / "poke_engine"
_RULESET = "sha256:" + "4" * 64


def _doc(name: str) -> dict[str, object]:
    value = json.loads((_FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _model() -> PokeEngineTransitionModel:
    return PokeEngineTransitionModel(
        catalog=_load_catalog(),
        _artifact_environment=RuntimeEnvironment(
            "windows-2025", "x86_64", "cp314", "none", "win_amd64"
        ),
    )


def _observed() -> ObservedState:
    return replace(
        ObservedState.initial("ash"),
        room_initialized=True,
        generation=9,
        game_type="singles",
        tier="gen9ou",
        battle_started=True,
        our_side="p1",
        turn=1,
    )


def _prepared(model: PokeEngineTransitionModel, *, world: dict[str, object] | None = None):
    return model.prepare_battle_root(
        observed_state=_observed(),
        safe_submissions=model.safe_submissions_from_document(_doc("observed_root_mapping.json")),
        complete_world=_doc("complete_world_mapping.json") if world is None else world,
        ruleset_digest=_RULESET,
    )


def test_root_actions_preserve_safe_set_order_index_and_submission_identity() -> None:
    model = _model()
    prepared = _prepared(model)

    assert [action.root_submission_index for action in prepared.root_actions] == [0, 1, 2, 3, 4]
    assert [action.kind for action in prepared.root_actions] == [
        "move",
        "move",
        "switch",
        "move",
        "move",
    ]
    submissions = tuple(model.root_submission(prepared, action) for action in prepared.root_actions)
    assert (
        submissions
        == model.safe_submissions_from_document(_doc("observed_root_mapping.json")).submissions
    )
    assert all(action.root_identity is prepared.root_identity for action in prepared.root_actions)


def test_root_actions_never_adopt_native_order_or_extra_choices() -> None:
    model = _model()
    safe = model.safe_submissions_from_document(_doc("observed_root_mapping.json"))
    reversed_safe = SafeSubmissionSet(
        request_identity=safe.request_identity,
        submissions=tuple(reversed(safe.submissions)),
    )
    prepared = model.prepare_battle_root(
        observed_state=_observed(),
        safe_submissions=reversed_safe,
        complete_world=_doc("complete_world_mapping.json"),
        ruleset_digest=_RULESET,
    )

    assert tuple(model.root_submission(prepared, action) for action in prepared.root_actions) == (
        reversed_safe.submissions
    )
    assert len(prepared.root_actions) == len(reversed_safe.submissions)


def test_deep_move_switch_and_tera_are_engine_neutral_catalog_actions() -> None:
    model = _model()
    prepared = _prepared(model)
    actions = model.legal_actions(prepared, "p2")

    assert actions
    assert all(isinstance(action, SearchAction) for action in actions)
    assert all(action.root_identity is None for action in actions)
    assert {action.kind for action in actions} >= {"move", "switch"}
    assert any(
        "gen9.legality.terastallization.activation"
        in {capability.value for capability in action.required_capabilities}
        for action in actions
    )
    assert "tackle" not in repr(actions)


def test_forced_switch_maps_only_switch_actions_with_forced_capability() -> None:
    model = _model()
    world = _doc("complete_world_mapping.json")
    world["sides"]["p2"]["force_switch"] = True  # type: ignore[index]
    prepared = _prepared(model, world=world)

    actions = model.legal_actions(prepared, "p2")
    assert actions and {action.kind for action in actions} == {"switch"}
    assert all(
        "gen9.legality.switch.forced"
        in {capability.value for capability in action.required_capabilities}
        for action in actions
    )


def test_stale_safe_set_and_unknown_root_submission_fail_closed() -> None:
    model = _model()
    safe = model.safe_submissions_from_document(_doc("observed_root_mapping.json"))
    illegal = BattleSubmission(
        kind=ActionKind.MOVE,
        provenance=safe.submissions[0].provenance,
        slot=4,
        move_id="recover",
    )

    with pytest.raises(PokeEngineMappingFailure) as caught:
        model.prepare_battle_root(
            observed_state=_observed(),
            safe_submissions=SafeSubmissionSet(safe.request_identity, (*safe.submissions, illegal)),
            complete_world=_doc("complete_world_mapping.json"),
            ruleset_digest=_RULESET,
        )

    assert caught.value.failure_class == "safe_submission_mismatch"


def test_root_move_identity_must_match_its_authoritative_request_slot() -> None:
    model = _model()
    safe = model.safe_submissions_from_document(_doc("observed_root_mapping.json"))
    wrong_slot = BattleSubmission(
        kind=ActionKind.MOVE,
        provenance=safe.submissions[0].provenance,
        slot=2,
        move_id="tackle",
    )

    with pytest.raises(PokeEngineMappingFailure) as caught:
        model.prepare_battle_root(
            observed_state=_observed(),
            safe_submissions=SafeSubmissionSet(
                safe.request_identity, (wrong_slot, *safe.submissions[1:])
            ),
            complete_world=_doc("complete_world_mapping.json"),
            ruleset_digest=_RULESET,
        )

    assert caught.value.failure_class == "safe_submission_mismatch"
    assert caught.value.work_units == 0


def test_distinct_safe_submissions_cannot_share_one_native_root_choice() -> None:
    model = _model()
    safe = model.safe_submissions_from_document(_doc("observed_root_mapping.json"))
    world = _doc("complete_world_mapping.json")
    p1_team = world["sides"]["p1"]["pokemon"]  # type: ignore[index]
    p1_team.append(copy.deepcopy(p1_team[1]))
    same_choice_different_identity = BattleSubmission(
        kind=ActionKind.SWITCH,
        provenance=safe.submissions[0].provenance,
        slot=3,
    )

    with pytest.raises(PokeEngineMappingFailure) as caught:
        model.prepare_battle_root(
            observed_state=_observed(),
            safe_submissions=SafeSubmissionSet(
                safe.request_identity, (*safe.submissions, same_choice_different_identity)
            ),
            complete_world=world,
            ruleset_digest=_RULESET,
        )

    assert caught.value.failure_class == "safe_submission_mismatch"
    assert caught.value.work_units == 0


def test_invalid_deep_action_is_rejected_before_native_transition() -> None:
    model = _model()
    prepared = _prepared(model)
    invalid = SearchAction(action_id="invalid.choice", kind="move")

    with pytest.raises(PokeEngineMappingFailure) as caught:
        model.transition(prepared, prepared.root_actions[0], invalid)

    assert caught.value.failure_class == "invalid_joint_action"
    assert caught.value.work_units == 0


def test_request_identity_mismatch_is_distinct_from_stale_safe_set() -> None:
    model = _model()
    prepared = _prepared(model)
    mismatched_root = PreparedRootIdentity.create(
        request_identity_digest="sha256:" + "9" * 64,
        safe_submission_set_digest=prepared.root_identity.safe_submission_set_digest,
        observed_state_digest=prepared.root_identity.observed_state_digest,
        root_player=prepared.root_identity.root_player,
        ruleset_digest=prepared.root_identity.ruleset_digest,
        backend_identity_digest=prepared.root_identity.backend_identity_digest,
        capability_catalog_digest=prepared.root_identity.capability_catalog_digest,
    )

    with pytest.raises(PokeEngineMappingFailure) as caught:
        model.prepare_battle_root(
            observed_state=_observed(),
            safe_submissions=model.safe_submissions_from_document(
                _doc("observed_root_mapping.json")
            ),
            complete_world=_doc("complete_world_mapping.json"),
            ruleset_digest=_RULESET,
            root_identity=mismatched_root,
        )

    assert caught.value.failure_class == "request_identity_mismatch"
    assert caught.value.work_units == 0


def test_unknown_native_depth_choice_fails_closed() -> None:
    model = _model()
    prepared = _prepared(model)
    model._backend.native.legal_choices = lambda _state: (["tackle"], ["switch too many tokens"])

    with pytest.raises(PokeEngineMappingFailure) as caught:
        model.legal_actions(prepared, "p2")

    assert caught.value.failure_class == "unknown_native_choice"


def test_native_path_or_host_payload_cannot_become_deep_action() -> None:
    model = _model()
    prepared = _prepared(model)
    model._backend.native.legal_choices = lambda _state: (
        ["tackle"],
        ["C:\\Users\\mallory\\State(0xDEADBEEF)"],
    )

    with pytest.raises(PokeEngineMappingFailure) as caught:
        model.legal_actions(prepared, "p2")

    assert caught.value.failure_class == "unknown_native_choice"
    assert "mallory" not in str(caught.value)
