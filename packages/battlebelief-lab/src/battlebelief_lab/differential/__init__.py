"""Versioned, synthetic-only differential corpus APIs."""

from battlebelief_lab.differential.classifier import DivergenceClass
from battlebelief_lab.differential.corpus import (
    CorpusValidationError,
    DifferentialCorpus,
    DifferentialFixture,
)
from battlebelief_lab.differential.evidence import CapabilityQualificationEvidence
from battlebelief_lab.differential.runner import (
    CanonicalMechanicsObservation,
    DifferentialRunner,
    FixtureResult,
)

__all__ = [
    "CanonicalMechanicsObservation",
    "CapabilityQualificationEvidence",
    "CorpusValidationError",
    "DifferentialCorpus",
    "DifferentialFixture",
    "DifferentialRunner",
    "DivergenceClass",
    "FixtureResult",
]
