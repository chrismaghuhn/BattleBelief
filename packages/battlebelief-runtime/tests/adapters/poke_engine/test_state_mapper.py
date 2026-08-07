from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_runtime.adapters.poke_engine import (
    PokeEngineMappingFailure,
    PokeEngineTransitionModel,
)
from battlebelief_runtime.adapters.poke_engine.artifact import RuntimeEnvironment
from battlebelief_runtime.adapters.poke_engine.transition_model import _load_catalog

_FIXTURES = Path(__file__).parents[2] / "fixtures" / "poke_engine"
_RULESET = "sha256:" + "4" * 64


def _document(name: str) -> dict[str, object]:
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


def _model() -> PokeEngineTransitionModel:
    return PokeEngineTransitionModel(
        catalog=_load_catalog(),
        _artifact_environment=RuntimeEnvironment(
            operating_system="windows-2025",
            architecture="x86_64",
            python_tag="cp314",
            abi_tag="none",
            platform_tag="win_amd64",
        ),
    )


def test_observed_root_and_complete_world_are_mapped_separately() -> None:
    model = _model()
    prepared = model.prepare_battle_root(
        observed_state=_observed(),
        safe_submissions=model.safe_submissions_from_document(
            _document("observed_root_mapping.json")
        ),
        complete_world=_document("complete_world_mapping.json"),
        ruleset_digest=_RULESET,
    )

    report = model.mapping_report(prepared)
    assert report.classification == "mapped"
    assert prepared.root_identity.observed_state_digest == report.observed_state_digest
    assert prepared._opaque.native_state
    assert "lightball" not in str(report.to_dict())
    assert "eviolite" not in str(report.to_dict())


def test_opponent_hidden_world_does_not_change_players_public_information_key() -> None:
    model = _model()
    safe = model.safe_submissions_from_document(_document("observed_root_mapping.json"))
    first_world = _document("complete_world_mapping.json")
    second_world = _document("complete_world_mapping.json")
    p2 = second_world["sides"]["p2"]  # type: ignore[index]
    p2["pokemon"][0]["item"] = "choicescarf"  # type: ignore[index]
    p2["pokemon"][0]["moves"][1]["id"] = "quickattack"  # type: ignore[index]

    first = model.prepare_battle_root(
        observed_state=_observed(),
        safe_submissions=safe,
        complete_world=first_world,
        ruleset_digest=_RULESET,
    )
    second = model.prepare_battle_root(
        observed_state=_observed(),
        safe_submissions=safe,
        complete_world=second_world,
        ruleset_digest=_RULESET,
    )

    assert model.information_state_key(model.player_view(first, "p1")) == (
        model.information_state_key(model.player_view(second, "p1"))
    )
    assert model.information_state_key(model.player_view(first, "p2")) != (
        model.information_state_key(model.player_view(second, "p2"))
    )


def test_public_observation_change_changes_information_key_deterministically() -> None:
    model = _model()
    safe = model.safe_submissions_from_document(_document("observed_root_mapping.json"))
    first_world = _document("complete_world_mapping.json")

    first = model.prepare_battle_root(
        observed_state=_observed(),
        safe_submissions=safe,
        complete_world=first_world,
        ruleset_digest=_RULESET,
    )
    second = model.prepare_battle_root(
        observed_state=replace(_observed(), turn=2),
        safe_submissions=safe,
        complete_world=first_world,
        ruleset_digest=_RULESET,
    )

    assert model.player_view(first, "p1") == model.player_view(first, "p1")
    assert model.player_view(first, "p1") != model.player_view(second, "p1")


def test_opponent_exact_max_hp_does_not_leak_when_public_hp_fraction_is_equal() -> None:
    model = _model()
    safe = model.safe_submissions_from_document(_document("observed_root_mapping.json"))
    first_world = _document("complete_world_mapping.json")
    second_world = _document("complete_world_mapping.json")
    first_active = first_world["sides"]["p2"]["pokemon"][0]  # type: ignore[index]
    second_active = second_world["sides"]["p2"]["pokemon"][0]  # type: ignore[index]
    first_active["hp"], first_active["maxhp"] = 70, 140
    second_active["hp"], second_active["maxhp"] = 50, 100

    first = model.prepare_battle_root(
        observed_state=_observed(),
        safe_submissions=safe,
        complete_world=first_world,
        ruleset_digest=_RULESET,
    )
    second = model.prepare_battle_root(
        observed_state=_observed(),
        safe_submissions=safe,
        complete_world=second_world,
        ruleset_digest=_RULESET,
    )

    assert model.player_view(first, "p1") == model.player_view(second, "p1")
    assert model.player_view(first, "p2") != model.player_view(second, "p2")


