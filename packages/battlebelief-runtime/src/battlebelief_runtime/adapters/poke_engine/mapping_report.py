"""Sanitized public mapping results for the poke-engine transition adapter."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Self

from battlebelief_core.domain.engine_capabilities import CapabilityId

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_TOKEN = re.compile(r"^[a-z0-9][a-z0-9]*(?:[._-][a-z0-9]+)*$")


class _MappingFailureClass(StrEnum):
    MISSING_FIELD = "missing_field"
    UNSUPPORTED_MAPPING = "unsupported_mapping"
    UNKNOWN_NATIVE_CHOICE = "unknown_native_choice"
    CAPABILITY_AMBIGUITY = "capability_ambiguity"
    REQUEST_IDENTITY_MISMATCH = "request_identity_mismatch"
    SAFE_SUBMISSION_MISMATCH = "safe_submission_mismatch"
    ARTIFACT_IDENTITY_MISMATCH = "artifact_identity_mismatch"
    ADAPTER_IDENTITY_MISMATCH = "adapter_identity_mismatch"
    BACKEND_UNAVAILABLE = "backend_unavailable"
    NATIVE_EXCEPTION = "native_exception"
    MALFORMED_NATIVE_RESULT = "malformed_native_result"
    INCONSISTENT_PLAYER_VIEW = "inconsistent_player_view"
    INVALID_JOINT_ACTION = "invalid_joint_action"
    CHANCE_NORMALIZATION_FAILURE = "chance_normalization_failure"
    WORK_ACCOUNTING_INCONSISTENCY = "work_accounting_inconsistency"


@dataclass(frozen=True, slots=True)
class RequiredCapabilities:
    """Catalog-bound requirements without support or qualification claims."""

    values: tuple[CapabilityId, ...]
    catalog_digest: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if type(self.values) is not tuple or any(
            not isinstance(value, CapabilityId) for value in self.values
        ):
            raise ValueError("required capabilities must be CapabilityId values")
        identifiers = tuple(value.value for value in self.values)
        if identifiers != tuple(sorted(set(identifiers))):
            raise ValueError("required capabilities must be uniquely sorted")
        catalogs = {value.catalog_digest for value in self.values}
        if len(catalogs) > 1:
            raise ValueError("required capabilities must use one catalog")
        object.__setattr__(self, "catalog_digest", next(iter(catalogs), ""))

    @classmethod
    def canonical(cls, values: tuple[CapabilityId, ...]) -> Self:
        by_value = {value.value: value for value in values}
        return cls(tuple(by_value[value] for value in sorted(by_value)))

    def to_dict(self) -> dict[str, object]:
        return {
            "catalog_digest": self.catalog_digest,
            "capability_ids": [value.value for value in self.values],
        }


@dataclass(frozen=True, slots=True)
class MappingReport:
    """Path-free, hidden-information-free account of one mapping boundary."""

    classification: str
    adapter_id: str
    adapter_version: str
    backend_identity_digest: str = field(repr=False)
    observed_state_digest: str | None = field(default=None, repr=False)
    request_identity_digest: str | None = field(default=None, repr=False)
    safe_submission_set_digest: str | None = field(default=None, repr=False)
    capability_ids: tuple[str, ...] = ()
    work_units: int = 0
    failure_class: str | None = None

    def __post_init__(self) -> None:
        if self.classification not in {"mapped", "transitioned", "failed"}:
            raise ValueError("mapping report classification is invalid")
        for value in (self.classification, self.adapter_id, self.adapter_version):
            if type(value) is not str or _TOKEN.fullmatch(value) is None:
                raise ValueError("mapping report identity must be canonical")
        for digest_value in (
            self.backend_identity_digest,
            self.observed_state_digest,
            self.request_identity_digest,
            self.safe_submission_set_digest,
        ):
            if digest_value is not None and (
                type(digest_value) is not str or _DIGEST.fullmatch(digest_value) is None
            ):
                raise ValueError("mapping report digest is invalid")
        if self.capability_ids != tuple(sorted(set(self.capability_ids))):
            raise ValueError("mapping report capability ids must be uniquely sorted")
        if type(self.work_units) is not int or self.work_units < 0:
            raise ValueError("mapping report work must be non-negative")
        if self.failure_class is not None and self.failure_class not in {
            item.value for item in _MappingFailureClass
        }:
            raise ValueError("mapping report failure class is invalid")

    def to_dict(self) -> dict[str, object]:
        return {
            "classification": self.classification,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "backend_identity_digest": self.backend_identity_digest,
            "observed_state_digest": self.observed_state_digest,
            "request_identity_digest": self.request_identity_digest,
            "safe_submission_set_digest": self.safe_submission_set_digest,
            "capability_ids": list(self.capability_ids),
            "work_units": self.work_units,
            "failure_class": self.failure_class,
        }


class PokeEngineMappingFailure(RuntimeError):
    """Stable fail-closed adapter error that never retains a native exception."""

    def __init__(self, failure_class: str, *, report: MappingReport, work_units: int) -> None:
        if failure_class not in {item.value for item in _MappingFailureClass}:
            raise ValueError("unknown poke-engine mapping failure class")
        if report.failure_class != failure_class or report.work_units != work_units:
            raise ValueError("failure and mapping report accounting must agree")
        self.failure_class = failure_class
        self.report = report
        self.work_units = work_units
        super().__init__(f"poke_engine mapping failed: {failure_class}")


__all__ = ["MappingReport", "PokeEngineMappingFailure", "RequiredCapabilities"]
