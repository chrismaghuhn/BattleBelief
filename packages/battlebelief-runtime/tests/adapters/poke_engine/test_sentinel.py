from __future__ import annotations

from unittest.mock import patch

from battlebelief_runtime.adapters.poke_engine.errors import (
    EngineArtifactError,
    EngineFailureClass,
)
from battlebelief_runtime.adapters.poke_engine.sentinel import run_gen9_sentinel


def test_public_sentinel_maps_artifact_failure_to_sanitized_availability() -> None:
    with patch(
        "battlebelief_runtime.adapters.poke_engine.artifact.verify_installed_artifact",
        side_effect=EngineArtifactError(EngineFailureClass.EXTRA_UNAVAILABLE),
    ):
        availability = run_gen9_sentinel()

    assert availability.to_dict() == {
        "status": "extra_unavailable",
        "identity": None,
        "failure_class": "extra_unavailable",
    }