def test_root_public_information_comes_from_observation_not_hypothetical_world() -> None:
    model = _model()
    safe = model.safe_submissions_from_document(_document("observed_root_mapping.json"))
    first_world = _document("complete_world_mapping.json")
    second_world = _document("complete_world_mapping.json")
    hidden_active = second_world["sides"]["p2"]["pokemon"][0]  # type: ignore[index]
    hidden_active["id"] = "vaporeon"
    hidden_active["types"] = ["water", "typeless"]
    hidden_active["base_types"] = ["water", "typeless"]
    hidden_active["status"] = "brn"
    hidden_active["hp"] = 35

    first = model.prepare_battle_root(
        observed_state=_observed(),
        safe_submissions=safe,
        complete_world=first_world,
        ruleset_digest=_RULESET,
    )
    second = model.prepare_battle_root(
        observed_state=_observed(),
        safe_submissions=safe,
        complete_world=second_world,
        ruleset_digest=_RULESET,
    )

    assert model.player_view(first, "p1") == model.player_view(second, "p1")
    assert model.player_view(first, "p2") != model.player_view(second, "p2")


def test_unchanged_hidden_baseline_does_not_enter_deeper_player_view() -> None:
    model = _model()
    safe = model.safe_submissions_from_document(_document("observed_root_mapping.json"))
    first_world = _document("complete_world_mapping.json")
    second_world = _document("complete_world_mapping.json")
    hidden_active = second_world["sides"]["p2"]["pokemon"][0]  # type: ignore[index]
    hidden_active["id"] = "vaporeon"
    hidden_active["types"] = ["water", "typeless"]
    hidden_active["base_types"] = ["water", "typeless"]
    first = model.prepare_battle_root(
        observed_state=_observed(),
        safe_submissions=safe,
        complete_world=first_world,
        ruleset_digest=_RULESET,
    )
    second = model.prepare_battle_root(
        observed_state=_observed(),
        safe_submissions=safe,
        complete_world=second_world,
        ruleset_digest=_RULESET,
    )
    first_p2 = next(action for action in model.legal_actions(first, "p2") if action.kind == "move")
    second_p2 = next(
        action for action in model.legal_actions(second, "p2") if action.kind == "move"
    )

    first_outcome = model.transition(first, first.root_actions[0], first_p2)
    second_outcome = model.transition(second, second.root_actions[0], second_p2)

    assert {
        model.player_view(successor.world, "p1").view_digest
        for successor in first_outcome.successors
    } == {
        model.player_view(successor.world, "p1").view_digest
        for successor in second_outcome.successors
    }


@pytest.mark.parametrize("mutation", ["missing", "unsupported", "wrong_generation"])
def test_missing_or_unsupported_complete_world_fails_closed(mutation: str) -> None:
    model = _model()
    world = _document("complete_world_mapping.json")
    if mutation == "missing":
        del world["sides"]
    elif mutation == "unsupported":
        world["native_dump"] = _document("unsupported_mapping.json")
    else:
        world["generation"] = 8

    with pytest.raises(PokeEngineMappingFailure) as caught:
        model.prepare_battle_root(
            observed_state=_observed(),
            safe_submissions=model.safe_submissions_from_document(
                _document("observed_root_mapping.json")
            ),
            complete_world=world,
            ruleset_digest=_RULESET,
        )

    assert caught.value.failure_class in {"missing_field", "unsupported_mapping"}
    assert "native_dump" not in str(caught.value)


def test_observed_root_rejects_non_gen9_singles_without_enrichment() -> None:
    model = _model()
    observed = replace(_observed(), generation=8)
    before = repr(observed)

    with pytest.raises(PokeEngineMappingFailure) as caught:
        model.prepare_battle_root(
            observed_state=observed,
            safe_submissions=model.safe_submissions_from_document(
                _document("observed_root_mapping.json")
            ),
            complete_world=_document("complete_world_mapping.json"),
            ruleset_digest=_RULESET,
        )

    assert caught.value.failure_class == "unsupported_mapping"
    assert repr(observed) == before


def test_native_world_constructor_exception_is_typed_and_sanitized() -> None:
    model = _model()

    def fail_native_constructor(**_: object) -> None:
        raise RuntimeError("C:\\Users\\mallory\\hidden State(0xDEADBEEF)")

    model._backend.native.Pokemon = fail_native_constructor

    with pytest.raises(PokeEngineMappingFailure) as caught:
        model.prepare_battle_root(
            observed_state=_observed(),
            safe_submissions=model.safe_submissions_from_document(
                _document("observed_root_mapping.json")
            ),
            complete_world=_document("complete_world_mapping.json"),
            ruleset_digest=_RULESET,
        )

    assert caught.value.failure_class == "native_exception"
    assert "mallory" not in str(caught.value)
