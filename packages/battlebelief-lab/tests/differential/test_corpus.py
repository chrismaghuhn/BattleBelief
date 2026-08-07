"""Tests for the versioned, content-addressed differential corpus closure."""

from __future__ import annotations

import json
import runpy
import tomllib
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from battlebelief_core.canonicalization import canonicalize, manifest_digest
from battlebelief_core.domain.engine_capabilities import CapabilityCatalog
from battlebelief_lab.differential.corpus import (
    CorpusValidationError,
    DifferentialCorpus,
    DifferentialFixture,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_CATALOG_PATH = _REPOSITORY_ROOT / "artifacts/gen9ou/m2/engine-capability-catalog-v1.json"
_CORPUS_V1_PATH = _REPOSITORY_ROOT / "artifacts/gen9ou/m2/differential/corpus-v1"
_DIGEST = "sha256:" + "a" * 64
_CLASSIFIER_ID = "battlebelief-differential-classifier"
_CLASSIFIER_VERSION = "1"
_CORPUS_ID = "gen9ou-differential"
_CORPUS_VERSION = "1"
_NORMALIZATION = {
    "profile_id": "canonical-ordering",
    "profile_version": "1",
    "profile_digest": "sha256:" + "c" * 64,
}
_RULESET_SNAPSHOT = {
    "format_id": "gen9ou",
    "ruleset_id": "synthetic-gen9ou-ruleset-v1",
    "ruleset_version": 1,
}
_STRICT_RULESET = {
    "ruleset_id": _RULESET_SNAPSHOT["ruleset_id"],
    "ruleset_digest": manifest_digest(_RULESET_SNAPSHOT),
    "snapshot": _RULESET_SNAPSHOT,
}
_RULESET = _STRICT_RULESET


def _catalog() -> CapabilityCatalog:
    return CapabilityCatalog.from_document(json.loads(_CATALOG_PATH.read_text(encoding="utf-8")))


def _raw_schema_digest(filename: str) -> str:
    schema_path = _REPOSITORY_ROOT / "schemas/evaluation" / filename
    return "sha256:" + sha256(schema_path.read_bytes()).hexdigest()


def _fixture_document(
    fixture_id: str,
    capability_ids: list[str],
    *,
    corpus_version: str = _CORPUS_VERSION,
    ruleset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    document = _strict_fixture_document(fixture_id, capability_ids)
    document["corpus_version"] = corpus_version
    if ruleset is not None:
        document["ruleset"] = ruleset
    _refresh_fixture_digest(document)
    return document


def _strict_fixture_document(
    fixture_id: str,
    capability_ids: list[str],
    *,
    comparison_fields: list[str] | None = None,
) -> dict[str, Any]:
    fields = comparison_fields or ["legal_actions"]

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
            "stats": {"atk": 55, "def": 40, "hp": 100, "spa": 50, "spd": 50, "spe": 90},
            "boosts": {
                "accuracy": 0,
                "atk": 0,
                "def": 0,
                "evasion": 0,
                "spa": 0,
                "spd": 0,
                "spe": 0,
            },
            "moves": [{"move_id": "tackle", "pp": {"current": 35, "maximum": 35}}],
            "fainted": False,
        }

    def public_combatant(combatant_document: dict[str, object]) -> dict[str, object]:
        return {
            "fainted": combatant_document["fainted"],
            "hp": combatant_document["hp"],
            "slot_id": combatant_document["slot_id"],
            "species_id": combatant_document["species_id"],
            "status": combatant_document["status"],
            "terastallized": False,
            "types": combatant_document["types"],
        }

    p1_active = combatant("p1a", "pikachu", ["electric"])
    p2_active = combatant("p2a", "squirtle", ["water"])
    move_action = {"kind": "move", "move_id": "tackle"}
    document: dict[str, Any] = {
        "schema_version": 1,
        "corpus_id": _CORPUS_ID,
        "corpus_version": _CORPUS_VERSION,
        "fixture_id": fixture_id,
        "fixture_digest": "",
        "generation": 9,
        "format": "gen9ou",
        "ruleset": deepcopy(_STRICT_RULESET),
        "seed": {"seed_id": f"seed-{fixture_id}", "seed_value": "0000000000000001"},
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
                    "legal_actions": [move_action],
                    "opponent_active": public_combatant(p2_active),
                    "opponent_active_slot": "p2a",
                    "own_active": public_combatant(p1_active),
                    "own_active_slot": "p1a",
                    "tera_available": True,
                },
            },
            {
                "player_id": "p2",
                "view": {
                    "legal_actions": [move_action],
                    "opponent_active": public_combatant(p1_active),
                    "opponent_active_slot": "p1a",
                    "own_active": public_combatant(p2_active),
                    "own_active_slot": "p2a",
                    "tera_available": True,
                },
            },
        ],
        "joint_action_intent": [
            {"actor": "p1", "action": move_action},
            {"actor": "p2", "action": move_action},
        ],
        "chance_inputs": [],
        "capability_ids": capability_ids,
        "observation_checkpoints": [
            {"checkpoint_id": "after-joint-action", "comparison_fields": fields}
        ],
        "declared_comparison_fields": fields,
        "normalization": deepcopy(_NORMALIZATION),
        "classification_policy": {
            "classifier_id": _CLASSIFIER_ID,
            "classifier_version": _CLASSIFIER_VERSION,
            "classifier_source_digest": _DIGEST,
            "known_divergence_id": None,
        },
        "provenance": {
            "source_type": "project-authored",
            "source_id": f"fixture-source-{fixture_id}",
            "license_id": "Apache-2.0",
            "reviewed": True,
        },
    }
    _refresh_fixture_digest(document)
    return document


