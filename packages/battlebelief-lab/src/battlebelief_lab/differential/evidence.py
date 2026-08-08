"""Fail-closed, synthetic-only qualification-evidence eligibility checks."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from types import MappingProxyType
from typing import Literal

from battlebelief_lab.differential.classifier import DivergenceClass
from battlebelief_lab.differential.runner import FixtureResult, FixtureResultProvenance

_CAPABILITY_ID_RE = re.compile(
    r"^gen9\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*){2,7}$"
)
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_VERSION_RE = re.compile(r"^[1-9][0-9]*$")


@dataclass(frozen=True, slots=True)
class CapabilityQualificationExpectation:
    """The complete identity matrix a future Task-29 claim would have to satisfy."""

    capability_id: str
    required_fixtures: Mapping[str, str]
    required_environments: Mapping[str, str]
    provenance: FixtureResultProvenance
    runner_id: str
    runner_version: str
    runner_source_digest: str
    classifier_id: str
    classifier_version: str
    classifier_source_digest: str

    def __post_init__(self) -> None:
        if _CAPABILITY_ID_RE.fullmatch(self.capability_id) is None:
            raise ValueError("capability evidence capability ID is invalid")
        fixtures = dict(self.required_fixtures)
        environments = dict(self.required_environments)
        if not fixtures or not environments:
            raise ValueError("capability evidence requires fixtures and environments")
        if any(_ID_RE.fullmatch(identifier) is None for identifier in fixtures) or any(
            _DIGEST_RE.fullmatch(digest) is None for digest in fixtures.values()
        ):
            raise ValueError("required fixture identity is invalid")
        if any(_ID_RE.fullmatch(identifier) is None for identifier in environments) or any(
            _DIGEST_RE.fullmatch(digest) is None for digest in environments.values()
        ):
            raise ValueError("required environment identity is invalid")
        if tuple(fixtures) != tuple(sorted(fixtures)) or tuple(environments) != tuple(
            sorted(environments)
        ):
            raise ValueError("capability evidence matrix must have canonical ordering")
        if not isinstance(self.provenance, FixtureResultProvenance):
            raise TypeError("capability evidence provenance is invalid")
        if any(_ID_RE.fullmatch(value) is None for value in (self.runner_id, self.classifier_id)):
            raise ValueError("capability evidence implementation ID is invalid")
        if any(
            _VERSION_RE.fullmatch(value) is None
            for value in (self.runner_version, self.classifier_version)
        ):
            raise ValueError("capability evidence implementation version is invalid")
        if any(
            _DIGEST_RE.fullmatch(value) is None
            for value in (self.runner_source_digest, self.classifier_source_digest)
        ):
            raise ValueError("capability evidence implementation digest is invalid")
        object.__setattr__(self, "required_fixtures", MappingProxyType(fixtures))
        object.__setattr__(self, "required_environments", MappingProxyType(environments))


@dataclass(frozen=True, slots=True)
class CapabilityQualificationEvidence:
    """Task-28 evidence projection that is mechanically unable to create an exact claim."""

    capability_id: str
    required_fixture_count: int
    required_environment_count: int
    result_count: int
    all_required_fixtures_present: bool
    environment_matrix_complete: bool
    all_executed: bool
    all_results_match: bool
    identities_match: bool
    contains_synthetic: bool
    capability_status: Literal["unknown"] = "unknown"
    exact_eligible: bool = False

    def __post_init__(self) -> None:
        if _CAPABILITY_ID_RE.fullmatch(self.capability_id) is None:
            raise ValueError("capability qualification evidence ID is invalid")
        if any(
            type(value) is not int or value < 0
            for value in (
                self.required_fixture_count,
                self.required_environment_count,
                self.result_count,
            )
        ):
            raise ValueError("capability qualification evidence counts are invalid")
        if any(
            type(value) is not bool
            for value in (
                self.all_required_fixtures_present,
                self.environment_matrix_complete,
                self.all_executed,
                self.all_results_match,
                self.identities_match,
                self.contains_synthetic,
                self.exact_eligible,
            )
        ):
            raise TypeError("capability qualification evidence flags must be bool")
        if self.exact_eligible:
            raise ValueError("Task-28 evidence cannot create an exact capability claim")
        if self.capability_status != "unknown":
            raise ValueError("Task-28 evidence status must remain unknown")

    @classmethod
    def assess(
        cls,
        expectation: CapabilityQualificationExpectation,
        results: Sequence[FixtureResult],
    ) -> CapabilityQualificationEvidence:
        """Project a result matrix into conservative eligibility facts, never an exact claim."""

        if not isinstance(expectation, CapabilityQualificationExpectation):
            raise TypeError("capability qualification expectation is required")
        if any(not isinstance(result, FixtureResult) for result in results):
            raise TypeError("capability qualification results must be FixtureResult values")
        expected_cells = {
            (fixture_id, environment_id)
            for fixture_id in expectation.required_fixtures
            for environment_id in expectation.required_environments
        }
        actual_cells = {(result.fixture_id, result.provenance.environment_id) for result in results}
        actual_fixture_ids = {result.fixture_id for result in results}
        all_required_fixtures_present = set(expectation.required_fixtures).issubset(
            actual_fixture_ids
        )
        environment_matrix_complete = actual_cells == expected_cells and len(results) == len(
            actual_cells
        )
        identities_match = (
            all(_matches_expectation(result, expectation) for result in results)
            and environment_matrix_complete
        )
        all_executed = environment_matrix_complete and all(
            result.execution_status == "completed" for result in results
        )
        all_results_match = environment_matrix_complete and all(
            result.divergence_class is DivergenceClass.MATCH and not result.differing_fields
            for result in results
        )
        contains_synthetic = any(result.synthetic for result in results)
        return cls(
            capability_id=expectation.capability_id,
            required_fixture_count=len(expectation.required_fixtures),
            required_environment_count=len(expectation.required_environments),
            result_count=len(results),
            all_required_fixtures_present=all_required_fixtures_present,
            environment_matrix_complete=environment_matrix_complete,
            all_executed=all_executed,
            all_results_match=all_results_match,
            identities_match=identities_match,
            contains_synthetic=contains_synthetic,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "capability_id": self.capability_id,
            "required_fixture_count": self.required_fixture_count,
            "required_environment_count": self.required_environment_count,
            "result_count": self.result_count,
            "all_required_fixtures_present": self.all_required_fixtures_present,
            "environment_matrix_complete": self.environment_matrix_complete,
            "all_executed": self.all_executed,
            "all_results_match": self.all_results_match,
            "identities_match": self.identities_match,
            "contains_synthetic": self.contains_synthetic,
            "capability_status": "unknown",
            "exact_eligible": False,
        }


def _matches_expectation(
    result: FixtureResult,
    expectation: CapabilityQualificationExpectation,
) -> bool:
    expected_fixture_digest = expectation.required_fixtures.get(result.fixture_id)
    expected_environment_digest = expectation.required_environments.get(
        result.provenance.environment_id
    )
    return (
        expected_fixture_digest == result.fixture_digest
        and expected_environment_digest == result.provenance.environment_digest
        and all(
            getattr(result.provenance, field_name) == getattr(expectation.provenance, field_name)
            for field_name in _MATCHED_PROVENANCE_FIELDS
        )
        and (
            result.runner_id,
            result.runner_version,
            result.runner_source_digest,
            result.classifier_id,
            result.classifier_version,
            result.classifier_source_digest,
        )
        == (
            expectation.runner_id,
            expectation.runner_version,
            expectation.runner_source_digest,
            expectation.classifier_id,
            expectation.classifier_version,
            expectation.classifier_source_digest,
        )
    )


_EXPLICIT_PROVENANCE_FIELDS = frozenset({"environment_id", "environment_digest"})
_MATCHED_PROVENANCE_FIELDS = tuple(
    field.name
    for field in fields(FixtureResultProvenance)
    if field.name not in _EXPLICIT_PROVENANCE_FIELDS
)


__all__ = ["CapabilityQualificationEvidence", "CapabilityQualificationExpectation"]
