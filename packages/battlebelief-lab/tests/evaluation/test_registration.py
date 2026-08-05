from __future__ import annotations

from battlebelief_lab.evaluation.registration import (
    artifact_digest,
    validate_registered_artifacts,
)


def test_registration_facade_uses_shared_validator() -> None:
    assert validate_registered_artifacts() == []
    assert artifact_digest({"artifact": "stable"}).startswith("sha256:")