def _index_document(
    fixtures: list[dict[str, Any]],
    catalog: CapabilityCatalog,
    *,
    corpus_version: str = _CORPUS_VERSION,
    ruleset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    capability_to_fixtures: dict[str, list[str]] = {}
    for fixture in fixtures:
        for capability_id in fixture["capability_ids"]:
            capability_to_fixtures.setdefault(capability_id, []).append(fixture["fixture_id"])
    document: dict[str, Any] = {
        "schema_version": 1,
        "corpus_id": _CORPUS_ID,
        "corpus_version": corpus_version,
        "corpus_digest": "",
        "schema_bindings": [
            {
                "schema_id": "urn:battlebelief:schema:evaluation:differential-corpus:v1",
                "schema_version": 1,
                "schema_digest": _raw_schema_digest("differential-corpus.schema.json"),
            },
            {
                "schema_id": "urn:battlebelief:schema:evaluation:differential-fixture:v1",
                "schema_version": 1,
                "schema_digest": _raw_schema_digest("differential-fixture.schema.json"),
            },
        ],
        "canonicalization": {
            "canonicalization_id": catalog.canonicalization_contract_id,
            "canonicalization_version": catalog.canonicalization_contract_version,
            "canonicalization_digest": catalog.canonicalization_contract_digest,
        },
        "catalog": {
            "catalog_id": catalog.catalog_id,
            "catalog_version": catalog.catalog_version,
            "catalog_digest": catalog.catalog_digest,
        },
        "ruleset": ruleset or deepcopy(_RULESET),
        "normalization": deepcopy(_NORMALIZATION),
        "classifier": {
            "classifier_id": _CLASSIFIER_ID,
            "classifier_version": _CLASSIFIER_VERSION,
            "classifier_source_digest": _DIGEST,
            "known_divergence_definitions": [],
        },
        "fixtures": [
            {
                "fixture_id": fixture["fixture_id"],
                "path": f"fixtures/{fixture['fixture_id']}.json",
                "fixture_digest": fixture["fixture_digest"],
            }
            for fixture in fixtures
        ],
        "coverage": [
            {
                "capability_id": capability_id,
                "coverage_kind": "reviewed_fixture",
                "fixture_ids": fixture_ids,
                "known_divergence_id": None,
            }
            for capability_id, fixture_ids in capability_to_fixtures.items()
        ],
    }
    document["corpus_digest"] = manifest_digest(
        {name: value for name, value in document.items() if name != "corpus_digest"}
    )
    return document


def _write_corpus(tmp_path: Path, index: dict[str, Any], fixtures: list[dict[str, Any]]) -> Path:
    (tmp_path / "fixtures").mkdir(parents=True)
    for fixture in fixtures:
        (tmp_path / "fixtures" / f"{fixture['fixture_id']}.json").write_bytes(canonicalize(fixture))
    (tmp_path / "index.json").write_bytes(canonicalize(index))
    return tmp_path


def _complete_corpus_documents() -> tuple[CapabilityCatalog, list[dict[str, Any]], dict[str, Any]]:
    catalog = _catalog()
    fixtures = [
        _fixture_document(f"fixture-{position:02d}", [definition.value])
        for position, definition in enumerate(catalog.definitions, start=1)
    ]
    return catalog, fixtures, _index_document(fixtures, catalog)


def _refresh_fixture_digest(document: dict[str, Any]) -> None:
    document["fixture_digest"] = manifest_digest(
        {name: value for name, value in document.items() if name != "fixture_digest"}
    )


def _refresh_index_digest(document: dict[str, Any]) -> None:
    document["corpus_digest"] = manifest_digest(
        {name: value for name, value in document.items() if name != "corpus_digest"}
    )


def test_accepts_a_strict_typed_gen9ou_transition_fixture() -> None:
    fixture_document = _strict_fixture_document(
        "strict-transition", ["gen9.legality.move.selection"]
    )

    fixture = DifferentialFixture.from_document(fixture_document)

    assert fixture.ruleset_digest == manifest_digest(_RULESET_SNAPSHOT)


def test_rejects_a_ruleset_snapshot_with_a_nonbinding_digest() -> None:
    fixture_document = _strict_fixture_document(
        "wrong-ruleset-snapshot", ["gen9.legality.move.selection"]
    )
    fixture_document["ruleset"]["ruleset_digest"] = "sha256:" + "d" * 64
    _refresh_fixture_digest(fixture_document)

    with pytest.raises(CorpusValidationError, match="ruleset snapshot digest"):
        DifferentialFixture.from_document(fixture_document)


def test_rejects_a_checkpoint_that_does_not_exactly_bind_declared_fields() -> None:
    fixture_document = _strict_fixture_document(
        "mismatched-checkpoint",
        ["gen9.legality.move.selection"],
        comparison_fields=["legal_actions", "status"],
    )
    fixture_document["observation_checkpoints"][0]["comparison_fields"] = ["legal_actions"]
    _refresh_fixture_digest(fixture_document)

    with pytest.raises(CorpusValidationError, match="exactly match"):
        DifferentialFixture.from_document(fixture_document)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda document: document.update(
            {"initial_authoritative_full_state": {"scenario": "symbolic"}}
        ),
        lambda document: document["initial_authoritative_full_state"]["field"].pop("weather"),
        lambda document: document["player_views"][0]["view"].update({"private": "hidden"}),
        lambda document: document["player_views"][1]["view"].pop("own_active"),
        lambda document: document["joint_action_intent"][0]["action"].pop("move_id"),
        lambda document: document["chance_inputs"].append(
            {"chance_id": "damage", "kind": "damage-roll", "seed_value": "1"}
        ),
    ],
)
def test_rejects_symbolic_or_incomplete_strict_transition_documents(
    mutate: Any,
) -> None:
    fixture_document = _strict_fixture_document(
        "incomplete-transition", ["gen9.legality.move.selection"]
    )
    mutate(fixture_document)
    _refresh_fixture_digest(fixture_document)

    with pytest.raises(CorpusValidationError, match="schema validation failed"):
        DifferentialFixture.from_document(fixture_document)


