"""Task-28 guardrail: expose synthetic smoke only, never a qualification run."""

from __future__ import annotations

import argparse
import sys


def _synthetic_smoke() -> None:
    """Exercise one injected golden match without importing an engine or oracle backend."""

    from battlebelief_core.canonicalization import manifest_digest
    from battlebelief_lab.differential.classifier import DifferentialClassifier, DivergenceClass
    from battlebelief_lab.differential.corpus import DifferentialFixture
    from battlebelief_lab.differential.runner import (
        CanonicalMechanicsObservation,
        DifferentialRunner,
        FixtureResultProvenance,
        _authoritative_result_schema_digest,
    )

    def digest(label: str) -> str:
        return manifest_digest({"synthetic": label})

    classifier = DifferentialClassifier()
    ruleset_snapshot: dict[str, object] = {
        "format_id": "gen9ou",
        "ruleset_id": "synthetic-gen9ou-ruleset-v1",
        "ruleset_version": 1,
    }
    ruleset_digest = manifest_digest(ruleset_snapshot)

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
    fixture_document: dict[str, object] = {
        "schema_version": 1,
        "corpus_id": "gen9ou-differential",
        "corpus_version": "1",
        "fixture_id": "synthetic-smoke",
        "fixture_digest": digest("placeholder"),
        "generation": 9,
        "format": "gen9ou",
        "ruleset": {
            "ruleset_id": "synthetic-gen9ou-ruleset-v1",
            "ruleset_digest": ruleset_digest,
            "snapshot": ruleset_snapshot,
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
            {"checkpoint_id": "post-step", "comparison_fields": ["legal_actions"]}
        ],
        "declared_comparison_fields": ["legal_actions"],
        "normalization": {
            "profile_id": "canonicalization-profile",
            "profile_version": "1",
            "profile_digest": digest("canonicalization"),
        },
        "classification_policy": {
            "classifier_id": classifier.classifier_id,
            "classifier_version": classifier.classifier_version,
            "classifier_source_digest": classifier.source_digest,
            "known_divergence_id": None,
        },
        "provenance": {
            "source_type": "project-authored",
            "source_id": "synthetic-smoke",
            "license_id": "apache-2-0",
            "reviewed": True,
        },
    }
    fixture_document["fixture_digest"] = DifferentialFixture.derive_digest(fixture_document)
    fixture = DifferentialFixture.from_document(
        fixture_document,
        _corpus_digest_for_runner=digest("corpus"),
    )
    provenance = FixtureResultProvenance(
        corpus_id="gen9ou-differential",
        corpus_version="1",
        corpus_digest=digest("corpus"),
        ruleset_id="synthetic-gen9ou-ruleset-v1",
        ruleset_digest=ruleset_digest,
        catalog_id="gen9ou-engine-capabilities",
        catalog_version="1",
        catalog_digest=digest("catalog"),
        oracle_source_manifest_digest=digest("oracle-source"),
        oracle_build_manifest_digest=digest("oracle-build"),
        engine_source_manifest_digest=digest("engine-source"),
        engine_build_manifest_digest=digest("engine-build"),
        wheel_digest=digest("wheel"),
        runtime_adapter_id="poke-engine-transition",
        runtime_adapter_version="1",
        runtime_adapter_source_digest=digest("adapter"),
        environment_id="synthetic-golden",
        environment_digest=digest("environment"),
        canonicalization_profile_id="canonicalization-profile",
        canonicalization_profile_version="1",
        canonicalization_profile_digest=digest("canonicalization"),
        result_schema_id="urn:battlebelief:schema:evaluation:differential-result:v1",
        result_schema_version="1",
        result_schema_digest=_authoritative_result_schema_digest(),
    )
    observation = CanonicalMechanicsObservation({"legal_actions": ["move-1"]})
    result = DifferentialRunner(
        oracle_executor=lambda _fixture: observation,
        engine_executor=lambda _fixture: observation,
        provenance=provenance,
        classifier=classifier,
    ).run_fixture(fixture)
    if result.divergence_class is not DivergenceClass.MATCH or not result.synthetic:
        raise RuntimeError("synthetic runner smoke did not produce the frozen golden match")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--synthetic-smoke",
        action="store_true",
        help="acknowledge the injected synthetic/golden runner smoke boundary",
    )
    arguments = parser.parse_args(argv)
    if not arguments.synthetic_smoke:
        print(
            "REFUSED: Task 28 permits only --synthetic-smoke; real qualification belongs to Task 29.",
            file=sys.stderr,
        )
        return 2
    _synthetic_smoke()
    print("PASS: synthetic differential runner smoke boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
