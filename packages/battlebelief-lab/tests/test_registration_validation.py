from __future__ import annotations

from battlebelief_lab.registration_validation import validate_repository_artifacts


def test_repository_artifact_validation_is_a_noop_before_task_21() -> None:
    assert validate_repository_artifacts() == []
