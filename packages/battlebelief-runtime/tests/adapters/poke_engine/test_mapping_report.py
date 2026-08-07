from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_runtime.adapters.poke_engine import (
    MappingReport,
    PokeEngineMappingFailure,
    PokeEngineTransitionModel,
    RequiredCapabilities,
)
from battlebelief_runtime.adapters.poke_engine.artifact import RuntimeEnvironment
from battlebelief_runtime.adapters.poke_engine.transition_model import _load_catalog

_FIXTURES = Path(__file__).parents[2] / "fixtures" / "poke_engine"


def _doc(name: str) -> dict[str, object]:
    value = json.loads((_FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _prepared():
    model = PokeEngineTransitionModel(
        catalog=_load_catalog(),
        _artifact_environment=RuntimeEnvironment(
            "windows-2025", "x86_64", "cp314", "none", "win_amd64"
        ),
    )
    observed = replace(
        ObservedState.initial("ash"),
        room_initialized=True,
        generation=9,
        game_type="singles",
        tier="gen9ou",
        battle_started=True,
        our_side="p1",
        turn=1,
    )
    return model, model.prepare_battle_root(
        observed_state=observed,
        safe_submissions=model.safe_submissions_from_document(_doc("observed_root_mapping.json")),
        complete_world=_doc("complete_world_mapping.json"),
        ruleset_digest="sha256:" + "4" * 64,
    )


def test_mapping_report_is_public_deterministic_and_sanitized() -> None:
    model, prepared = _prepared()
    first = model.mapping_report(prepared)
    second = model.mapping_report(prepared)

    assert isinstance(first, MappingReport)
    assert first == second
    document = first.to_dict()
    rendered = json.dumps(document, sort_keys=True)
    assert "sha256:" in rendered
    for forbidden in (
        "lightball",
        "eviolite",
        "tackle",
        "State(",
        "0x",
        "C:\\",
        "Users",
        "mallory",
    ):
        assert forbidden not in rendered


def test_required_capabilities_are_catalog_bound_sorted_and_not_claims() -> None:
    model, prepared = _prepared()
    required = model.required_capabilities(prepared)

    assert isinstance(required, RequiredCapabilities)
    values = tuple(capability.value for capability in required.values)
    assert values == tuple(sorted(set(values)))
    assert all(
        capability.catalog_digest == required.catalog_digest for capability in required.values
    )
    assert "exact" not in json.dumps(required.to_dict())
    assert "bounded_approximation" not in json.dumps(required.to_dict())


def test_preflight_conservatively_covers_every_statically_reachable_adapter_path() -> None:
    model, prepared = _prepared()

    assert {capability.value for capability in model.required_capabilities(prepared).values} == {
        "gen9.legality.move.selection",
        "gen9.legality.switch.forced",
        "gen9.legality.switch.voluntary",
        "gen9.legality.terastallization.activation",
        "gen9.transition.chance.damage-roll",
        "gen9.transition.move.direct-damage",
        "gen9.transition.order.priority",
        "gen9.transition.order.speed",
        "gen9.transition.switch.active-slot",
        "gen9.transition.terastallization.damage",
        "gen9.transition.terastallization.type-change",
        "gen9.transition.terminal.detection",
        "gen9.transition.terminal.value",
    }


def test_failure_contains_only_stable_class_report_and_deterministic_work() -> None:
    model, _ = _prepared()
    world = _doc("complete_world_mapping.json")
    world["secret"] = "C:\\Users\\mallory\\private State(0xBADC0DE)"

    with pytest.raises(PokeEngineMappingFailure) as caught:
        model.prepare_battle_root(
            observed_state=replace(
                ObservedState.initial("ash"),
                room_initialized=True,
                generation=9,
                game_type="singles",
                tier="gen9ou",
                battle_started=True,
                our_side="p1",
            ),
            safe_submissions=model.safe_submissions_from_document(
                _doc("observed_root_mapping.json")
            ),
            complete_world=world,
            ruleset_digest="sha256:" + "4" * 64,
        )

    failure = caught.value
    assert failure.failure_class == "unsupported_mapping"
    assert failure.work_units == 0
    assert failure.report.failure_class == failure.failure_class
    assert str(failure) == "poke_engine mapping failed: unsupported_mapping"
    assert "mallory" not in repr(failure.report)