def test_rejects_more_than_one_observation_checkpoint() -> None:
    fixture_document = _strict_fixture_document("two-checkpoints", ["gen9.legality.move.selection"])
    fixture_document["observation_checkpoints"].append(
        {"checkpoint_id": "after-second-step", "comparison_fields": ["legal_actions"]}
    )
    _refresh_fixture_digest(fixture_document)

    with pytest.raises(CorpusValidationError, match="schema validation failed"):
        DifferentialFixture.from_document(fixture_document)


def test_loads_a_complete_canonical_corpus_closure(tmp_path: Path) -> None:
    catalog, fixtures, index = _complete_corpus_documents()
    corpus_path = _write_corpus(tmp_path, index, fixtures)

    corpus = DifferentialCorpus.load(corpus_path, catalog)

    assert (corpus_path / "index.json").read_bytes() == canonicalize(index)
    assert (corpus_path / "fixtures/fixture-01.json").read_bytes() == canonicalize(fixtures[0])
    assert corpus.corpus_id == _CORPUS_ID
    assert corpus.corpus_version == _CORPUS_VERSION
    assert tuple(fixture.fixture_id for fixture in corpus.fixtures) == tuple(
        fixture["fixture_id"] for fixture in fixtures
    )
    assert corpus.capability_coverage == {
        definition.value: (f"fixture-{position:02d}",)
        for position, definition in enumerate(catalog.definitions, start=1)
    }


def test_loads_the_reviewed_strict_gen9ou_corpus_v1_closure() -> None:
    catalog = _catalog()

    corpus = DifferentialCorpus.load(_CORPUS_V1_PATH, catalog)

    assert corpus.corpus_digest == (
        "sha256:2073b321604f4aba24bc0ac05b0ac734b83c6a95522f39d6fc6e961e42547bbd"
    )
    assert len(corpus.fixtures) == 13
    assert set(corpus.capability_coverage) == {
        definition.value for definition in catalog.definitions
    }


def test_rejects_a_state_with_an_active_slot_owned_by_the_other_player() -> None:
    fixture_document = _strict_fixture_document(
        "wrong-active-owner", ["gen9.legality.move.selection"]
    )
    fixture_document["initial_authoritative_full_state"]["players"]["p1"]["active_slot"] = "p2a"
    _refresh_fixture_digest(fixture_document)

    with pytest.raises(CorpusValidationError, match="active slot does not belong"):
        DifferentialFixture.from_document(fixture_document)


def test_rejects_a_terminal_value_that_does_not_match_its_terminal_state() -> None:
    fixture_document = _strict_fixture_document(
        "wrong-terminal-value", ["gen9.legality.move.selection"]
    )
    fixture_document["initial_authoritative_full_state"]["terminal"] = {
        "state": "p1-win",
        "value": 0,
    }
    _refresh_fixture_digest(fixture_document)

    with pytest.raises(CorpusValidationError, match="terminal value does not match"):
        DifferentialFixture.from_document(fixture_document)


@pytest.mark.parametrize(("fainted", "current_hp"), [(True, 1), (False, 0)])
def test_rejects_a_combatant_with_inconsistent_fainted_and_hp_state(
    fainted: bool, current_hp: int
) -> None:
    fixture_document = _strict_fixture_document(
        "inconsistent-fainted-state", ["gen9.legality.move.selection"]
    )
    combatant = fixture_document["initial_authoritative_full_state"]["players"]["p2"]["team"][0]
    combatant["fainted"] = fainted
    combatant["hp"]["current"] = current_hp
    _refresh_fixture_digest(fixture_document)

    with pytest.raises(CorpusValidationError, match="fainted state does not match HP"):
        DifferentialFixture.from_document(fixture_document)


