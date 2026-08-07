"""Synthetic-only rejection tests for future capability qualification evidence."""

from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import battlebelief_lab.differential as differential
from battlebelief_core.canonicalization import manifest_digest
from battlebelief_lab.differential.classifier import DivergenceClass
from battlebelief_lab.differential.evidence import (
    CapabilityQualificationEvidence,
    CapabilityQualificationExpectation,
)
from battlebelief_lab.differential.runner import FixtureResult, FixtureResultProvenance


def _digest(label: str) -> str:
    return manifest_digest({"synthetic": label})


def _authoritative_result_schema_digest() -> str:
    schema_path = (
        Path(__file__).resolve().parents[4] / "schemas/evaluation/differential-result.schema.json"
    )
    return "sha256:" + sha256(schema_path.read_bytes()).hexdigest()


def _provenance(environment_id: str = "environment-a") -> FixtureResultProvenance:
    return FixtureResultProvenance(
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
        environment_id=environment_id,
        environment_digest=_digest(environment_id),
        canonicalization_profile_id="canonicalization-profile",
        canonicalization_profile_version="1",
        canonicalization_profile_digest=_digest("canonicalization"),
        result_schema_id="urn:battlebelief:schema:evaluation:differential-result:v1",
        result_schema_version="1",
        result_schema_digest=_authoritative_result_schema_digest(),
    )


def _result(
    *,
    environment_id: str = "environment-a",
    synthetic: bool = True,
) -> FixtureResult:
    return FixtureResult(
        fixture_id="fixture-a",
        fixture_digest=_digest("fixture-a"),
        execution_status="completed",
        divergence_class=DivergenceClass.MATCH,
        failure_class=None,
        failure_origin=None,
        differing_fields=(),
        known_divergence_id=None,
        synthetic=synthetic,
        provenance=_provenance(environment_id),
        runner_id="battlebelief-differential-runner",
        runner_version="1",
        runner_source_digest=_digest("runner"),
        classifier_id="battlebelief-differential-classifier",
        classifier_version="1",
        classifier_source_digest=_digest("classifier"),
        seed_id="synthetic-seed",
        seed_digest=_digest("seed"),
    )


def _expectation(
    *, environments: tuple[str, ...] = ("environment-a",)
) -> CapabilityQualificationExpectation:
    result = _result()
    return CapabilityQualificationExpectation(
        capability_id="gen9.legality.move.selection",
        required_fixtures={"fixture-a": _digest("fixture-a")},
        required_environments={
            environment_id: _digest(environment_id) for environment_id in environments
        },
        provenance=result.provenance,
        runner_id=result.runner_id,
        runner_version=result.runner_version,
        runner_source_digest=result.runner_source_digest,
        classifier_id=result.classifier_id,
        classifier_version=result.classifier_version,
        classifier_source_digest=result.classifier_source_digest,
    )


def test_public_api_exports_non_exact_capability_evidence() -> None:
    assert hasattr(differential, "CapabilityQualificationEvidence")


def test_complete_synthetic_matrix_is_never_exact_in_task_28() -> None:
    evidence = CapabilityQualificationEvidence.assess(_expectation(), [_result()])

    assert evidence.all_required_fixtures_present is True
    assert evidence.environment_matrix_complete is True
    assert evidence.all_executed is True
    assert evidence.all_results_match is True
    assert evidence.identities_match is True
    assert evidence.contains_synthetic is True
    assert evidence.capability_status == "unknown"
    assert evidence.exact_eligible is False


def test_complete_two_environment_matrix_can_match_identities_but_remains_non_exact() -> None:
    evidence = CapabilityQualificationEvidence.assess(
        _expectation(environments=("environment-a", "environment-b")),
        [_result(environment_id="environment-a"), _result(environment_id="environment-b")],
    )

    assert evidence.environment_matrix_complete is True
    assert evidence.identities_match is True
    assert evidence.exact_eligible is False


def test_missing_row_is_not_exact() -> None:
    evidence = CapabilityQualificationEvidence.assess(_expectation(), [])

    assert evidence.all_required_fixtures_present is False
    assert evidence.environment_matrix_complete is False
    assert evidence.exact_eligible is False


def test_incomplete_environment_matrix_is_not_exact() -> None:
    evidence = CapabilityQualificationEvidence.assess(
        _expectation(environments=("environment-a", "environment-b")),
        [_result(environment_id="environment-a")],
    )

    assert evidence.all_required_fixtures_present is True
    assert evidence.environment_matrix_complete is False
    assert evidence.exact_eligible is False


@pytest.mark.parametrize(
    "result",
    [
        replace(
            _result(),
            execution_status="skipped",
            divergence_class=None,
        ),
        replace(
            _result(),
            execution_status="failed",
            divergence_class=None,
            failure_class="crash",
            failure_origin="engine",
        ),
        replace(
            _result(),
            execution_status="failed",
            divergence_class=None,
            failure_class="backend_error",
            failure_origin="engine",
        ),
        replace(
            _result(),
            divergence_class=DivergenceClass.UNCLASSIFIED,
            differing_fields=("hp",),
        ),
        replace(
            _result(),
            divergence_class=DivergenceClass.KNOWN_DIVERGENCE,
            known_divergence_id="frozen",
            differing_fields=("hp",),
        ),
    ],
)
def test_nonmatching_or_unexecuted_result_is_not_exact(result: FixtureResult) -> None:
    evidence = CapabilityQualificationEvidence.assess(_expectation(), [result])

    assert evidence.exact_eligible is False
    assert not (evidence.all_executed and evidence.all_results_match)


@pytest.mark.parametrize(
    "changed_result",
    [
        replace(
            _result(), provenance=replace(_result().provenance, wheel_digest=_digest("wrong-wheel"))
        ),
        replace(
            _result(),
            provenance=replace(
                _result().provenance, oracle_build_manifest_digest=_digest("wrong-oracle")
            ),
        ),
        replace(
            _result(),
            provenance=replace(_result().provenance, ruleset_digest=_digest("wrong-ruleset")),
        ),
        replace(
            _result(),
            provenance=replace(_result().provenance, corpus_digest=_digest("wrong-corpus")),
        ),
        replace(_result(), classifier_source_digest=_digest("wrong-classifier")),
    ],
)
def test_identity_mismatch_is_not_exact(changed_result: FixtureResult) -> None:
    evidence = CapabilityQualificationEvidence.assess(_expectation(), [changed_result])

    assert evidence.identities_match is False
    assert evidence.exact_eligible is False


def test_capability_qualification_schema_rejects_an_exact_claim() -> None:
    schema_path = (
        Path(__file__).resolve().parents[4]
        / "schemas/evaluation/capability-qualification.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    document = CapabilityQualificationEvidence.assess(_expectation(), [_result()]).to_dict()

    assert list(Draft202012Validator(schema).iter_errors(document)) == []
    document["exact_eligible"] = True
    assert list(Draft202012Validator(schema).iter_errors(document))


def test_evidence_does_not_treat_a_contradictory_match_as_a_match() -> None:
    contradictory = _result(synthetic=False)
    object.__setattr__(contradictory, "differing_fields", ("hp",))

    evidence = CapabilityQualificationEvidence.assess(_expectation(), [contradictory])

    assert evidence.all_results_match is False
    assert evidence.exact_eligible is False
