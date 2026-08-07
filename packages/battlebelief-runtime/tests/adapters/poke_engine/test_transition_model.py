from __future__ import annotations

import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from battlebelief_core.domain.search import TransitionOutcome
from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_core.ports.transition_model import EngineBackendHealth
from battlebelief_runtime.adapters.poke_engine import (
    PokeEngineMappingFailure,
    PokeEngineTransitionModel,
)
from battlebelief_runtime.adapters.poke_engine.artifact import RuntimeEnvironment
from battlebelief_runtime.adapters.poke_engine.errors import (
    EngineArtifactError,
    EngineFailureClass,
)
from battlebelief_runtime.adapters.poke_engine.transition_model import _load_catalog

_FIXTURES = Path(__file__).parents[2] / "fixtures" / "poke_engine"
_RULESET = "sha256:" + "4" * 64


def _doc(name: str) -> dict[str, object]:
    value = json.loads((_FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


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


def _model_and_world(world: dict[str, object] | None = None):
    model = PokeEngineTransitionModel(
        catalog=_load_catalog(),
        _artifact_environment=RuntimeEnvironment(
            "windows-2025", "x86_64", "cp314", "none", "win_amd64"
        ),
    )
    prepared = model.prepare_battle_root(
        observed_state=_observed(),
        safe_submissions=model.safe_submissions_from_document(_doc("observed_root_mapping.json")),
        complete_world=_doc("complete_world_mapping.json") if world is None else world,
        ruleset_digest=_RULESET,
    )
    return model, prepared


def _model() -> PokeEngineTransitionModel:
    return PokeEngineTransitionModel(
        catalog=_load_catalog(),
        _artifact_environment=RuntimeEnvironment(
            "windows-2025", "x86_64", "cp314", "none", "win_amd64"
        ),
    )


def _action_with_capability(actions, capability: str):
    return next(
        action
        for action in actions
        if capability in {item.value for item in action.required_capabilities}
    )


def test_joint_transition_normalizes_chance_preserves_root_and_counts_one_work_unit() -> None:
    model, prepared = _model_and_world()
    p1 = prepared.root_actions[1]
    p2 = next(action for action in model.legal_actions(prepared, "p2") if action.kind == "move")

    outcome = model.transition(prepared, p1, p2)

    assert isinstance(outcome, TransitionOutcome)
    assert outcome.work.units == 1
    assert sum(item.probability_numerator for item in outcome.successors) == (
        outcome.probability_denominator
    )
    assert all(item.world.root_identity is prepared.root_identity for item in outcome.successors)
    assert all(item.world.root_actions == prepared.root_actions for item in outcome.successors)
    assert all(item.world._opaque.ply == 1 for item in outcome.successors)
    assert any(item.world._opaque.terastallized[0] for item in outcome.successors)


def test_transition_capabilities_cover_priority_speed_damage_chance_and_tera() -> None:
    model, prepared = _model_and_world()
    p2 = next(action for action in model.legal_actions(prepared, "p2") if action.kind == "move")
    outcome = model.transition(prepared, prepared.root_actions[1], p2)
    values = {capability.value for capability in outcome.required_capabilities}

    assert {
        "gen9.transition.chance.damage-roll",
        "gen9.transition.move.direct-damage",
        "gen9.transition.order.priority",
        "gen9.transition.order.speed",
        "gen9.transition.terastallization.damage",
        "gen9.transition.terastallization.type-change",
    } <= values


def test_switch_transition_updates_active_slot_only_after_joint_choice() -> None:
    model, prepared = _model_and_world()
    before = prepared._opaque.active_indexes
    p2 = next(action for action in model.legal_actions(prepared, "p2") if action.kind == "move")
    outcome = model.transition(prepared, prepared.root_actions[2], p2)

    assert prepared._opaque.active_indexes == before
    assert all(item.world._opaque.active_indexes[0] == 1 for item in outcome.successors)
    assert "gen9.transition.switch.active-slot" in {
        capability.value for capability in outcome.required_capabilities
    }


def test_terminal_detection_and_value_are_zero_sum() -> None:
    world = _doc("complete_world_mapping.json")
    for pokemon in world["sides"]["p2"]["pokemon"]:  # type: ignore[index]
        pokemon["hp"] = 0
    model, prepared = _model_and_world(world)

    assert model.is_terminal(prepared)
    assert model.terminal_value(prepared, "p1") == Fraction(1)
    assert model.terminal_value(prepared, "p2") == Fraction(-1)
    assert model.backend_health is EngineBackendHealth.HEALTHY


def test_identical_transition_input_has_identical_work_and_probabilities() -> None:
    model, prepared = _model_and_world()
    p2 = next(action for action in model.legal_actions(prepared, "p2") if action.kind == "move")
    first = model.transition(prepared, prepared.root_actions[0], p2)
    second = model.transition(prepared, prepared.root_actions[0], p2)

    assert first.work == second.work
    assert first.probability_denominator == second.probability_denominator
    assert tuple(item.probability_numerator for item in first.successors) == tuple(
        item.probability_numerator for item in second.successors
    )
    assert tuple(item.outcome_id for item in first.successors) == tuple(
        item.outcome_id for item in second.successors
    )


def test_native_exception_is_sanitized_and_charged_one_invoked_transition() -> None:
    model, prepared = _model_and_world()
    p2 = next(action for action in model.legal_actions(prepared, "p2") if action.kind == "move")
    model._generate_instructions = lambda *_: (_ for _ in ()).throw(  # type: ignore[method-assign]
        RuntimeError("secret C:\\Users\\mallory State(0xDEADBEEF)")
    )

    with pytest.raises(PokeEngineMappingFailure) as caught:
        model.transition(prepared, prepared.root_actions[0], p2)

    assert caught.value.failure_class == "native_exception"
    assert caught.value.work_units == 1
    assert "mallory" not in str(caught.value)


def test_player_validation_fails_closed() -> None:
    model, prepared = _model_and_world()
    with pytest.raises(PokeEngineMappingFailure):
        model.player_view(prepared, "p3")  # type: ignore[arg-type]
    with pytest.raises(PokeEngineMappingFailure):
        model.legal_actions(prepared, "p3")  # type: ignore[arg-type]
    with pytest.raises(PokeEngineMappingFailure):
        model.terminal_value(prepared, "p3")  # type: ignore[arg-type]


@pytest.mark.parametrize("artifact_case", ["wrong_wheel", "wrong_build", "wrong_cell"])
def test_artifact_identity_failures_are_typed(
    artifact_case: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from battlebelief_runtime.adapters.poke_engine import transition_model

    def fail_verification(**_: object) -> None:
        raise EngineArtifactError(EngineFailureClass.ARTIFACT_MISMATCH)

    monkeypatch.setattr(transition_model, "verify_installed_artifact", fail_verification)

    with pytest.raises(PokeEngineMappingFailure) as caught:
        _model()

    assert artifact_case in {"wrong_wheel", "wrong_build", "wrong_cell"}
    assert caught.value.failure_class == "artifact_identity_mismatch"
    assert caught.value.work_units == 0


def test_missing_extension_is_backend_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    from battlebelief_runtime.adapters.poke_engine import transition_model

    def fail_verification(**_: object) -> None:
        raise EngineArtifactError(EngineFailureClass.ARTIFACT_UNAVAILABLE)

    monkeypatch.setattr(transition_model, "verify_installed_artifact", fail_verification)

    with pytest.raises(PokeEngineMappingFailure) as caught:
        _model()

    assert caught.value.failure_class == "backend_unavailable"


def test_wrong_import_origin_is_adapter_identity_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from battlebelief_runtime.adapters.poke_engine import transition_model

    def fail_import(_verified: object) -> None:
        raise RuntimeError("C:\\Users\\mallory\\poke_engine.pyd at 0xDEADBEEF")

    monkeypatch.setattr(transition_model, "_import_verified_native", fail_import)

    with pytest.raises(PokeEngineMappingFailure) as caught:
        _model()

    assert caught.value.failure_class == "adapter_identity_mismatch"
    assert "mallory" not in str(caught.value)


@pytest.mark.parametrize("digest_function", ["_adapter_source_digest", "_core_contract_digest"])
def test_adapter_and_frozen_port_closure_mismatch_fail_closed(
    digest_function: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from battlebelief_runtime.adapters.poke_engine import transition_model

    monkeypatch.setattr(transition_model, digest_function, lambda: "sha256:" + "0" * 64)

    with pytest.raises(PokeEngineMappingFailure) as caught:
        _model()

    assert caught.value.failure_class == "adapter_identity_mismatch"
    assert caught.value.work_units == 0


def test_malformed_legal_choices_and_chance_fail_closed() -> None:
    model, prepared = _model_and_world()
    model._backend.native.legal_choices = lambda _state: ("tackle", ["ember"])
    with pytest.raises(PokeEngineMappingFailure) as legal_failure:
        model.legal_actions(prepared, "p2")
    assert legal_failure.value.failure_class == "malformed_native_result"
    assert legal_failure.value.work_units == 0

    model, prepared = _model_and_world()
    p2 = next(action for action in model.legal_actions(prepared, "p2") if action.kind == "move")
    model._generate_instructions = lambda *_: [  # type: ignore[method-assign]
        type("NativeInstruction", (), {"percentage": float("nan"), "state": "private"})()
    ]
    with pytest.raises(PokeEngineMappingFailure) as chance_failure:
        model.transition(prepared, prepared.root_actions[0], p2)
    assert chance_failure.value.failure_class == "chance_normalization_failure"
    assert chance_failure.value.work_units == 1


def test_core_work_accounting_rejection_has_distinct_typed_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from battlebelief_runtime.adapters.poke_engine import transition_model

    model, prepared = _model_and_world()
    p2 = next(action for action in model.legal_actions(prepared, "p2") if action.kind == "move")
    monkeypatch.setattr(transition_model, "TransitionWork", lambda **_: object())

    with pytest.raises(PokeEngineMappingFailure) as caught:
        model.transition(prepared, prepared.root_actions[0], p2)

    assert caught.value.failure_class == "work_accounting_inconsistency"
    assert caught.value.work_units == 1


def test_bounded_smoke_accepts_reviewed_repository_fixture_root() -> None:
    from battlebelief_runtime.adapters.poke_engine.transition_model import (
        _load_catalog,
        _run_bounded_conformance_smoke,
    )

    report = _run_bounded_conformance_smoke(_load_catalog(), fixture_root=_FIXTURES)

    assert report.classification == "transitioned"
    assert report.work_units == 1