@pytest.mark.parametrize(
    ("relative_path", "mutation"),
    [
        ("index.json", lambda payload: payload + b"\n"),
        ("fixtures/fixture-01.json", lambda payload: b"\xef\xbb\xbf" + payload),
        (
            "fixtures/fixture-02.json",
            lambda payload: json.dumps(
                {
                    key: value
                    for key, value in reversed(json.loads(payload.decode("utf-8")).items())
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8"),
        ),
    ],
)
def test_rejects_noncanonical_raw_corpus_json_bytes(
    tmp_path: Path, relative_path: str, mutation: object
) -> None:
    catalog, fixtures, index = _complete_corpus_documents()
    corpus_path = _write_corpus(tmp_path, index, fixtures)
    path = corpus_path / relative_path
    payload = path.read_bytes()
    assert callable(mutation)
    path.write_bytes(mutation(payload))

    with pytest.raises(CorpusValidationError, match="canonical JSON"):
        DifferentialCorpus.load(corpus_path, catalog)


def test_fixture_digest_vector_uses_rfc8785_payload_without_self_digest() -> None:
    fixture = _fixture_document("fixture-vector", ["gen9.legality.move.selection"])

    assert DifferentialFixture.derive_digest(fixture) == (
        "sha256:74754af021fb0acce7b4923231c76d4ac7fbd22b105a50dbba441504370867a6"
    )


def test_fixture_corpus_digest_is_bound_to_each_equal_fixture_instance() -> None:
    fixture_document = _strict_fixture_document(
        "independent-corpus-binding", ["gen9.legality.move.selection"]
    )
    first = DifferentialFixture.from_document(
        fixture_document,
        _corpus_digest_for_runner="sha256:" + "a" * 64,
    )
    second = DifferentialFixture.from_document(
        fixture_document,
        _corpus_digest_for_runner="sha256:" + "b" * 64,
    )

    assert first == second
    assert first._corpus_digest_for_runner() == "sha256:" + "a" * 64
    assert second._corpus_digest_for_runner() == "sha256:" + "b" * 64


def test_corpus_index_digest_vector_uses_rfc8785_payload_without_self_digest() -> None:
    catalog, _fixtures, index = _complete_corpus_documents()
    assert catalog.catalog_id == "gen9ou-engine-capabilities"

    assert DifferentialCorpus.derive_digest(index) == (
        "sha256:c9b77ded2a7ca66011b2bcf3090b58e6da194f5fc86ea6b769d62f4226973dfc"
    )


def test_one_fixture_field_mutation_changes_its_fixture_and_corpus_digest(tmp_path: Path) -> None:
    catalog, fixtures, index = _complete_corpus_documents()
    original = DifferentialCorpus.load(
        _write_corpus(tmp_path / "original", index, fixtures), catalog
    )
    mutated_fixtures = deepcopy(fixtures)
    mutated_fixtures[0]["seed"]["seed_value"] = "0000000000000002"
    _refresh_fixture_digest(mutated_fixtures[0])
    mutated_index = _index_document(mutated_fixtures, catalog)

    mutated = DifferentialCorpus.load(
        _write_corpus(tmp_path / "mutated", mutated_index, mutated_fixtures), catalog
    )

    assert mutated.fixtures[0].fixture_digest != original.fixtures[0].fixture_digest
    assert mutated.corpus_digest != original.corpus_digest


def test_rejects_duplicate_fixture_ids(tmp_path: Path) -> None:
    catalog, fixtures, index = _complete_corpus_documents()
    index["fixtures"].append(
        {
            "fixture_id": fixtures[0]["fixture_id"],
            "path": "fixtures/fixture-duplicate.json",
            "fixture_digest": fixtures[0]["fixture_digest"],
        }
    )
    _refresh_index_digest(index)
    with pytest.raises(CorpusValidationError, match="duplicate fixture ID"):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)


def test_rejects_missing_referenced_fixture(tmp_path: Path) -> None:
    catalog, _fixtures, index = _complete_corpus_documents()
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "index.json").write_bytes(canonicalize(index))

    with pytest.raises(CorpusValidationError, match="referenced fixture is missing"):
        DifferentialCorpus.load(tmp_path, catalog)


def test_rejects_unreferenced_fixture_file(tmp_path: Path) -> None:
    catalog, fixtures, index = _complete_corpus_documents()
    extra = _fixture_document("fixture-extra", [catalog.definitions[0].value])

    with pytest.raises(CorpusValidationError, match="unreferenced fixture"):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, [*fixtures, extra]), catalog)


def test_rejects_a_fixture_capability_outside_the_task_26_catalog(tmp_path: Path) -> None:
    catalog, fixtures, _ = _complete_corpus_documents()
    fixtures[0]["capability_ids"] = ["gen9.transition.unknown.axis"]
    _refresh_fixture_digest(fixtures[0])
    index = _index_document(fixtures, catalog)

    with pytest.raises(CorpusValidationError, match="not defined by the capability catalog"):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)


def test_rejects_wrong_catalog_digest(tmp_path: Path) -> None:
    catalog, fixtures, index = _complete_corpus_documents()
    index["catalog"]["catalog_digest"] = "sha256:" + "d" * 64
    _refresh_index_digest(index)

    with pytest.raises(CorpusValidationError, match="catalog digest"):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)


