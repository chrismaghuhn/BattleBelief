"""Injected, synthetic-testable mechanics comparison runner.

The runner deliberately has no process, clock, random, filesystem, or native
``poke_engine`` dependency.  Callers inject both execution sides and this
module projects only their canonical public mechanics observations.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import Literal, cast

from battlebelief_core.canonicalization import canonicalize, manifest_digest
from battlebelief_lab.differential.classifier import (
    ClassifierConfigurationError,
    DifferentialClassifier,
    DivergenceClass,
)
from battlebelief_lab.differential.corpus import DifferentialFixture
from battlebelief_runtime.adapters.poke_engine import PokeEngineMappingFailure

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_VERSION_RE = re.compile(r"^[1-9][0-9]*$")
_RESULT_SCHEMA_ID = "urn:battlebelief:schema:evaluation:differential-result:v1"
_RESULT_SCHEMA_VERSION = "1"
_RESULT_SCHEMA_FILENAME = "differential-result.schema.json"
_LOCAL_ABSOLUTE_PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|(?<![A-Za-z0-9])/(?:[^\s/]+))")
_HOSTNAME_RE = re.compile(
    r"(?i)\b(?:localhost|(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}|"
    r"(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})(?:\.(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})){3})\b"
)
_URI_RE = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://")
_EXCEPTION_TEXT_RE = re.compile(r"(?i)(?:traceback|exception|\b(?:value|type|runtime)error\s*:)")
_RAW_STATE_TEXT_RE = re.compile(
    r"(?i)(?:^\||\b(?:raw|native|authoritative|full)[ _-]?state\b|\bside_(?:one|two)\b)"
)
_PRIVATE_MEMBER_NAMES = frozenset(
    {
        "authoritative_state",
        "exception",
        "full_state",
        "native_state",
        "raw_state",
        "stack",
        "traceback",
    }
)
_COMPARISON_FIELDS = frozenset(
    {
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
    }
)
_FAILURE_CLASSES = frozenset(
    {
        "unavailable",
        "artifact_mismatch",
        "timeout",
        "crash",
        "malformed_output",
        "mapping_failure",
        "backend_error",
    }
)
_FAILURE_ORIGINS = frozenset({"oracle", "engine", "runtime_adapter"})
_EXECUTION_STATUSES = frozenset({"completed", "skipped", "failed"})


class RunnerConfigurationError(ValueError):
    """Raised for a non-secret configuration mismatch before execution."""


def _source_digest() -> str:
    return "sha256:" + sha256(Path(__file__).read_bytes()).hexdigest()


def _authoritative_result_schema_digest() -> str:
    """Digest the installed result-schema resource, with a source-tree fallback."""

    try:
        package_resource = resources.files("battlebelief_lab.differential").joinpath(
            "schemas", _RESULT_SCHEMA_FILENAME
        )
        if package_resource.is_file():
            return "sha256:" + sha256(package_resource.read_bytes()).hexdigest()
        source_path = (
            Path(__file__).resolve().parents[5]
            / "schemas"
            / "evaluation"
            / (_RESULT_SCHEMA_FILENAME)
        )
        if source_path.is_file():
            return "sha256:" + sha256(source_path.read_bytes()).hexdigest()
    except (IndexError, OSError) as error:
        raise ValueError(
            "authoritative differential-result schema resource is unavailable"
        ) from error
    raise ValueError("authoritative differential-result schema resource is unavailable")


def _copy_canonical_json(value: object, field_name: str) -> object:
    try:
        copied = json.loads(canonicalize(value))
    except (OverflowError, RecursionError, TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a finite canonical JSON value") from error
    return copied


def _validate_public_safe_value(value: object, location: str) -> None:
    """Reject operational data before an observation becomes public result material."""

    if type(value) is str:
        if (
            "\x00" in value
            or "\r" in value
            or "\n" in value
            or _LOCAL_ABSOLUTE_PATH_RE.search(value)
            or _HOSTNAME_RE.search(value)
            or _URI_RE.search(value)
            or _EXCEPTION_TEXT_RE.search(value)
            or _RAW_STATE_TEXT_RE.search(value)
        ):
            raise ValueError(f"{location} is not public-safe")
        return
    if value is None or type(value) in {bool, int, float}:
        return
    if isinstance(value, list):
        for index, nested_value in enumerate(value):
            _validate_public_safe_value(nested_value, f"{location}[{index}]")
        return
    if isinstance(value, Mapping):
        for name, nested_value in value.items():
            if type(name) is not str:
                raise ValueError(f"{location} is not public-safe")
            if name.lower() in _PRIVATE_MEMBER_NAMES:
                raise ValueError(f"{location} is not public-safe")
            _validate_public_safe_value(name, f"{location} member name")
            _validate_public_safe_value(nested_value, f"{location}.{name}")
        return
    raise ValueError(f"{location} is not public-safe")


def _freeze_canonical_json(value: object) -> object:
    """Recursively freeze a canonical JSON value before it reaches public observation state."""

    if isinstance(value, Mapping):
        return MappingProxyType(
            {
                str(name): _freeze_canonical_json(nested_value)
                for name, nested_value in value.items()
            }
        )
    if isinstance(value, list):
        return tuple(_freeze_canonical_json(nested_value) for nested_value in value)
    return value


def _thaw_canonical_json(value: object) -> object:
    """Return a detached ordinary JSON representation of an immutable observation value."""

    if isinstance(value, Mapping):
        return {
            str(name): _thaw_canonical_json(nested_value) for name, nested_value in value.items()
        }
    if isinstance(value, tuple):
        return [_thaw_canonical_json(nested_value) for nested_value in value]
    return value


def _canonical_string_set(value: object, field_name: str) -> list[str]:
    if not isinstance(value, list) or any(type(item) is not str for item in value):
        raise ValueError(f"{field_name} must be a JSON string array")
    values = cast(list[str], value)
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must not contain duplicates")
    return sorted(values)


@dataclass(frozen=True, slots=True)
class CanonicalMechanicsObservation:
    """Public, implementation-independent mechanics values for declared fields only."""

    fields: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.fields, Mapping):
            raise TypeError("mechanics observation fields must be a mapping")
        unknown_fields = set(self.fields) - _COMPARISON_FIELDS
        if unknown_fields:
            raise ValueError("mechanics observation has an undeclared field")
        canonical_fields: dict[str, object] = {}
        for field_name, raw_value in self.fields.items():
            if type(field_name) is not str:
                raise TypeError("mechanics observation field names must be strings")
            value = _copy_canonical_json(raw_value, field_name)
            _validate_public_safe_value(value, field_name)
            if field_name in {"legal_actions", "effective_types"}:
                value = _canonical_string_set(value, field_name)
            canonical_fields[field_name] = value
        copied = _copy_canonical_json(canonical_fields, "mechanics observation")
        if not isinstance(copied, dict):  # pragma: no cover - guaranteed above
            raise ValueError("mechanics observation must serialize as an object")
        frozen = _freeze_canonical_json(copied)
        if not isinstance(frozen, Mapping):  # pragma: no cover - guaranteed above
            raise ValueError("mechanics observation must freeze as an object")
        object.__setattr__(self, "fields", frozen)

    def has_field(self, field_name: str) -> bool:
        return field_name in self.fields

    def value_for(self, field_name: str) -> object:
        return self.fields[field_name]

    def to_dict(self) -> dict[str, object]:
        thawed = _thaw_canonical_json(self.fields)
        if not isinstance(thawed, dict):  # pragma: no cover - guaranteed by __post_init__
            raise ValueError("mechanics observation must thaw as an object")
        return cast(dict[str, object], thawed)


@dataclass(frozen=True, slots=True)
class DifferentialSideExecution:
    """Successful injected side execution projected into canonical mechanics data."""

    observation: CanonicalMechanicsObservation

    def __post_init__(self) -> None:
        if not isinstance(self.observation, CanonicalMechanicsObservation):
            raise TypeError("side execution requires a canonical mechanics observation")


@dataclass(frozen=True, slots=True)
class DifferentialExecutionFailure:
    """Sanitized synthetic/integration failure supplied by an injected executor."""

    failure_class: str

    def __post_init__(self) -> None:
        if self.failure_class not in _FAILURE_CLASSES:
            raise ValueError("differential failure class is not approved")


@dataclass(frozen=True, slots=True)
class DifferentialExecutionSkip:
    """A deliberate non-execution, optionally with an ADR-0008 failure reason."""

    failure_class: str | None = None

    def __post_init__(self) -> None:
        if self.failure_class is not None and self.failure_class not in _FAILURE_CLASSES:
            raise ValueError("differential skip failure class is not approved")


@dataclass(frozen=True, slots=True)
class FixtureResultProvenance:
    """Path-free, content-addressed closure for one public fixture result."""

    corpus_id: str
    corpus_version: str
    corpus_digest: str
    ruleset_id: str
    ruleset_digest: str
    catalog_id: str
    catalog_version: str
    catalog_digest: str
    oracle_source_manifest_digest: str
    oracle_build_manifest_digest: str
    engine_source_manifest_digest: str
    engine_build_manifest_digest: str
    wheel_digest: str
    runtime_adapter_id: str
    runtime_adapter_version: str
    runtime_adapter_source_digest: str
    environment_id: str
    environment_digest: str
    canonicalization_profile_id: str
    canonicalization_profile_version: str
    canonicalization_profile_digest: str
    result_schema_id: str
    result_schema_version: str
    result_schema_digest: str

    def __post_init__(self) -> None:
        identifiers = (
            self.corpus_id,
            self.ruleset_id,
            self.catalog_id,
            self.runtime_adapter_id,
            self.environment_id,
            self.canonicalization_profile_id,
        )
        if any(_ID_RE.fullmatch(value) is None for value in identifiers):
            raise ValueError("result provenance identity is invalid")
        versions = (
            self.corpus_version,
            self.catalog_version,
            self.runtime_adapter_version,
            self.canonicalization_profile_version,
            self.result_schema_version,
        )
        if any(_VERSION_RE.fullmatch(value) is None for value in versions):
            raise ValueError("result provenance version is invalid")
        if (
            self.result_schema_id,
            self.result_schema_version,
        ) != (_RESULT_SCHEMA_ID, _RESULT_SCHEMA_VERSION):
            raise ValueError("result schema must bind the exact differential-result v1 contract")
        if self.result_schema_digest != _authoritative_result_schema_digest():
            raise ValueError("result schema digest does not bind the authoritative v1 resource")
        digests = (
            self.corpus_digest,
            self.ruleset_digest,
            self.catalog_digest,
            self.oracle_source_manifest_digest,
            self.oracle_build_manifest_digest,
            self.engine_source_manifest_digest,
            self.engine_build_manifest_digest,
            self.wheel_digest,
            self.runtime_adapter_source_digest,
            self.environment_digest,
            self.canonicalization_profile_digest,
            self.result_schema_digest,
        )
        if any(_DIGEST_RE.fullmatch(value) is None for value in digests):
            raise ValueError("result provenance digest is invalid")

    def to_dict(self) -> dict[str, object]:
        return {
            "corpus": {
                "corpus_id": self.corpus_id,
                "corpus_version": self.corpus_version,
                "corpus_digest": self.corpus_digest,
            },
            "ruleset": {"ruleset_id": self.ruleset_id, "ruleset_digest": self.ruleset_digest},
            "catalog": {
                "catalog_id": self.catalog_id,
                "catalog_version": self.catalog_version,
                "catalog_digest": self.catalog_digest,
            },
            "oracle": {
                "source_manifest_digest": self.oracle_source_manifest_digest,
                "build_manifest_digest": self.oracle_build_manifest_digest,
            },
            "engine": {
                "source_manifest_digest": self.engine_source_manifest_digest,
                "build_manifest_digest": self.engine_build_manifest_digest,
                "wheel_digest": self.wheel_digest,
            },
            "runtime_adapter": {
                "adapter_id": self.runtime_adapter_id,
                "adapter_version": self.runtime_adapter_version,
                "source_digest": self.runtime_adapter_source_digest,
            },
            "environment": {
                "environment_id": self.environment_id,
                "environment_digest": self.environment_digest,
            },
            "canonicalization": {
                "profile_id": self.canonicalization_profile_id,
                "profile_version": self.canonicalization_profile_version,
                "profile_digest": self.canonicalization_profile_digest,
            },
            "result_schema": {
                "schema_id": self.result_schema_id,
                "schema_version": self.result_schema_version,
                "schema_digest": self.result_schema_digest,
            },
        }


@dataclass(frozen=True, slots=True)
class FixtureResult:
    """Sanitized public outcome for one fixture; it contains no observations or errors."""

    fixture_id: str
    fixture_digest: str
    execution_status: Literal["completed", "skipped", "failed"]
    divergence_class: DivergenceClass | None
    failure_class: str | None
    failure_origin: str | None
    differing_fields: tuple[str, ...]
    known_divergence_id: str | None
    synthetic: bool
    provenance: FixtureResultProvenance
    runner_id: str
    runner_version: str
    runner_source_digest: str
    classifier_id: str
    classifier_version: str
    classifier_source_digest: str
    seed_id: str
    seed_digest: str

    def __post_init__(self) -> None:
        if _ID_RE.fullmatch(self.fixture_id) is None:
            raise ValueError("fixture result fixture ID is invalid")
        if _DIGEST_RE.fullmatch(self.fixture_digest) is None:
            raise ValueError("fixture result fixture digest is invalid")
        if self.execution_status not in _EXECUTION_STATUSES:
            raise ValueError("fixture result execution status is invalid")
        if self.divergence_class is not None and not isinstance(
            self.divergence_class, DivergenceClass
        ):
            raise TypeError("fixture result divergence class is invalid")
        if self.failure_class is not None and self.failure_class not in _FAILURE_CLASSES:
            raise ValueError("fixture result failure class is invalid")
        if self.failure_origin is not None and self.failure_origin not in _FAILURE_ORIGINS:
            raise ValueError("fixture result failure origin is invalid")
        if (self.failure_class is None) != (self.failure_origin is None):
            raise ValueError("fixture result failure class and origin must agree")
        if self.execution_status == "completed":
            if self.divergence_class is None or self.failure_class is not None:
                raise ValueError("completed result invariants are invalid")
        elif self.divergence_class is not None:
            raise ValueError("non-completed result cannot have a divergence class")
        if self.execution_status == "failed" and self.failure_class is None:
            raise ValueError("failed result requires a failure class and origin")
        if self.execution_status != "completed" and (
            self.differing_fields or self.known_divergence_id is not None
        ):
            raise ValueError("non-completed result must not expose comparison details")
        if self.divergence_class is DivergenceClass.KNOWN_DIVERGENCE:
            if (
                self.known_divergence_id is None
                or _ID_RE.fullmatch(self.known_divergence_id) is None
            ):
                raise ValueError("known divergence result requires a canonical frozen ID")
        elif self.known_divergence_id is not None:
            raise ValueError("only known divergence results may expose a divergence ID")
        if self.differing_fields != tuple(sorted(set(self.differing_fields))):
            raise ValueError("differing fields must be unique and sorted")
        if not set(self.differing_fields).issubset(_COMPARISON_FIELDS):
            raise ValueError("differing fields are not approved mechanics fields")
        if self.execution_status == "completed" and (
            self.divergence_class is DivergenceClass.MATCH
        ) != (not self.differing_fields):
            raise ValueError("completed match status must exactly bind differing fields")
        if type(self.synthetic) is not bool or not isinstance(
            self.provenance, FixtureResultProvenance
        ):
            raise TypeError("fixture result provenance is invalid")
        identities = (
            self.runner_id,
            self.classifier_id,
            self.seed_id,
        )
        if any(_ID_RE.fullmatch(value) is None for value in identities):
            raise ValueError("fixture result identity is invalid")
        if any(
            _VERSION_RE.fullmatch(value) is None
            for value in (self.runner_version, self.classifier_version)
        ):
            raise ValueError("fixture result version is invalid")
        if any(
            _DIGEST_RE.fullmatch(value) is None
            for value in (
                self.runner_source_digest,
                self.classifier_source_digest,
                self.seed_digest,
            )
        ):
            raise ValueError("fixture result digest is invalid")

    def to_dict(self) -> dict[str, object]:
        self.__post_init__()
        return {
            "schema_version": 1,
            "fixture_id": self.fixture_id,
            "fixture_digest": self.fixture_digest,
            "execution_status": self.execution_status,
            "divergence_class": self.divergence_class.value
            if self.divergence_class is not None
            else None,
            "failure_class": self.failure_class,
            "failure_origin": self.failure_origin,
            "differing_fields": list(self.differing_fields),
            "known_divergence_id": self.known_divergence_id,
            "synthetic": self.synthetic,
            "provenance": self.provenance.to_dict(),
            "runner": {
                "runner_id": self.runner_id,
                "runner_version": self.runner_version,
                "runner_source_digest": self.runner_source_digest,
            },
            "classifier": {
                "classifier_id": self.classifier_id,
                "classifier_version": self.classifier_version,
                "classifier_source_digest": self.classifier_source_digest,
            },
            "seed": {"seed_id": self.seed_id, "seed_digest": self.seed_digest},
        }

    @property
    def digest(self) -> str:
        return manifest_digest(self.to_dict())


_Executor = Callable[[Mapping[str, object]], object]


@dataclass(frozen=True, slots=True)
class _SideOutcome:
    observation: CanonicalMechanicsObservation | None
    execution_status: Literal["completed", "skipped", "failed"]
    failure_class: str | None
    failure_origin: str | None


class DifferentialRunner:
    """Execute exactly one fixture through injected oracle and engine functions."""

    runner_id = "battlebelief-differential-runner"
    runner_version = "1"

    def __init__(
        self,
        *,
        oracle_executor: _Executor,
        engine_executor: _Executor,
        provenance: FixtureResultProvenance,
        classifier: DifferentialClassifier,
    ) -> None:
        if not callable(oracle_executor) or not callable(engine_executor):
            raise TypeError("differential executors must be injected callables")
        if not isinstance(provenance, FixtureResultProvenance):
            raise TypeError("differential runner requires result provenance")
        if not isinstance(classifier, DifferentialClassifier):
            raise TypeError("differential runner requires the frozen classifier")
        self._oracle_executor = oracle_executor
        self._engine_executor = engine_executor
        self._provenance = provenance
        self._classifier = classifier
        self.source_digest = _source_digest()

    def run_fixture(self, fixture: DifferentialFixture, *, synthetic: bool = True) -> FixtureResult:
        """Run one canonical fixture without retaining state, output, or exception bytes."""

        if not isinstance(fixture, DifferentialFixture):
            raise TypeError("differential runner requires a DifferentialFixture")
        if type(synthetic) is not bool:
            raise TypeError("synthetic flag must be a bool")
        self._validate_fixture_binding(fixture)
        oracle_document = fixture._execution_document_for_runner()
        engine_document = fixture._execution_document_for_runner()
        seed_document = oracle_document["seed"]
        if not isinstance(seed_document, Mapping):  # pragma: no cover - corpus validates this
            raise RunnerConfigurationError("fixture seed is unavailable")
        seed_digest = manifest_digest(seed_document)
        oracle = self._execute_side(self._oracle_executor, oracle_document, "oracle")
        if oracle.execution_status != "completed":
            return self._unsuccessful_result(fixture, oracle, synthetic, seed_digest)
        engine = self._execute_side(self._engine_executor, engine_document, "engine")
        if engine.execution_status != "completed":
            return self._unsuccessful_result(fixture, engine, synthetic, seed_digest)
        assert oracle.observation is not None and engine.observation is not None
        missing_oracle = [
            field_name
            for field_name in fixture.declared_comparison_fields
            if not oracle.observation.has_field(field_name)
        ]
        if missing_oracle:
            return self._failed_result(
                fixture, "malformed_output", "oracle", synthetic, seed_digest
            )
        missing_engine = [
            field_name
            for field_name in fixture.declared_comparison_fields
            if not engine.observation.has_field(field_name)
        ]
        if missing_engine:
            return self._failed_result(
                fixture, "malformed_output", "engine", synthetic, seed_digest
            )
        differing_fields = tuple(
            field_name
            for field_name in fixture.declared_comparison_fields
            if oracle.observation.value_for(field_name) != engine.observation.value_for(field_name)
        )
        try:
            divergence_class = self._classifier.classify(fixture, differing_fields)
        except ClassifierConfigurationError as error:
            raise RunnerConfigurationError("fixture classifier binding is invalid") from error
        return FixtureResult(
            fixture_id=fixture.fixture_id,
            fixture_digest=fixture.fixture_digest,
            execution_status="completed",
            divergence_class=divergence_class,
            failure_class=None,
            failure_origin=None,
            differing_fields=differing_fields,
            known_divergence_id=fixture.known_divergence_id
            if divergence_class is DivergenceClass.KNOWN_DIVERGENCE
            else None,
            synthetic=synthetic,
            provenance=self._provenance,
            runner_id=self.runner_id,
            runner_version=self.runner_version,
            runner_source_digest=self.source_digest,
            classifier_id=self._classifier.classifier_id,
            classifier_version=self._classifier.classifier_version,
            classifier_source_digest=self._classifier.source_digest,
            seed_id=fixture.seed_id,
            seed_digest=seed_digest,
        )

    def _validate_fixture_binding(self, fixture: DifferentialFixture) -> None:
        if not set(fixture.declared_comparison_fields).issubset(_COMPARISON_FIELDS):
            raise RunnerConfigurationError(
                "fixture declares a comparison field this runner does not support"
            )
        if (fixture.corpus_id, fixture.corpus_version) != (
            self._provenance.corpus_id,
            self._provenance.corpus_version,
        ):
            raise RunnerConfigurationError("fixture corpus identity does not match provenance")
        if fixture._corpus_digest_for_runner() != self._provenance.corpus_digest:
            raise RunnerConfigurationError("fixture corpus digest does not match provenance")
        if (
            fixture.ruleset_id,
            fixture.ruleset_digest,
        ) != (
            self._provenance.ruleset_id,
            self._provenance.ruleset_digest,
        ):
            raise RunnerConfigurationError("fixture ruleset ID or digest does not match provenance")
        if (
            fixture.normalization_profile_id,
            fixture.normalization_profile_version,
            fixture.normalization_profile_digest,
        ) != (
            self._provenance.canonicalization_profile_id,
            self._provenance.canonicalization_profile_version,
            self._provenance.canonicalization_profile_digest,
        ):
            raise RunnerConfigurationError(
                "fixture normalization binding does not match provenance"
            )
        if (
            fixture.classifier_id,
            fixture.classifier_version,
            fixture.classifier_source_digest,
        ) != (
            self._classifier.classifier_id,
            self._classifier.classifier_version,
            self._classifier.source_digest,
        ):
            raise RunnerConfigurationError("fixture classifier binding does not match runner")

    @staticmethod
    def _execute_side(
        executor: _Executor,
        execution_document: Mapping[str, object],
        origin: Literal["oracle", "engine"],
    ) -> _SideOutcome:
        try:
            outcome = executor(execution_document)
        except TimeoutError:
            return _SideOutcome(None, "failed", "timeout", origin)
        except PokeEngineMappingFailure:
            return _SideOutcome(None, "failed", "mapping_failure", "runtime_adapter")
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            return _SideOutcome(None, "failed", "crash", origin)
        if isinstance(outcome, CanonicalMechanicsObservation):
            return _SideOutcome(outcome, "completed", None, None)
        if isinstance(outcome, DifferentialSideExecution):
            return _SideOutcome(outcome.observation, "completed", None, None)
        if isinstance(outcome, DifferentialExecutionSkip):
            return _SideOutcome(
                None,
                "skipped",
                outcome.failure_class,
                origin if outcome.failure_class is not None else None,
            )
        if isinstance(outcome, DifferentialExecutionFailure):
            return _SideOutcome(None, "failed", outcome.failure_class, origin)
        return _SideOutcome(None, "failed", "malformed_output", origin)

    def _unsuccessful_result(
        self,
        fixture: DifferentialFixture,
        outcome: _SideOutcome,
        synthetic: bool,
        seed_digest: str,
    ) -> FixtureResult:
        if outcome.execution_status == "skipped":
            return FixtureResult(
                fixture_id=fixture.fixture_id,
                fixture_digest=fixture.fixture_digest,
                execution_status="skipped",
                divergence_class=None,
                failure_class=outcome.failure_class,
                failure_origin=outcome.failure_origin,
                differing_fields=(),
                known_divergence_id=None,
                synthetic=synthetic,
                provenance=self._provenance,
                runner_id=self.runner_id,
                runner_version=self.runner_version,
                runner_source_digest=self.source_digest,
                classifier_id=self._classifier.classifier_id,
                classifier_version=self._classifier.classifier_version,
                classifier_source_digest=self._classifier.source_digest,
                seed_id=fixture.seed_id,
                seed_digest=seed_digest,
            )
        assert outcome.failure_class is not None and outcome.failure_origin is not None
        return self._failed_result(
            fixture,
            outcome.failure_class,
            outcome.failure_origin,
            synthetic,
            seed_digest,
        )

    def _failed_result(
        self,
        fixture: DifferentialFixture,
        failure_class: str,
        failure_origin: str,
        synthetic: bool,
        seed_digest: str,
    ) -> FixtureResult:
        return FixtureResult(
            fixture_id=fixture.fixture_id,
            fixture_digest=fixture.fixture_digest,
            execution_status="failed",
            divergence_class=None,
            failure_class=failure_class,
            failure_origin=failure_origin,
            differing_fields=(),
            known_divergence_id=None,
            synthetic=synthetic,
            provenance=self._provenance,
            runner_id=self.runner_id,
            runner_version=self.runner_version,
            runner_source_digest=self.source_digest,
            classifier_id=self._classifier.classifier_id,
            classifier_version=self._classifier.classifier_version,
            classifier_source_digest=self._classifier.source_digest,
            seed_id=fixture.seed_id,
            seed_digest=seed_digest,
        )


__all__ = [
    "CanonicalMechanicsObservation",
    "DifferentialExecutionFailure",
    "DifferentialExecutionSkip",
    "DifferentialRunner",
    "DifferentialSideExecution",
    "FixtureResult",
    "FixtureResultProvenance",
    "RunnerConfigurationError",
]
