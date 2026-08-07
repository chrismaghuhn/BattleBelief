"""Synthetic-only tests for the injected differential runner."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

import battlebelief_lab.differential as differential
from battlebelief_core.canonicalization import manifest_digest
from battlebelief_lab.differential.classifier import DifferentialClassifier, DivergenceClass
from battlebelief_lab.differential.corpus import DifferentialFixture
from battlebelief_lab.differential.runner import (
    CanonicalMechanicsObservation,
    DifferentialExecutionSkip,
    DifferentialRunner,
    FixtureResultProvenance,
)
from battlebelief_runtime.adapters.poke_engine import MappingReport, PokeEngineMappingFailure


def _digest(label: str) -> str:
    return manifest_digest({"synthetic": label})


def _authoritative_result_schema_digest() -> str:
    schema_path = (
        Path(__file__).resolve().parents[4] / "schemas/evaluation/differential-result.schema.json"
    )
    return "sha256:" + sha256(schema_path.read_bytes()).hexdigest()


_RULESET_SNAPSHOT = {
    "format_id": "gen9ou",
    "ruleset_id": "synthetic-gen9ou-ruleset-v1",
    "ruleset_version": 1,
}
_RULESET_DIGEST = manifest_digest(_RULESET_SNAPSHOT)


def _provenance() -> FixtureResultProvenance:
    return FixtureResultProvenance(
        corpus_id="gen9ou-differential",
        corpus_version="1",
        corpus_digest=_digest("corpus"),
        ruleset_id="synthetic-gen9ou-ruleset-v1",
        ruleset_digest=_RULESET_DIGEST,
        catalog_id="gen9ou-engine-capabilities",
        catalog_version="1",
        catalog_digest=_digest("catalog"),
        oracle_source_manifest_digest=_digest("oracle-source"),
        oracle_build_manifest_digest=_digest("oracle-build"),
        engine_source_manifest_digest=_digest("engine-source"),
        engine_build_manifest_digest=_digest("engine-build"),
        wheel_digest=_digest("wheel"),
        runtime_adapter_id="poke-engine-transition",
        runtime_adapter_version="1",
        runtime_adapter_source_digest=_digest("adapter"),
        environment_id="synthetic-golden",
        environment_digest=_digest("environment"),
        canonicalization_profile_id="canonicalization-profile",
        canonicalization_profile_version="1",
        canonicalization_profile_digest=_digest("canonicalization"),
        result_schema_id="urn:battlebelief:schema:evaluation:differential-result:v1",
        result_schema_version="1",
        result_schema_digest=_authoritative_result_schema_digest(),
    )


def _fixture(
    classifier: DifferentialClassifier,
    *,
    fields: list[str] | None = None,
    known_divergence_id: str | None = None,
) -> DifferentialFixture:
    comparison_fields = fields or ["legal_actions"]

    def combatant(slot_id: str, species_id: str, types: list[str]) -> dict[str, object]:
        return {
            "slot_id": slot_id,
            "species_id": species_id,
            "level": 100,
            "types": types,
            "ability_id": "static",
            "item_id": "none",
            "tera": {"active": False, "type": "electric"},
            "hp": {"current": 100, "maximum": 100},
            "status": "none",
            "stats": {"hp": 100, "atk": 55, "def": 40, "spa": 50, "spd": 50, "spe": 90},
            "boosts": {
                "atk": 0,
                "def": 0,
                "spa": 0,
                "spd": 0,
                "spe": 0,
                "accuracy": 0,
                "evasion": 0,
            },
            "moves": [{"move_id": "tackle", "pp": {"current": 35, "maximum": 35}}],
            "fainted": False,
        }

    def public_combatant(combatant_document: dict[str, object]) -> dict[str, object]:
        return {
            "slot_id": combatant_document["slot_id"],
            "species_id": combatant_document["species_id"],
            "types": combatant_document["types"],
            "hp": combatant_document["hp"],
            "status": combatant_document["status"],
            "terastallized": False,
            "fainted": combatant_document["fainted"],
        }

    p1_active = combatant("p1a", "pikachu", ["electric"])
    p2_active = combatant("p2a", "squirtle", ["water"])
    move_action = {"kind": "move", "move_id": "tackle"}
    document: dict[str, object] = {
        "schema_version": 1,
        "corpus_id": "gen9ou-differential",
        "corpus_version": "1",
        "fixture_id": "synthetic-runner",
        "fixture_digest": _digest("placeholder"),
        "generation": 9,
        "format": "gen9ou",
        "ruleset": {
            "ruleset_id": "synthetic-gen9ou-ruleset-v1",
            "ruleset_digest": _RULESET_DIGEST,
            "snapshot": deepcopy(_RULESET_SNAPSHOT),
        },
        "seed": {"seed_id": "synthetic-seed", "seed_value": "0000000000000001"},
        "initial_authoritative_full_state": {
            "field": {"terrain": "none", "turn": 1, "weather": "none"},
            "players": {
                "p1": {"active_slot": "p1a", "team": [p1_active]},
                "p2": {"active_slot": "p2a", "team": [p2_active]},
            },
            "terminal": {"state": "ongoing", "value": None},
        },
        "player_views": [
            {
                "player_id": "p1",
                "view": {
                    "own_active_slot": "p1a",
                    "opponent_active_slot": "p2a",
                    "own_active": public_combatant(p1_active),
                    "opponent_active": public_combatant(p2_active),
                    "legal_actions": [move_action],
                    "tera_available": True,
                },
            },
            {
                "player_id": "p2",
                "view": {
                    "own_active_slot": "p2a",
                    "opponent_active_slot": "p1a",
                    "own_active": public_combatant(p2_active),
                    "opponent_active": public_combatant(p1_active),
                    "legal_actions": [move_action],
                    "tera_available": True,
                },
            },
        ],
        "joint_action_intent": [
            {"actor": "p1", "action": move_action},
            {"actor": "p2", "action": move_action},
        ],
        "chance_inputs": [],
        "capability_ids": ["gen9.legality.move.selection"],
        "observation_checkpoints": [
            {"checkpoint_id": "post-step", "comparison_fields": comparison_fields}
        ],
        "declared_comparison_fields": comparison_fields,
        "normalization": {
            "profile_id": "canonicalization-profile",
            "profile_version": "1",
            "profile_digest": _digest("canonicalization"),
        },
        "classification_policy": {
            "classifier_id": classifier.classifier_id,
            "classifier_version": classifier.classifier_version,
            "classifier_source_digest": classifier.source_digest,
            "known_divergence_id": known_divergence_id,
        },
        "provenance": {
            "source_type": "project-authored",
            "source_id": "synthetic-runner",
            "license_id": "apache-2-0",
            "reviewed": True,
        },
    }
    document["fixture_digest"] = DifferentialFixture.derive_digest(document)
    return DifferentialFixture.from_document(
        document,
        _corpus_digest_for_runner=_digest("corpus"),
    )


def test_public_api_exports_runner_and_canonical_observation() -> None:
    assert hasattr(differential, "DifferentialRunner")
    assert hasattr(differential, "CanonicalMechanicsObservation")
    assert hasattr(differential, "FixtureResult")


def test_runner_compares_only_declared_fields_with_canonical_set_ordering() -> None:
    classifier = DifferentialClassifier()
    fixture = _fixture(classifier)

    def oracle(_: Mapping[str, object]) -> CanonicalMechanicsObservation:
        return CanonicalMechanicsObservation(
            {"legal_actions": ["move-1", "switch-1"], "hp": {"p1": 100}}
        )

    def engine(_: Mapping[str, object]) -> CanonicalMechanicsObservation:
        return CanonicalMechanicsObservation(
            {"legal_actions": ["switch-1", "move-1"], "hp": {"p1": 1}}
        )

    result = DifferentialRunner(
        oracle_executor=oracle,
        engine_executor=engine,
        provenance=_provenance(),
        classifier=classifier,
    ).run_fixture(fixture)

    assert result.execution_status == "completed"
    assert result.divergence_class is DivergenceClass.MATCH
    assert result.differing_fields == ()
    assert result.synthetic is True


def test_runner_classifies_a_new_declared_difference_as_unclassified() -> None:
    classifier = DifferentialClassifier()
    fixture = _fixture(classifier)
    observation = CanonicalMechanicsObservation({"legal_actions": ["move-1"]})
    different_observation = CanonicalMechanicsObservation({"legal_actions": ["switch-1"]})

    result = DifferentialRunner(
        oracle_executor=lambda _: observation,
        engine_executor=lambda _: different_observation,
        provenance=_provenance(),
        classifier=classifier,
    ).run_fixture(fixture)

    assert result.execution_status == "completed"
    assert result.divergence_class is DivergenceClass.UNCLASSIFIED
    assert result.differing_fields == ("legal_actions",)


def test_runner_classifies_only_a_prebound_difference_as_known_divergence() -> None:
    classifier = DifferentialClassifier(known_divergence_ids=("tera-boundary",))
    fixture = _fixture(classifier, known_divergence_id="tera-boundary")

    result = DifferentialRunner(
        oracle_executor=lambda _: CanonicalMechanicsObservation({"legal_actions": ["move-1"]}),
        engine_executor=lambda _: CanonicalMechanicsObservation({"legal_actions": ["switch-1"]}),
        provenance=_provenance(),
        classifier=classifier,
    ).run_fixture(fixture)

    assert result.divergence_class is DivergenceClass.KNOWN_DIVERGENCE
    assert result.known_divergence_id == "tera-boundary"


@pytest.mark.parametrize(
    ("executor", "expected_status", "failure_class", "failure_origin"),
    [
        (lambda _: DifferentialExecutionSkip(), "skipped", None, None),
        (lambda _: (_ for _ in ()).throw(TimeoutError()), "failed", "timeout", "oracle"),
        (
            lambda _: (_ for _ in ()).throw(RuntimeError("private crash")),
            "failed",
            "crash",
            "oracle",
        ),
        (lambda _: {"untrusted": "native output"}, "failed", "malformed_output", "oracle"),
    ],
)
def test_runner_never_classifies_noncompleted_or_malformed_or_crashed_side_as_match(
    executor: object,
    expected_status: str,
    failure_class: str | None,
    failure_origin: str | None,
) -> None:
    classifier = DifferentialClassifier()
    fixture = _fixture(classifier)

    result = DifferentialRunner(
        oracle_executor=executor,  # type: ignore[arg-type]
        engine_executor=lambda _: CanonicalMechanicsObservation({"legal_actions": ["move-1"]}),
        provenance=_provenance(),
        classifier=classifier,
    ).run_fixture(fixture)

    assert result.execution_status == expected_status
    assert result.divergence_class is None
    assert result.failure_class == failure_class
    assert result.failure_origin == failure_origin


@pytest.mark.parametrize(
    ("engine_executor", "failure_class"),
    [
        (lambda _: (_ for _ in ()).throw(TimeoutError()), "timeout"),
        (lambda _: (_ for _ in ()).throw(RuntimeError("private engine crash")), "crash"),
        (lambda _: {"malformed": "engine output"}, "malformed_output"),
    ],
)
def test_runner_never_classifies_engine_timeout_crash_or_malformed_output_as_match(
    engine_executor: object,
    failure_class: str,
) -> None:
    classifier = DifferentialClassifier()
    fixture = _fixture(classifier)

    result = DifferentialRunner(
        oracle_executor=lambda _: CanonicalMechanicsObservation({"legal_actions": ["move-1"]}),
        engine_executor=engine_executor,  # type: ignore[arg-type]
        provenance=_provenance(),
        classifier=classifier,
    ).run_fixture(fixture)

    assert result.execution_status == "failed"
    assert result.divergence_class is None
    assert result.failure_class == failure_class
    assert result.failure_origin == "engine"


def test_runner_projects_runtime_mapping_failure_without_exposing_the_native_error() -> None:
    classifier = DifferentialClassifier()
    fixture = _fixture(classifier)
    report = MappingReport(
        classification="failed",
        adapter_id="poke-engine-transition",
        adapter_version="1",
        backend_identity_digest=_digest("backend"),
        failure_class="missing_field",
    )

    def mapping_failure(_: Mapping[str, object]) -> CanonicalMechanicsObservation:
        raise PokeEngineMappingFailure("missing_field", report=report, work_units=0)

    result = DifferentialRunner(
        oracle_executor=lambda _: CanonicalMechanicsObservation({"legal_actions": ["move-1"]}),
        engine_executor=mapping_failure,
        provenance=_provenance(),
        classifier=classifier,
    ).run_fixture(fixture)

    assert result.execution_status == "failed"
    assert result.failure_class == "mapping_failure"
    assert result.failure_origin == "runtime_adapter"
    assert "missing_field" not in repr(result)


def test_runner_rejects_missing_declared_observation_field_as_malformed_output() -> None:
    classifier = DifferentialClassifier()
    fixture = _fixture(classifier, fields=["hp", "legal_actions"])

    result = DifferentialRunner(
        oracle_executor=lambda _: CanonicalMechanicsObservation({"legal_actions": ["move-1"]}),
        engine_executor=lambda _: CanonicalMechanicsObservation(
            {"hp": {"p1": 1}, "legal_actions": ["move-1"]}
        ),
        provenance=_provenance(),
        classifier=classifier,
    ).run_fixture(fixture)

    assert result.execution_status == "failed"
    assert result.failure_class == "malformed_output"
    assert result.failure_origin == "oracle"


def test_runner_compares_all_supported_mechanics_axes_when_declared() -> None:
    classifier = DifferentialClassifier()
    fields = sorted(
        [
            "legal_actions",
            "active_slot",
            "effective_types",
            "terastallized",
            "hp",
            "status",
            "action_order",
            "terminal_state",
            "terminal_value",
            "chance_branch_probabilities",
        ]
    )
    fixture = _fixture(classifier, fields=fields)
    observation = CanonicalMechanicsObservation(
        {
            "legal_actions": ["switch-1", "move-1"],
            "active_slot": "p1a",
            "effective_types": ["Ground"],
            "terastallized": True,
            "hp": {"p1": 50, "p2": 0},
            "status": {"p1": None, "p2": "brn"},
            "action_order": ["p1", "p2"],
            "terminal_state": "win",
            "terminal_value": 1,
            "chance_branch_probabilities": {"damage-low": "1/16", "damage-high": "1/16"},
        }
    )

    result = DifferentialRunner(
        oracle_executor=lambda _: observation,
        engine_executor=lambda _: observation,
        provenance=_provenance(),
        classifier=classifier,
    ).run_fixture(fixture)

    assert result.execution_status == "completed"
    assert result.divergence_class is DivergenceClass.MATCH


def test_runner_normalizes_nested_object_member_order_before_exact_comparison() -> None:
    classifier = DifferentialClassifier()
    fixture = _fixture(classifier, fields=["hp"])

    result = DifferentialRunner(
        oracle_executor=lambda _: CanonicalMechanicsObservation({"hp": {"p1": 100, "p2": 0}}),
        engine_executor=lambda _: CanonicalMechanicsObservation({"hp": {"p2": 0, "p1": 100}}),
        provenance=_provenance(),
        classifier=classifier,
    ).run_fixture(fixture)

    assert result.divergence_class is DivergenceClass.MATCH


@pytest.mark.parametrize(
    "fields",
    [
        {"terminal_state": "C:\\Users\\chris\\private"},
        {"status": {"p1": "Traceback (most recent call last): private"}},
        {"hp": {"native_state": "|turn|1"}},
        {"active_slot": "oracle.internal.example"},
    ],
)
def test_canonical_observation_rejects_private_or_operational_values(
    fields: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="public-safe"):
        CanonicalMechanicsObservation(fields)


def test_canonical_observation_recursively_freezes_nested_values() -> None:
    observation = CanonicalMechanicsObservation({"hp": {"p1": 100}, "legal_actions": ["move-1"]})

    hp = observation.fields["hp"]
    legal_actions = observation.fields["legal_actions"]
    with pytest.raises(TypeError):
        hp["p1"] = 1  # type: ignore[index]
    with pytest.raises(AttributeError):
        legal_actions.append("C:\\private-state")  # type: ignore[attr-defined]

    assert observation.to_dict() == {"hp": {"p1": 100}, "legal_actions": ["move-1"]}


def test_runner_gives_engine_a_detached_fixture_snapshot_after_oracle_mutation() -> None:
    classifier = DifferentialClassifier()
    fixture = _fixture(classifier)

    def oracle(document: Mapping[str, object]) -> CanonicalMechanicsObservation:
        full_state = document["initial_authoritative_full_state"]
        assert isinstance(full_state, dict)
        field = full_state["field"]
        assert isinstance(field, dict)
        field["turn"] = 999
        return CanonicalMechanicsObservation({"legal_actions": ["move-1"]})

    def engine(document: Mapping[str, object]) -> CanonicalMechanicsObservation:
        full_state = document["initial_authoritative_full_state"]
        assert isinstance(full_state, dict)
        field = full_state["field"]
        assert isinstance(field, dict)
        assert field["turn"] == 1
        return CanonicalMechanicsObservation({"legal_actions": ["move-1"]})

    result = DifferentialRunner(
        oracle_executor=oracle,
        engine_executor=engine,
        provenance=_provenance(),
        classifier=classifier,
    ).run_fixture(fixture)

    assert result.divergence_class is DivergenceClass.MATCH


def test_runner_rejects_a_ruleset_id_that_does_not_bind_the_fixture() -> None:
    classifier = DifferentialClassifier()
    fixture = _fixture(classifier)
    wrong_provenance = replace(_provenance(), ruleset_id="different-ruleset")

    with pytest.raises(ValueError, match="ruleset ID"):
        DifferentialRunner(
            oracle_executor=lambda _: CanonicalMechanicsObservation({"legal_actions": ["move-1"]}),
            engine_executor=lambda _: CanonicalMechanicsObservation({"legal_actions": ["move-1"]}),
            provenance=wrong_provenance,
            classifier=classifier,
        ).run_fixture(fixture)


def test_runner_rejects_a_corpus_digest_that_does_not_bind_the_fixture() -> None:
    classifier = DifferentialClassifier()
    fixture = _fixture(classifier)
    wrong_provenance = replace(_provenance(), corpus_digest=_digest("different-corpus"))

    with pytest.raises(ValueError, match="corpus digest"):
        DifferentialRunner(
            oracle_executor=lambda _: CanonicalMechanicsObservation({"legal_actions": ["move-1"]}),
            engine_executor=lambda _: CanonicalMechanicsObservation({"legal_actions": ["move-1"]}),
            provenance=wrong_provenance,
            classifier=classifier,
        ).run_fixture(fixture)


def test_private_fixture_handoff_retains_only_the_bound_corpus_digest() -> None:
    classifier = DifferentialClassifier()
    fixture = _fixture(classifier)

    assert fixture._corpus_digest_for_runner() == _digest("corpus")
