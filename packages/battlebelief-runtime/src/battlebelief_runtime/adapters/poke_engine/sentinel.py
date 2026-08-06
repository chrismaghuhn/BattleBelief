"""Public entry point for the verified native Gen-9 health sentinel."""

from __future__ import annotations

from battlebelief_runtime.search_status import EngineAvailability

from .errors import EngineArtifactError


def run_gen9_sentinel() -> EngineAvailability:
    """Verify the installed artifact and run the bounded native health probe."""

    from .artifact import verify_installed_artifact
    from .native_probe import run_native_probe

    try:
        return run_native_probe(verify_installed_artifact())
    except EngineArtifactError as error:
        return EngineAvailability(
            status=error.failure_class.value,
            identity=None,
            failure_class=error.failure_class.value,
        )


__all__ = ["run_gen9_sentinel"]