def test_rejects_an_index_ruleset_snapshot_with_a_nonbinding_digest(tmp_path: Path) -> None:
    catalog, fixtures, index = _complete_corpus_documents()
    index["ruleset"]["ruleset_digest"] = "sha256:" + "d" * 64
    _refresh_index_digest(index)

    with pytest.raises(CorpusValidationError, match="ruleset snapshot digest"):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)


def test_rejects_fixture_ruleset_that_differs_from_index_ruleset(tmp_path: Path) -> None:
    catalog, fixtures, _ = _complete_corpus_documents()
    fixtures[0]["ruleset"]["ruleset_digest"] = "sha256:" + "e" * 64
    _refresh_fixture_digest(fixtures[0])
    index = _index_document(fixtures, catalog)

    with pytest.raises(CorpusValidationError, match="ruleset"):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)


def test_rejects_fixture_corpus_version_that_differs_from_index(tmp_path: Path) -> None:
    catalog, fixtures, _ = _complete_corpus_documents()
    fixtures[0]["corpus_version"] = "2"
    _refresh_fixture_digest(fixtures[0])
    index = _index_document(fixtures, catalog)

    with pytest.raises(CorpusValidationError, match="corpus version"):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)


def test_rejects_unsorted_fixture_entries_even_when_the_digest_is_recomputed(
    tmp_path: Path,
) -> None:
    catalog, fixtures, index = _complete_corpus_documents()
    index["fixtures"] = list(reversed(index["fixtures"]))
    _refresh_index_digest(index)

    with pytest.raises(CorpusValidationError, match="fixtures must be sorted"):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)


def test_rejects_unknown_fixture_fields_without_silent_defaults(tmp_path: Path) -> None:
    catalog, fixtures, _ = _complete_corpus_documents()
    fixtures[0]["unrecognized"] = "not permitted"
    _refresh_fixture_digest(fixtures[0])
    index = _index_document(fixtures, catalog)

    with pytest.raises(CorpusValidationError, match="schema"):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)


@pytest.mark.parametrize(
    "license_id",
    [
        "C:\\Users\\chris\\private-license",
        "https://license.example.test",
        "licenses.internal.example",
        "192.0.2.44",
        "hostname=private-builder",
    ],
)
def test_rejects_unsafe_provenance_license_id_before_fixture_digest_acceptance(
    tmp_path: Path, license_id: str
) -> None:
    catalog, fixtures, _ = _complete_corpus_documents()
    fixtures[0]["provenance"]["license_id"] = license_id
    _refresh_fixture_digest(fixtures[0])
    index = _index_document(fixtures, catalog)

    with pytest.raises(CorpusValidationError, match=r"path|hostname"):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)


@pytest.mark.parametrize(
    "license_id",
    [
        "C:\\Users\\chris\\private-license",
        "https://license.example.test",
        "licenses.internal.example",
        "192.0.2.44",
        "hostname=private-builder",
    ],
)
def test_fixture_schema_rejects_unsafe_provenance_license_id(license_id: str) -> None:
    fixture = _fixture_document("fixture-schema-license", ["gen9.legality.move.selection"])
    fixture["provenance"]["license_id"] = license_id
    schema = json.loads(
        (_REPOSITORY_ROOT / "schemas/evaluation/differential-fixture.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert list(Draft202012Validator(schema).iter_errors(fixture))


def test_rejects_non_nfc_fixture_string_before_fixture_digest_acceptance(tmp_path: Path) -> None:
    catalog, fixtures, _ = _complete_corpus_documents()
    fixtures[0]["initial_authoritative_full_state"]["label"] = "cafe\u0301"
    _refresh_fixture_digest(fixtures[0])
    index = _index_document(fixtures, catalog)

    with pytest.raises(CorpusValidationError, match="NFC"):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)


def test_rejects_non_nfc_corpus_index_string_before_corpus_digest_acceptance(
    tmp_path: Path,
) -> None:
    catalog, fixtures, index = _complete_corpus_documents()
    index["ruleset"]["ruleset_id"] = "cafe\u0301"
    _refresh_index_digest(index)

    with pytest.raises(CorpusValidationError, match="NFC"):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)


@pytest.mark.parametrize(
    ("target", "unsafe_value"),
    [
        ("initial_authoritative_full_state.state_path", "C:\\Users\\chris\\secret"),
        ("player_views.0.view.remote", "/private/evaluation"),
        ("joint_action_intent.1.action.target", "oracle.internal.example"),
        ("chance_inputs", [{"seed_source": "localhost"}]),
        ("seed.seed_value", "\\\\server\\private"),
    ],
)
def test_rejects_unsafe_strings_in_recursively_allowed_fixture_values(
    tmp_path: Path, target: str, unsafe_value: object
) -> None:
    catalog, fixtures, _ = _complete_corpus_documents()
    fixture = fixtures[0]
    target_parts = target.split(".")
    destination: object = fixture
    for part in target_parts[:-1]:
        if isinstance(destination, list):
            destination = destination[int(part)]
        else:
            assert isinstance(destination, dict)
            destination = destination[part]
    if isinstance(destination, list):
        destination.append(unsafe_value)
    else:
        assert isinstance(destination, dict)
        destination[target_parts[-1]] = unsafe_value
    _refresh_fixture_digest(fixture)
    index = _index_document(fixtures, catalog)

    with pytest.raises(CorpusValidationError, match=r"path|hostname|schema validation failed"):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)


