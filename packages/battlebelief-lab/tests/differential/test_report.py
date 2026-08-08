"""Tests for sanitized, deterministic differential report serialization."""

from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import battlebelief_lab.differential.report as report
from battlebelief_core.canonicalization import manifest_digest
from battlebelief_lab.differential.classifier import DivergenceClass
from battlebelief_lab.differential.runner import FixtureResult, FixtureResultProvenance


def _digest(label: str) -> str:
    return manifest_digest({"synthetic": label})


def _authoritative_result_schema_digest() -> str:
    schema_path = (
        Path(__file__).resolve().parents[4] / "schemas/evaluation/differential-result.schema.json"
    )
    return "sha256:" + sha256(schema_path.read_bytes()).hexdigest()


def _result() -> FixtureResult:
    provenance = FixtureResultProvenance(
        corpus_id="gen9ou-differential",
        corpus_version="1",
        corpus_digest=_digest("corpus"),
        ruleset_id="gen9ou-ruleset",
        ruleset_digest=_digest("ruleset"),
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
    return FixtureResult(
        fixture_id="fixture-a",
        fixture_digest=_digest("fixture"),
        execution_status="completed",
        divergence_class=DivergenceClass.UNCLASSIFIED,
        failure_class=None,
        failure_origin=None,
        differing_fields=("hp",),
        known_divergence_id=None,
        synthetic=True,
        provenance=provenance,
        runner_id="battlebelief-differential-runner",
        runner_version="1",
        runner_source_digest=_digest("runner"),
        classifier_id="battlebelief-differential-classifier",
        classifier_version="1",
        classifier_source_digest=_digest("classifier"),
        seed_id="synthetic-seed",
        seed_digest=_digest("seed"),
    )


def test_report_module_exposes_canonical_fixture_result_rendering() -> None:
    assert hasattr(report, "render_fixture_result")


def test_report_is_repeatable_and_contains_no_observation_or_exception_payload() -> None:
    result = _result()

    first = report.render_fixture_result(result)
    second = report.render_fixture_result(result)

    assert first == second
    assert b"unclassified" in first
    assert b"differing_fields" in first
    assert b"private crash" not in first
    assert b"initial_authoritative_full_state" not in first
    assert b"C:\\\\" not in first


def test_result_schema_accepts_sanitized_result_and_rejects_unknown_fields() -> None:
    schema_path = (
        Path(__file__).resolve().parents[4] / "schemas/evaluation/differential-result.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    document = _result().to_dict()

    assert list(Draft202012Validator(schema).iter_errors(document)) == []
    document["raw_exception"] = "private"
    assert list(Draft202012Validator(schema).iter_errors(document))


def test_completed_match_cannot_expose_differing_fields_in_result_or_schema() -> None:
    with pytest.raises(ValueError, match="match"):
        replace(_result(), divergence_class=DivergenceClass.MATCH, differing_fields=("hp",))

    schema_path = (
        Path(__file__).resolve().parents[4] / "schemas/evaluation/differential-result.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    contradictory = _result().to_dict()
    contradictory["divergence_class"] = "match"
    contradictory["differing_fields"] = ["hp"]

    assert list(Draft202012Validator(schema).iter_errors(contradictory))


@pytest.mark.parametrize(
    ("failure_class", "failure_origin"),
    [("timeout", None), (None, "oracle")],
)
def test_result_schema_rejects_skipped_result_with_only_one_failure_field(
    failure_class: str | None,
    failure_origin: str | None,
) -> None:
    schema_path = (
        Path(__file__).resolve().parents[4] / "schemas/evaluation/differential-result.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    skipped = _result().to_dict()
    skipped["execution_status"] = "skipped"
    skipped["divergence_class"] = None
    skipped["failure_class"] = failure_class
    skipped["failure_origin"] = failure_origin

    assert list(Draft202012Validator(schema).iter_errors(skipped))


@pytest.mark.parametrize("invalid_id", ["C:\\private-known", "oracle.internal.example"])
def test_public_result_construction_rejects_unsafe_known_divergence_id_and_report(
    invalid_id: str,
) -> None:
    unsafe = _result()
    object.__setattr__(unsafe, "divergence_class", DivergenceClass.KNOWN_DIVERGENCE)
    object.__setattr__(unsafe, "known_divergence_id", invalid_id)

    with pytest.raises(ValueError, match="known divergence"):
        unsafe.to_dict()
    with pytest.raises(ValueError, match="known divergence"):
        report.render_fixture_result(unsafe)


@pytest.mark.parametrize(
    ("schema_id", "schema_version"),
    [
        ("urn:battlebelief:schema:evaluation:differential-result:v2", "1"),
        ("urn:battlebelief:schema:evaluation:differential-result:v1", "2"),
    ],
)
def test_public_result_provenance_requires_exact_v1_result_schema(
    schema_id: str,
    schema_version: str,
) -> None:
    with pytest.raises(ValueError, match="result schema"):
        replace(
            _result().provenance,
            result_schema_id=schema_id,
            result_schema_version=schema_version,
        )


def test_public_result_provenance_rejects_a_forged_v1_result_schema_digest() -> None:
    forged_digest = _digest("result-schema")
    assert forged_digest != _authoritative_result_schema_digest()

    with pytest.raises(ValueError, match="result schema digest"):
        replace(_result().provenance, result_schema_digest=forged_digest)
