"""Focused tests for the data-only differential corpus validator."""

import json
from pathlib import Path

import pytest
from tools import check_schemas, validate_differential_corpus

from battlebelief_core.canonicalization import canonicalize
from battlebelief_core.domain.engine_capabilities import CapabilityCatalog
from battlebelief_lab.differential.corpus import DifferentialCorpus

ROOT = Path(__file__).resolve().parents[2]


def test_authoritative_corpus_v1_is_closed_and_covers_the_task_26_catalog() -> None:
    catalog = CapabilityCatalog.from_document(
        json.loads(
            (ROOT / "artifacts/gen9ou/m2/engine-capability-catalog-v1.json").read_text(
                encoding="utf-8"
            )
        )
    )

    corpus = DifferentialCorpus.load(
        ROOT / "artifacts/gen9ou/m2/differential/corpus-v1",
        catalog,
    )

    assert corpus.corpus_id == "gen9ou-differential"
    assert corpus.corpus_version == "1"
    assert len(corpus.fixtures) == 13
    assert tuple(corpus.capability_coverage) == tuple(
        definition.value for definition in catalog.definitions
    )
    assert all(corpus.capability_coverage[definition.value] for definition in catalog.definitions)


def test_validator_fails_closed_when_the_authoritative_catalog_is_missing(tmp_path: Path) -> None:
    assert validate_differential_corpus.collect_errors(tmp_path) == [
        "engine capability catalog is missing"
    ]


def test_validator_rejects_duplicate_authoritative_catalog_members(tmp_path: Path) -> None:
    catalog_path = tmp_path / "artifacts/gen9ou/m2/engine-capability-catalog-v1.json"
    catalog_path.parent.mkdir(parents=True)
    source = (ROOT / "artifacts/gen9ou/m2/engine-capability-catalog-v1.json").read_text(
        encoding="utf-8"
    )
    catalog_path.write_text(
        source.replace(
            '  "schema_version": 1,\n',
            '  "schema_version": 1,\n  "schema_version": 1,\n',
            1,
        ),
        encoding="utf-8",
    )

    assert validate_differential_corpus.collect_errors(tmp_path) == [
        "engine capability catalog is invalid"
    ]


def test_validator_redacts_corpus_failure_details(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog_path = tmp_path / "artifacts/gen9ou/m2/engine-capability-catalog-v1.json"
    catalog_path.parent.mkdir(parents=True)
    catalog_path.write_bytes(
        (ROOT / "artifacts/gen9ou/m2/engine-capability-catalog-v1.json").read_bytes()
    )
    (tmp_path / "artifacts/gen9ou/m2/differential/corpus-v1").mkdir(parents=True)
    sensitive_value = "sensitive-full-state-value-must-not-escape"

    def raise_sensitive_corpus_error(*_arguments: object, **_keywords: object) -> None:
        raise validate_differential_corpus.CorpusValidationError(sensitive_value)

    monkeypatch.setattr(
        validate_differential_corpus.DifferentialCorpus,
        "load",
        raise_sensitive_corpus_error,
    )

    errors = validate_differential_corpus.collect_errors(tmp_path)

    assert errors == ["differential corpus is invalid"]
    assert sensitive_value not in "\n".join(errors)


def test_validator_catches_canonicalizer_recursion_without_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog_path = tmp_path / "artifacts/gen9ou/m2/engine-capability-catalog-v1.json"
    catalog_path.parent.mkdir(parents=True)
    catalog_path.write_bytes(
        (ROOT / "artifacts/gen9ou/m2/engine-capability-catalog-v1.json").read_bytes()
    )
    (tmp_path / "artifacts/gen9ou/m2/differential/corpus-v1").mkdir(parents=True)

    def trigger_deep_canonicalization(*_arguments: object, **_keywords: object) -> None:
        value: object = 0
        for _ in range(1_100):
            value = {"nested": value}
        canonicalize(value)

    monkeypatch.setattr(
        validate_differential_corpus.DifferentialCorpus,
        "load",
        trigger_deep_canonicalization,
    )

    assert validate_differential_corpus.collect_errors(tmp_path) == [
        "differential corpus is invalid"
    ]


def test_schema_checker_explicitly_registers_differential_evaluation_examples() -> None:
    schema_root = ROOT / "schemas"

    assert check_schemas.EXAMPLE_SCHEMA_MAP["differential-corpus.example.json"] == (
        "differential-corpus.schema.json"
    )
    assert check_schemas.EXAMPLE_SCHEMA_MAP["differential-fixture.example.json"] == (
        "differential-fixture.schema.json"
    )
    assert (
        check_schemas.INVALID_EXAMPLE_SCHEMA_MAP["invalid/differential-corpus.invalid.json"]
        == "differential-corpus.schema.json"
    )
    assert (
        check_schemas.INVALID_EXAMPLE_SCHEMA_MAP["invalid/differential-fixture.invalid.json"]
        == "differential-fixture.schema.json"
    )
    assert check_schemas._schema_path_for_example(
        schema_root, "differential-corpus.schema.json"
    ) == (schema_root / "evaluation/differential-corpus.schema.json")