def test_schema_failure_redacts_invalid_fixture_payload_values() -> None:
    sensitive_value = "sensitive-full-state-value-must-not-escape"
    fixture_document = _fixture_document(
        "fixture-schema-redaction", ["gen9.legality.move.selection"]
    )
    fixture_document["player_views"][0]["view"] = sensitive_value
    _refresh_fixture_digest(fixture_document)

    with pytest.raises(CorpusValidationError) as raised:
        DifferentialFixture.from_document(fixture_document)

    assert str(raised.value).startswith("schema validation failed: schema violation (type) at $")
    assert sensitive_value not in str(raised.value)


def test_loader_redacts_duplicate_nested_fixture_member_names(tmp_path: Path) -> None:
    catalog, fixtures, index = _complete_corpus_documents()
    sensitive_member_name = "sensitive-duplicate-fixture-member"
    corpus_path = _write_corpus(tmp_path, index, fixtures)
    (corpus_path / "fixtures/fixture-01.json").write_text(
        '{"nested":{"' + sensitive_member_name + '":1,"' + sensitive_member_name + '":2}}',
        encoding="utf-8",
    )

    with pytest.raises(CorpusValidationError) as raised:
        DifferentialCorpus.load(corpus_path, catalog)

    assert str(raised.value) == "duplicate JSON member is not permitted"
    assert sensitive_member_name not in str(raised.value)


def test_loader_redacts_dynamic_nested_fixture_member_names(tmp_path: Path) -> None:
    catalog, fixtures, _ = _complete_corpus_documents()
    sensitive_member_name = "sensitive-nested-fixture-member"
    fixtures[0]["initial_authoritative_full_state"][sensitive_member_name] = "C:\\private"
    _refresh_fixture_digest(fixtures[0])
    index = _index_document(fixtures, catalog)

    with pytest.raises(CorpusValidationError) as raised:
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)

    assert str(raised.value) == (
        "fixture.initial_authoritative_full_state.* contains an absolute local path"
    )
    assert sensitive_member_name not in str(raised.value)


def test_loader_redacts_huge_untrusted_fixture_integers_before_schema_validation(
    tmp_path: Path,
) -> None:
    catalog, fixtures, index = _complete_corpus_documents()
    huge_integer = 10**100
    corpus_path = _write_corpus(tmp_path, index, fixtures)
    fixture_path = corpus_path / "fixtures/fixture-01.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["initial_authoritative_full_state"]["huge_integer"] = huge_integer
    fixture_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )

    with pytest.raises(CorpusValidationError) as raised:
        DifferentialCorpus.load(corpus_path, catalog)

    assert str(raised.value) == "canonical JSON value is invalid"
    assert str(huge_integer) not in str(raised.value)


def test_loader_redacts_deep_untrusted_fixture_nesting_before_schema_validation(
    tmp_path: Path,
) -> None:
    catalog, fixtures, index = _complete_corpus_documents()
    corpus_path = _write_corpus(tmp_path, index, fixtures)
    fixture_path = corpus_path / "fixtures/fixture-01.json"
    fixture_path.write_text(
        '{"initial_authoritative_full_state":' + '{"nested":' * 1_100 + "0" + "}" * 1_100 + "}",
        encoding="utf-8",
    )

    with pytest.raises(CorpusValidationError) as raised:
        DifferentialCorpus.load(corpus_path, catalog)

    assert str(raised.value) == "canonical JSON value is invalid"
    assert "RecursionError" not in str(raised.value)


def test_rejects_reviewed_coverage_for_a_known_divergence_fixture(tmp_path: Path) -> None:
    catalog, fixtures, _ = _complete_corpus_documents()
    fixtures[0]["classification_policy"]["known_divergence_id"] = "known-tera-boundary"
    _refresh_fixture_digest(fixtures[0])
    index = _index_document(fixtures, catalog)
    index["classifier"]["known_divergence_definitions"] = [
        {
            "known_divergence_id": "known-tera-boundary",
            "affected_capability_ids": [catalog.definitions[0].value],
        }
    ]
    _refresh_index_digest(index)

    with pytest.raises(CorpusValidationError, match="reviewed fixture coverage"):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)


def test_rejects_known_boundary_coverage_with_a_different_fixture_divergence_id(
    tmp_path: Path,
) -> None:
    catalog, fixtures, _ = _complete_corpus_documents()
    fixtures[0]["classification_policy"]["known_divergence_id"] = "known-tera-boundary"
    _refresh_fixture_digest(fixtures[0])
    index = _index_document(fixtures, catalog)
    index["classifier"]["known_divergence_definitions"] = [
        {
            "known_divergence_id": "known-tera-boundary",
            "affected_capability_ids": [catalog.definitions[0].value],
        }
    ]
    index["coverage"][0]["coverage_kind"] = "known_boundary"
    index["coverage"][0]["known_divergence_id"] = "different-boundary"
    _refresh_index_digest(index)

    with pytest.raises(CorpusValidationError, match="known boundary coverage"):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)


