"""Frozen, public differential-result classification semantics for Task 28."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Protocol


class DivergenceClass(StrEnum):
    """The complete ADR-0008 divergence taxonomy for completed results."""

    MATCH = "match"
    KNOWN_DIVERGENCE = "known_divergence"
    UNCLASSIFIED = "unclassified"


class ClassifierConfigurationError(ValueError):
    """Raised when a fixture is not bound to this frozen classifier identity."""


class _FixtureClassificationPolicy(Protocol):
    @property
    def classifier_id(self) -> str: ...

    @property
    def classifier_version(self) -> str: ...

    @property
    def classifier_source_digest(self) -> str: ...

    @property
    def known_divergence_id(self) -> str | None: ...


def _source_digest() -> str:
    return "sha256:" + sha256(Path(__file__).read_bytes()).hexdigest()


class DifferentialClassifier:
    """Classify only differences in the policy prebound by a corpus fixture."""

    classifier_id = "battlebelief-differential-classifier"
    classifier_version = "1"

    def __init__(self, *, known_divergence_ids: Sequence[str] = ()) -> None:
        if any(
            type(identifier) is not str or not identifier for identifier in known_divergence_ids
        ):
            raise ValueError("known divergence IDs must be non-empty strings")
        if tuple(known_divergence_ids) != tuple(sorted(set(known_divergence_ids))):
            raise ValueError("known divergence IDs must be unique and sorted")
        self._known_divergence_ids = frozenset(known_divergence_ids)
        self.source_digest = _source_digest()

    def classify(
        self,
        fixture: _FixtureClassificationPolicy,
        differing_fields: Sequence[str],
    ) -> DivergenceClass:
        """Return the sole ADR-0008 class permitted for a completed result."""

        if fixture.classifier_id != self.classifier_id:
            raise ClassifierConfigurationError("fixture classifier ID does not match")
        if fixture.classifier_version != self.classifier_version:
            raise ClassifierConfigurationError("fixture classifier version does not match")
        if fixture.classifier_source_digest != self.source_digest:
            raise ClassifierConfigurationError("fixture classifier source digest does not match")
        if not differing_fields:
            return DivergenceClass.MATCH
        known_divergence_id = fixture.known_divergence_id
        if known_divergence_id is None:
            return DivergenceClass.UNCLASSIFIED
        if known_divergence_id not in self._known_divergence_ids:
            raise ClassifierConfigurationError("fixture known divergence is not frozen")
        return DivergenceClass.KNOWN_DIVERGENCE


__all__ = ["ClassifierConfigurationError", "DifferentialClassifier", "DivergenceClass"]
