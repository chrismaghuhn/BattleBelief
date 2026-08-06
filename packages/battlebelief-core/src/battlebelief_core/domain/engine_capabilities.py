"""Immutable catalog and qualification values for engine-neutral search."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Self

from battlebelief_core.canonicalization import manifest_digest

_CAPABILITY_ID_RE = re.compile(
    r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*){2,7}$"
)
_CANONICAL_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_ENVIRONMENT_CELL_ID_RE = re.compile(r"^[a-z0-9]+(?:[-._][a-z0-9]+)*$")
_SCHEMA_ID_RE = re.compile(
    r"^urn:battlebelief:schema:[a-z][a-z0-9-]*(?::[a-z][a-z0-9-]*)*:v[1-9][0-9]*$"
)
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_FORMAT = "gen9ou"


def _nonempty(value: object, name: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _digest(value: object, name: str) -> str:
    if type(value) is not str or not _DIGEST_RE.fullmatch(value):
        raise ValueError(f"{name} must be a sha256 digest")
    return value


def _canonical_id(value: object, name: str) -> str:
    if type(value) is not str or not _CANONICAL_ID_RE.fullmatch(value):
        raise ValueError(f"{name} must be a canonical identifier")
    return value


def _environment_cell_id(value: object) -> str:
    if type(value) is not str or not _ENVIRONMENT_CELL_ID_RE.fullmatch(value):
        raise ValueError("environment_cell_id must be canonical")
    return value


def _schema_id(value: object, name: str) -> str:
    if type(value) is not str or not _SCHEMA_ID_RE.fullmatch(value):
        raise ValueError(f"{name} must be a canonical BattleBelief schema id")
    return value


@dataclass(frozen=True, slots=True, init=False)
class CapabilityId:
    value: str
    catalog_digest: str = field(repr=False)

    def __init__(self, *_: object, **__: object) -> None:
        raise TypeError("CapabilityId values are issued by CapabilityCatalog")

    @classmethod
    def _issue(cls, catalog: CapabilityCatalog, value: str) -> Self:
        if not isinstance(catalog, CapabilityCatalog) or value not in catalog._definition_values:
            raise ValueError("capability must be defined by its issuing catalog")
        instance = object.__new__(cls)
        object.__setattr__(instance, "value", value)
        object.__setattr__(instance, "catalog_digest", catalog.catalog_digest)
        return instance


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    value: str
    description: str = ""

    def __post_init__(self) -> None:
        if (
            type(self.value) is not str
            or len(self.value.encode("ascii", "ignore")) != len(self.value)
            or len(self.value) > 128
            or not _CAPABILITY_ID_RE.fullmatch(self.value)
            or not self.value.startswith("gen9.")
        ):
            raise ValueError("capability value must be a canonical gen9 capability id")
        _nonempty(self.description, "description")


@dataclass(frozen=True, slots=True)
class CapabilityCatalog:
    catalog_id: str
    catalog_version: str
    generation: int
    format: str
    capability_contract_digest: str = field(repr=False)
    canonicalization_contract_digest: str = field(repr=False)
    catalog_digest: str = field(repr=False)
    definitions: tuple[CapabilityDefinition, ...] = ()
    _definition_values: frozenset[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _canonical_id(self.catalog_id, "catalog_id")
        _nonempty(self.catalog_version, "catalog_version")
        if type(self.generation) is not int or self.generation != 9 or self.format != _FORMAT:
            raise ValueError("catalog must be for Gen 9 OU")
        _digest(self.capability_contract_digest, "capability_contract_digest")
        _digest(self.canonicalization_contract_digest, "canonicalization_contract_digest")
        if (
            type(self.definitions) is not tuple
            or not self.definitions
            or any(not isinstance(item, CapabilityDefinition) for item in self.definitions)
        ):
            raise ValueError("definitions must be a non-empty tuple of CapabilityDefinition values")
        values = tuple(item.value for item in self.definitions)
        if values != tuple(sorted(values)) or len(set(values)) != len(values):
            raise ValueError("definitions must be uniquely sorted by value")
        expected = self._derive_digest(
            self.catalog_id,
            self.catalog_version,
            self.generation,
            self.format,
            self.capability_contract_digest,
            self.canonicalization_contract_digest,
            self.definitions,
        )
        if self.catalog_digest != expected:
            raise ValueError("catalog_digest must bind the canonical catalog document")
        object.__setattr__(self, "_definition_values", frozenset(values))

    @staticmethod
    def _derive_digest(
        catalog_id: str,
        catalog_version: str,
        generation: int,
        format: str,
        capability_contract_digest: str,
        canonicalization_contract_digest: str,
        definitions: tuple[CapabilityDefinition, ...],
    ) -> str:
        return manifest_digest(
            {
                "schema_version": 1,
                "catalog_id": catalog_id,
                "catalog_version": catalog_version,
                "generation": generation,
                "format": format,
                "capability_contract_digest": capability_contract_digest,
                "canonicalization_contract_digest": canonicalization_contract_digest,
                "definitions": [
                    {"value": definition.value, "description": definition.description}
                    for definition in definitions
                ],
            }
        )

    @classmethod
    def create(
        cls,
        *,
        catalog_id: str,
        catalog_version: str,
        capability_contract_digest: str,
        canonicalization_contract_digest: str,
        definitions: tuple[CapabilityDefinition, ...],
    ) -> Self:
        return cls(
            catalog_id=catalog_id,
            catalog_version=catalog_version,
            generation=9,
            format=_FORMAT,
            capability_contract_digest=capability_contract_digest,
            canonicalization_contract_digest=canonicalization_contract_digest,
            catalog_digest=cls._derive_digest(
                catalog_id,
                catalog_version,
                9,
                _FORMAT,
                capability_contract_digest,
                canonicalization_contract_digest,
                definitions,
            ),
            definitions=definitions,
        )

    def document(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "catalog_id": self.catalog_id,
            "catalog_version": self.catalog_version,
            "generation": self.generation,
            "format": self.format,
            "capability_contract_digest": self.capability_contract_digest,
            "canonicalization_contract_digest": self.canonicalization_contract_digest,
            "definitions": [
                {"value": definition.value, "description": definition.description}
                for definition in self.definitions
            ],
        }

    @classmethod
    def from_document(cls, document: Mapping[str, object]) -> Self:
        if not isinstance(document, Mapping) or set(document) != {
            "schema_version",
            "catalog_id",
            "catalog_version",
            "generation",
            "format",
            "capability_contract_digest",
            "canonicalization_contract_digest",
            "definitions",
        }:
            raise ValueError("catalog document has an invalid shape")
        definitions_value = document["definitions"]
        if not isinstance(definitions_value, list):
            raise ValueError("catalog document definitions must be a list")
        definitions: list[CapabilityDefinition] = []
        for item in definitions_value:
            if not isinstance(item, Mapping) or set(item) != {"value", "description"}:
                raise ValueError("catalog definition document is invalid")
            definitions.append(
                CapabilityDefinition(value=item["value"], description=item["description"])
            )
        if (
            type(document["schema_version"]) is not int
            or document["schema_version"] != 1
            or document["generation"] != 9
            or document["format"] != _FORMAT
        ):
            raise ValueError("catalog document is not Gen 9 OU schema version 1")
        catalog_id = document["catalog_id"]
        catalog_version = document["catalog_version"]
        capability_contract_digest = document["capability_contract_digest"]
        canonicalization_contract_digest = document["canonicalization_contract_digest"]
        if not (
            type(catalog_id) is str
            and type(catalog_version) is str
            and type(capability_contract_digest) is str
            and type(canonicalization_contract_digest) is str
        ):
            raise ValueError("catalog document fields must be strings")
        return cls.create(
            catalog_id=catalog_id,
            catalog_version=catalog_version,
            capability_contract_digest=capability_contract_digest,
            canonicalization_contract_digest=canonicalization_contract_digest,
            definitions=tuple(definitions),
        )

    def id_for(self, value: str) -> CapabilityId:
        if type(value) is not str or value not in self._definition_values:
            raise ValueError("capability is not defined by this catalog")
        return CapabilityId._issue(self, value)

    def require(self, capability: CapabilityId) -> CapabilityId:
        if (
            not isinstance(capability, CapabilityId)
            or capability.catalog_digest != self.catalog_digest
            or capability.value not in self._definition_values
        ):
            raise ValueError("capability does not belong to this catalog")
        return capability


class CapabilityStatus(StrEnum):
    EXACT = "exact"
    BOUNDED_APPROXIMATION = "bounded_approximation"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CapabilityApproximation:
    bound: str
    condition: str

    def __post_init__(self) -> None:
        _nonempty(self.bound, "bound")
        _nonempty(self.condition, "condition")


@dataclass(frozen=True, slots=True)
class EngineEnvironmentBinding:
    """Named environment matrix cell; adapter provenance is manifest-global."""

    environment_cell_id: str
    engine_build_manifest_digest: str = field(repr=False)
    wheel_digest: str = field(repr=False)

    def __post_init__(self) -> None:
        _environment_cell_id(self.environment_cell_id)
        _digest(self.engine_build_manifest_digest, "engine_build_manifest_digest")
        _digest(self.wheel_digest, "wheel_digest")


@dataclass(frozen=True, slots=True)
class CapabilityEvidenceRef:
    environment_cell_id: str = field(repr=False)
    engine_source_manifest_digest: str = field(repr=False)
    engine_build_manifest_digest: str = field(repr=False)
    artifact_index_digest: str = field(repr=False)
    wheel_digest: str = field(repr=False)
    transition_adapter_id: str = field(repr=False)
    transition_adapter_version: str = field(repr=False)
    transition_adapter_source_digest: str = field(repr=False)
    transition_model_contract_digest: str = field(repr=False)
    transition_adapter_conformance_digest: str = field(repr=False)
    oracle_source_manifest_digest: str = field(repr=False)
    oracle_build_manifest_digest: str = field(repr=False)
    ruleset_digest: str = field(repr=False)
    corpus_digest: str = field(repr=False)
    qualification_result_schema_id: str = field(repr=False)
    qualification_result_digest: str = field(repr=False)

    def __post_init__(self) -> None:
        _environment_cell_id(self.environment_cell_id)
        _canonical_id(self.transition_adapter_id, "transition_adapter_id")
        _nonempty(self.transition_adapter_version, "transition_adapter_version")
        _schema_id(self.qualification_result_schema_id, "qualification_result_schema_id")
        for name in _EVIDENCE_DIGEST_FIELDS:
            _digest(getattr(self, name), name)

    def document(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in _EVIDENCE_FIELDS}


_EVIDENCE_DIGEST_FIELDS = (
    "engine_source_manifest_digest",
    "engine_build_manifest_digest",
    "artifact_index_digest",
    "wheel_digest",
    "transition_adapter_source_digest",
    "transition_model_contract_digest",
    "transition_adapter_conformance_digest",
    "oracle_source_manifest_digest",
    "oracle_build_manifest_digest",
    "ruleset_digest",
    "corpus_digest",
    "qualification_result_digest",
)
_EVIDENCE_FIELDS = (
    "environment_cell_id",
    "engine_source_manifest_digest",
    "engine_build_manifest_digest",
    "artifact_index_digest",
    "wheel_digest",
    "transition_adapter_id",
    "transition_adapter_version",
    "transition_adapter_source_digest",
    "transition_model_contract_digest",
    "transition_adapter_conformance_digest",
    "oracle_source_manifest_digest",
    "oracle_build_manifest_digest",
    "ruleset_digest",
    "corpus_digest",
    "qualification_result_schema_id",
    "qualification_result_digest",
)


@dataclass(frozen=True, slots=True)
class CapabilityClaim:
    capability_id: CapabilityId
    status: CapabilityStatus
    evidence_refs: tuple[CapabilityEvidenceRef, ...] = field(default=(), repr=False)
    approximation: CapabilityApproximation | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, CapabilityId) or not isinstance(
            self.status, CapabilityStatus
        ):
            raise ValueError("claim must use a catalog capability and recognized status")
        if type(self.evidence_refs) is not tuple or any(
            not isinstance(ref, CapabilityEvidenceRef) for ref in self.evidence_refs
        ):
            raise ValueError("evidence_refs must be a tuple of CapabilityEvidenceRef values")
        cells = tuple(ref.environment_cell_id for ref in self.evidence_refs)
        if cells != tuple(sorted(cells)) or len(set(cells)) != len(cells):
            raise ValueError("evidence_refs must be uniquely sorted by environment cell id")
        qualifying = self.status in {CapabilityStatus.EXACT, CapabilityStatus.BOUNDED_APPROXIMATION}
        if qualifying != bool(self.evidence_refs):
            raise ValueError("qualifying claims require evidence; nonqualifying claims forbid it")
        if (self.status is CapabilityStatus.BOUNDED_APPROXIMATION) != (
            self.approximation is not None
        ):
            raise ValueError("only bounded claims carry an explicit approximation")


@dataclass(frozen=True, slots=True)
class EngineCapabilityManifest:
    manifest_id: str
    catalog: CapabilityCatalog
    generation: int
    format: str
    engine_source_manifest_digest: str = field(repr=False)
    artifact_index_digest: str = field(repr=False)
    environment_bindings: tuple[EngineEnvironmentBinding, ...] = ()
    transition_adapter_id: str | None = field(default=None, repr=False)
    transition_adapter_version: str | None = field(default=None, repr=False)
    transition_adapter_source_digest: str | None = field(default=None, repr=False)
    transition_model_contract_digest: str | None = field(default=None, repr=False)
    transition_adapter_conformance_digest: str | None = field(default=None, repr=False)
    oracle_source_manifest_digest: str | None = field(default=None, repr=False)
    oracle_build_manifest_digest: str | None = field(default=None, repr=False)
    ruleset_digest: str | None = field(default=None, repr=False)
    corpus_digest: str | None = field(default=None, repr=False)
    evidence_set_digest: str | None = field(default=None, repr=False)
    canonicalization_contract_digest: str = field(default="", repr=False)
    claims: tuple[CapabilityClaim, ...] = ()

    def __post_init__(self) -> None:
        _canonical_id(self.manifest_id, "manifest_id")
        if (
            not isinstance(self.catalog, CapabilityCatalog)
            or type(self.generation) is not int
            or self.generation != 9
        ):
            raise ValueError("manifest must bind the Gen 9 catalog")
        if self.format != _FORMAT:
            raise ValueError("manifest format must be gen9ou")
        if (
            self.catalog.generation != self.generation
            or self.catalog.format != self.format
            or self.catalog.canonicalization_contract_digest
            != self.canonicalization_contract_digest
        ):
            raise ValueError(
                "manifest must match its catalog generation, format, and canonicalization"
            )
        for name in (
            "engine_source_manifest_digest",
            "artifact_index_digest",
            "canonicalization_contract_digest",
        ):
            _digest(getattr(self, name), name)
        if type(self.environment_bindings) is not tuple or any(
            not isinstance(item, EngineEnvironmentBinding) for item in self.environment_bindings
        ):
            raise ValueError("environment_bindings must be a tuple of environment cells")
        cells = tuple(item.environment_cell_id for item in self.environment_bindings)
        if cells != tuple(sorted(cells)) or len(set(cells)) != len(cells):
            raise ValueError("environment_bindings must be uniquely sorted by environment cell id")
        adapter_values = tuple(getattr(self, name) for name in _ADAPTER_FIELDS)
        if any(value is None for value in adapter_values) and any(
            value is not None for value in adapter_values
        ):
            raise ValueError("adapter provenance must be all-null or all-present")
        if all(value is not None for value in adapter_values):
            _canonical_id(self.transition_adapter_id, "transition_adapter_id")
            _nonempty(self.transition_adapter_version, "transition_adapter_version")
            for name in _ADAPTER_DIGEST_FIELDS:
                _digest(getattr(self, name), name)
        for name in _OPTIONAL_CLOSURE_DIGEST_FIELDS:
            value = getattr(self, name)
            if value is not None:
                _digest(value, name)
        if type(self.claims) is not tuple or any(
            not isinstance(item, CapabilityClaim) for item in self.claims
        ):
            raise ValueError("claims must be a tuple of CapabilityClaim values")
        values = tuple(claim.capability_id.value for claim in self.claims)
        if values != tuple(sorted(values)) or len(set(values)) != len(values):
            raise ValueError("claims must be uniquely sorted by capability value")
        for claim in self.claims:
            self.catalog.require(claim.capability_id)
        qualifying_claims = tuple(
            claim
            for claim in self.claims
            if claim.status in {CapabilityStatus.EXACT, CapabilityStatus.BOUNDED_APPROXIMATION}
        )
        refs = tuple(dict.fromkeys(ref for claim in self.claims for ref in claim.evidence_refs))
        expected_evidence_set = self.evidence_set_digest_for(refs)
        if qualifying_claims:
            if (
                not self.environment_bindings
                or any(value is None for value in adapter_values)
                or any(getattr(self, name) is None for name in _OPTIONAL_CLOSURE_DIGEST_FIELDS)
            ):
                raise ValueError("qualifying claims require complete provenance closure")
            if self.evidence_set_digest != expected_evidence_set:
                raise ValueError("evidence_set_digest must bind all evidence references")
            for claim in qualifying_claims:
                if tuple(ref.environment_cell_id for ref in claim.evidence_refs) != cells:
                    raise ValueError("qualifying claim evidence must cover every environment cell")
                for ref in claim.evidence_refs:
                    self._require_matching_evidence(ref)
        elif (
            self.evidence_set_digest is not None
            and self.evidence_set_digest != expected_evidence_set
        ):
            raise ValueError("evidence_set_digest must bind all evidence references")

    @classmethod
    def create_unqualified(
        cls,
        *,
        manifest_id: str,
        catalog: CapabilityCatalog,
        generation: int,
        format: str,
        engine_source_manifest_digest: str,
        artifact_index_digest: str,
        environment_bindings: tuple[EngineEnvironmentBinding, ...],
        canonicalization_contract_digest: str,
    ) -> Self:
        return cls(
            manifest_id=manifest_id,
            catalog=catalog,
            generation=generation,
            format=format,
            engine_source_manifest_digest=engine_source_manifest_digest,
            artifact_index_digest=artifact_index_digest,
            environment_bindings=environment_bindings,
            canonicalization_contract_digest=canonicalization_contract_digest,
        )

    @staticmethod
    def evidence_set_digest_for(evidence_refs: tuple[CapabilityEvidenceRef, ...]) -> str:
        if type(evidence_refs) is not tuple or any(
            not isinstance(ref, CapabilityEvidenceRef) for ref in evidence_refs
        ):
            raise ValueError("evidence_refs must be a tuple of CapabilityEvidenceRef values")
        keyed_refs = tuple(
            (tuple(ref.document()[name] for name in _EVIDENCE_FIELDS), ref) for ref in evidence_refs
        )
        keys = tuple(key for key, _ in keyed_refs)
        if len(set(keys)) != len(keys):
            raise ValueError("evidence_refs must not contain duplicate references")
        return manifest_digest(
            {
                "evidence_refs": [
                    ref.document() for _, ref in sorted(keyed_refs, key=lambda item: item[0])
                ]
            }
        )

    def _require_matching_evidence(self, ref: CapabilityEvidenceRef) -> None:
        cell = next(
            (
                item
                for item in self.environment_bindings
                if item.environment_cell_id == ref.environment_cell_id
            ),
            None,
        )
        if (
            cell is None
            or ref.engine_build_manifest_digest != cell.engine_build_manifest_digest
            or ref.wheel_digest != cell.wheel_digest
        ):
            raise ValueError("evidence does not match its environment cell")
        for name in _GLOBAL_EVIDENCE_FIELDS:
            if getattr(ref, name) != getattr(self, name):
                raise ValueError("evidence does not match manifest provenance")

    def claim_for(self, capability: CapabilityId) -> CapabilityClaim | None:
        self.catalog.require(capability)
        return next((claim for claim in self.claims if claim.capability_id == capability), None)

    def status_for(self, capability: CapabilityId) -> CapabilityStatus:
        claim = self.claim_for(capability)
        return CapabilityStatus.UNKNOWN if claim is None else claim.status

    def backend_identity_digest(self, environment_cell_id: str) -> str:
        if any(getattr(self, name) is None for name in _ADAPTER_FIELDS):
            raise ValueError("backend identity is unavailable for an unqualified adapter")
        cell = next(
            (
                item
                for item in self.environment_bindings
                if item.environment_cell_id == environment_cell_id
            ),
            None,
        )
        if cell is None:
            raise ValueError("environment cell is not bound by this manifest")
        return manifest_digest(
            {
                "engine_source_manifest_digest": self.engine_source_manifest_digest,
                "artifact_index_digest": self.artifact_index_digest,
                "environment_cell_id": cell.environment_cell_id,
                "engine_build_manifest_digest": cell.engine_build_manifest_digest,
                "wheel_digest": cell.wheel_digest,
                "transition_adapter_id": self.transition_adapter_id,
                "transition_adapter_version": self.transition_adapter_version,
                "transition_adapter_source_digest": self.transition_adapter_source_digest,
                "transition_model_contract_digest": self.transition_model_contract_digest,
                "transition_adapter_conformance_digest": self.transition_adapter_conformance_digest,
            }
        )


_ADAPTER_FIELDS = (
    "transition_adapter_id",
    "transition_adapter_version",
    "transition_adapter_source_digest",
    "transition_model_contract_digest",
    "transition_adapter_conformance_digest",
)
_ADAPTER_DIGEST_FIELDS = _ADAPTER_FIELDS[2:]
_OPTIONAL_CLOSURE_DIGEST_FIELDS = (
    "oracle_source_manifest_digest",
    "oracle_build_manifest_digest",
    "ruleset_digest",
    "corpus_digest",
    "evidence_set_digest",
)
_GLOBAL_EVIDENCE_FIELDS = (
    "engine_source_manifest_digest",
    "artifact_index_digest",
    "transition_adapter_id",
    "transition_adapter_version",
    "transition_adapter_source_digest",
    "transition_model_contract_digest",
    "transition_adapter_conformance_digest",
    "oracle_source_manifest_digest",
    "oracle_build_manifest_digest",
    "ruleset_digest",
    "corpus_digest",
)


__all__ = [
    "CapabilityApproximation",
    "CapabilityCatalog",
    "CapabilityClaim",
    "CapabilityDefinition",
    "CapabilityEvidenceRef",
    "CapabilityId",
    "CapabilityStatus",
    "EngineCapabilityManifest",
    "EngineEnvironmentBinding",
]