def test_accepts_known_boundary_coverage_when_fixture_and_coverage_bind_the_same_id(
    tmp_path: Path,
) -> None:
    catalog, fixtures, _ = _complete_corpus_documents()
    fixtures[0]["classification_policy"]["known_divergence_id"] = "known-tera-boundary"
    _refresh_fixture_digest(fixtures[0])
    index = _index_document(fixtures, catalog)
    index["classifier"]["known_divergence_definitions"] = [
        {
            "known_divergence_id": "known-tera-boundary",
            "affected_capability_ids": [catalog.definitions[0].value],
        }
    ]
    index["coverage"][0]["coverage_kind"] = "known_boundary"
    index["coverage"][0]["known_divergence_id"] = "known-tera-boundary"
    _refresh_index_digest(index)

    assert DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog).fixtures


def test_rejects_known_boundary_with_an_unbound_divergence_definition(tmp_path: Path) -> None:
    catalog, fixtures, _ = _complete_corpus_documents()
    fixtures[0]["classification_policy"]["known_divergence_id"] = "known-tera-boundary"
    _refresh_fixture_digest(fixtures[0])
    index = _index_document(fixtures, catalog)
    index["coverage"][0]["coverage_kind"] = "known_boundary"
    index["coverage"][0]["known_divergence_id"] = "known-tera-boundary"
    _refresh_index_digest(index)

    with pytest.raises(CorpusValidationError, match=r"fixture known divergence.*not defined"):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)


def test_rejects_known_boundary_with_a_definition_that_does_not_affect_capability(
    tmp_path: Path,
) -> None:
    catalog, fixtures, _ = _complete_corpus_documents()
    fixtures[0]["classification_policy"]["known_divergence_id"] = "known-tera-boundary"
    _refresh_fixture_digest(fixtures[0])
    index = _index_document(fixtures, catalog)
    index["classifier"]["known_divergence_definitions"] = [
        {
            "known_divergence_id": "known-tera-boundary",
            "affected_capability_ids": [catalog.definitions[1].value],
        }
    ]
    index["coverage"][0]["coverage_kind"] = "known_boundary"
    index["coverage"][0]["known_divergence_id"] = "known-tera-boundary"
    _refresh_index_digest(index)

    with pytest.raises(CorpusValidationError, match="does not cover fixture capability"):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)


def test_rejects_an_unbound_known_divergence_fixture_hidden_by_reviewed_coverage(
    tmp_path: Path,
) -> None:
    catalog, fixtures, _ = _complete_corpus_documents()
    known_divergence_fixture = _fixture_document(
        "fixture-known-divergence", [catalog.definitions[0].value]
    )
    known_divergence_fixture["classification_policy"]["known_divergence_id"] = (
        "invented-known-divergence"
    )
    _refresh_fixture_digest(known_divergence_fixture)
    fixtures.append(known_divergence_fixture)
    index = _index_document(fixtures, catalog)
    index["coverage"][0]["fixture_ids"] = ["fixture-01"]
    _refresh_index_digest(index)

    with pytest.raises(CorpusValidationError, match=r"fixture known divergence.*not defined"):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)


def test_rejects_known_divergence_fixture_with_unaffected_capability(
    tmp_path: Path,
) -> None:
    catalog, fixtures, _ = _complete_corpus_documents()
    known_divergence_fixture = _fixture_document(
        "fixture-known-divergence", [catalog.definitions[0].value]
    )
    known_divergence_fixture["classification_policy"]["known_divergence_id"] = "known-tera-boundary"
    _refresh_fixture_digest(known_divergence_fixture)
    fixtures.append(known_divergence_fixture)
    index = _index_document(fixtures, catalog)
    index["classifier"]["known_divergence_definitions"] = [
        {
            "known_divergence_id": "known-tera-boundary",
            "affected_capability_ids": [catalog.definitions[1].value],
        }
    ]
    index["coverage"][0]["fixture_ids"] = ["fixture-01"]
    _refresh_index_digest(index)

    with pytest.raises(CorpusValidationError, match="does not cover fixture capability"):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)


