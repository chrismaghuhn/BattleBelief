from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from battlebelief_runtime.adapters.poke_engine.artifact import RuntimeEnvironment
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


def test_unsupported_environment_stops_before_distribution_probe_or_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unsupported = RuntimeEnvironment(
        operating_system="unsupported",
        architecture="x86_64",
        python_tag="cp314",
        abi_tag="cp314",
        platform_tag="linux_x86_64",
    )
    monkeypatch.delitem(sys.modules, "poke_engine", raising=False)

    with (
        patch(
            "battlebelief_runtime.adapters.poke_engine.artifact.current_environment",
            return_value=unsupported,
        ),
        patch(
            "battlebelief_runtime.adapters.poke_engine.artifact.importlib.metadata.distribution",
            side_effect=AssertionError("distribution lookup must not run"),
        ) as distribution,
        patch(
            "battlebelief_runtime.adapters.poke_engine.native_probe.run_native_probe",
            side_effect=AssertionError("native probe must not run"),
        ) as native_probe,
        patch(
            "subprocess.run", side_effect=AssertionError("build fallback must not run")
        ) as process,
    ):
        availability = run_gen9_sentinel()

    assert availability.to_dict() == {
        "status": "unsupported_environment",
        "identity": None,
        "failure_class": "unsupported_environment",
    }
    distribution.assert_not_called()
    native_probe.assert_not_called()
    process.assert_not_called()
    assert "poke_engine" not in sys.modules
