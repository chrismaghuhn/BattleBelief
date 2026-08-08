"""Synthetic-only tests for the frozen differential classifier."""

from __future__ import annotations

import pytest

import battlebelief_lab.differential as differential
from battlebelief_lab.differential.classifier import (
    ClassifierConfigurationError,
    DifferentialClassifier,
    DivergenceClass,
)


class _FixturePolicy:
    def __init__(self, classifier: DifferentialClassifier, known_divergence_id: str | None) -> None:
        self.classifier_id = classifier.classifier_id
        self.classifier_version = classifier.classifier_version
        self.classifier_source_digest = classifier.source_digest
        self.known_divergence_id = known_divergence_id


def test_public_api_exports_the_frozen_divergence_class() -> None:
    assert hasattr(differential, "DivergenceClass")


def test_classifier_marks_an_empty_declared_difference_as_match() -> None:
    classifier = DifferentialClassifier()

    assert classifier.classify(_FixturePolicy(classifier, None), ()) is DivergenceClass.MATCH


def test_classifier_marks_a_prebound_known_difference_as_known_divergence() -> None:
    classifier = DifferentialClassifier(known_divergence_ids=("tera-damage-boundary",))

    assert (
        classifier.classify(_FixturePolicy(classifier, "tera-damage-boundary"), ("hp",))
        is DivergenceClass.KNOWN_DIVERGENCE
    )


def test_classifier_marks_a_new_difference_as_unclassified() -> None:
    classifier = DifferentialClassifier()

    assert (
        classifier.classify(_FixturePolicy(classifier, None), ("terminal_value",))
        is DivergenceClass.UNCLASSIFIED
    )


def test_classifier_rejects_a_fixture_bound_to_a_different_classifier_version() -> None:
    classifier = DifferentialClassifier()
    fixture = _FixturePolicy(classifier, None)
    fixture.classifier_version = "2"

    with pytest.raises(ClassifierConfigurationError, match="classifier version"):
        classifier.classify(fixture, ())


def test_classifier_cannot_reclassify_an_unbound_known_divergence_in_place() -> None:
    classifier = DifferentialClassifier()

    with pytest.raises(ClassifierConfigurationError, match="known divergence"):
        classifier.classify(_FixturePolicy(classifier, "new-after-run"), ("hp",))


def test_classifier_rejects_an_unbound_known_divergence_even_when_sides_match() -> None:
    classifier = DifferentialClassifier()

    with pytest.raises(ClassifierConfigurationError, match="known divergence"):
        classifier.classify(_FixturePolicy(classifier, "new-after-run"), ())