def test_public_fixture_surface_does_not_expose_authoritative_full_state() -> None:
    sensitive_value = "secretmon"
    fixture_document = _fixture_document("fixture-execution-copy", ["gen9.legality.move.selection"])
    fixture_document["initial_authoritative_full_state"]["players"]["p1"]["team"][0][
        "species_id"
    ] = sensitive_value
    _refresh_fixture_digest(fixture_document)
    fixture = DifferentialFixture.from_document(fixture_document)

    assert not hasattr(fixture, "execution_document")
    assert "_execution_document" not in asdict(fixture)
    assert sensitive_value not in repr(fixture)
    assert sensitive_value not in json.dumps(asdict(fixture), sort_keys=True)

    execution_document = fixture._execution_document_for_runner()
    execution_document["seed"]["seed_value"] = "mutated"  # type: ignore[index]

    assert fixture._execution_document_for_runner()["seed"]["seed_value"] == "0000000000000001"  # type: ignore[index]


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "message"),
    [
        (
            "player_views",
            "reverse-players",
            "player views must be ordered p1, p2",
        ),
        (
            "joint_action_intent",
            "duplicate-p1-action",
            "joint action intent must contain p1 and p2 exactly once",
        ),
    ],
)
def test_rejects_noncanonical_player_or_action_actor_closure(
    tmp_path: Path, field_name: str, invalid_value: str, message: str
) -> None:
    catalog, fixtures, _ = _complete_corpus_documents()
    if invalid_value == "reverse-players":
        fixtures[0][field_name] = list(reversed(fixtures[0][field_name]))
    else:
        fixtures[0][field_name][1]["actor"] = "p1"
    _refresh_fixture_digest(fixtures[0])
    index = _index_document(fixtures, catalog)

    with pytest.raises(CorpusValidationError, match=message):
        DifferentialCorpus.load(_write_corpus(tmp_path, index, fixtures), catalog)


def test_rejects_a_fixture_directory_symlink(tmp_path: Path) -> None:
    catalog, fixtures, index = _complete_corpus_documents()
    corpus_path = _write_corpus(tmp_path, index, fixtures)
    target = tmp_path / "fixture-target.json"
    target.write_text("{}", encoding="utf-8")
    link = corpus_path / "fixtures" / "linked-fixture.json"
    try:
        link.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")

    with pytest.raises(CorpusValidationError, match="non-regular fixture entry"):
        DifferentialCorpus.load(corpus_path, catalog)


def test_rejects_a_symlinked_corpus_index_before_reading_it(tmp_path: Path) -> None:
    catalog, fixtures, index = _complete_corpus_documents()
    corpus_path = _write_corpus(tmp_path, index, fixtures)
    target = tmp_path / "index-target.json"
    target.write_bytes(canonicalize(index))
    index_path = corpus_path / "index.json"
    index_path.unlink()
    try:
        index_path.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")

    with pytest.raises(CorpusValidationError, match="corpus index is not a regular file"):
        DifferentialCorpus.load(corpus_path, catalog)


def test_default_schema_resource_matches_the_authoritative_source_bytes() -> None:
    from battlebelief_lab.differential import corpus as corpus_module

    for filename in (
        "differential-corpus.schema.json",
        "differential-fixture.schema.json",
    ):
        assert (
            corpus_module._schema_resource(filename, None).read_bytes()
            == (_REPOSITORY_ROOT / "schemas/evaluation" / filename).read_bytes()
        )


def test_lab_wheel_configuration_force_includes_authoritative_differential_schemas() -> None:
    pyproject = tomllib.loads(
        (_REPOSITORY_ROOT / "packages/battlebelief-lab/pyproject.toml").read_text(encoding="utf-8")
    )
    force_include = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]

    assert force_include == {
        "schemas/evaluation/capability-qualification.schema.json": (
            "battlebelief_lab/differential/schemas/capability-qualification.schema.json"
        ),
        "schemas/evaluation/differential-corpus.schema.json": (
            "battlebelief_lab/differential/schemas/differential-corpus.schema.json"
        ),
        "schemas/evaluation/differential-fixture.schema.json": (
            "battlebelief_lab/differential/schemas/differential-fixture.schema.json"
        ),
        "schemas/evaluation/differential-result.schema.json": (
            "battlebelief_lab/differential/schemas/differential-result.schema.json"
        ),
    }
    sdist_force_include = pyproject["tool"]["hatch"]["build"]["targets"]["sdist"]["force-include"]
    assert sdist_force_include == {
        "../../schemas/evaluation/capability-qualification.schema.json": (
            "schemas/evaluation/capability-qualification.schema.json"
        ),
        "../../schemas/evaluation/differential-corpus.schema.json": (
            "schemas/evaluation/differential-corpus.schema.json"
        ),
        "../../schemas/evaluation/differential-fixture.schema.json": (
            "schemas/evaluation/differential-fixture.schema.json"
        ),
        "../../schemas/evaluation/differential-result.schema.json": (
            "schemas/evaluation/differential-result.schema.json"
        ),
    }
    assert pyproject["tool"]["hatch"]["build"]["hooks"]["custom"] == {"path": "hatch_build.py"}


def test_lab_hatch_hook_resolves_evaluation_schemas_from_checkout_and_sdist_layouts(
    tmp_path: Path,
) -> None:
    hook = runpy.run_path(str(_REPOSITORY_ROOT / "packages/battlebelief-lab/hatch_build.py"))
    schema_directory = hook["_schema_directory"]
    checkout_root = tmp_path / "checkout/repository/packages/battlebelief-lab"
    checkout_schema_directory = tmp_path / "checkout/repository/schemas/evaluation"
    sdist_root = tmp_path / "sdist/battlebelief-lab"
    sdist_schema_directory = sdist_root / "schemas/evaluation"
    checkout_schema_directory.mkdir(parents=True)
    sdist_schema_directory.mkdir(parents=True)

    assert schema_directory(checkout_root) == checkout_schema_directory
    assert schema_directory(sdist_root) == sdist_schema_directory
