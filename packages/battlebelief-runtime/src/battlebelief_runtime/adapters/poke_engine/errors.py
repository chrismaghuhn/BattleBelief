"""Private stable failures for the poke-engine artifact boundary."""

from __future__ import annotations

from enum import StrEnum


class EngineFailureClass(StrEnum):
    EXTRA_UNAVAILABLE = "extra_unavailable"
    ARTIFACT_UNAVAILABLE = "artifact_unavailable"
    ARTIFACT_MISMATCH = "artifact_mismatch"
    UNSUPPORTED_ENVIRONMENT = "unsupported_environment"
    IMPORT_FAILED = "import_failed"
    SENTINEL_FAILED = "sentinel_failed"
    NATIVE_UNHEALTHY = "native_unhealthy"


class EngineArtifactError(RuntimeError):
    """Private exception carrying only an approved failure class."""

    def __init__(self, failure_class: EngineFailureClass) -> None:
        self.failure_class = failure_class
        super().__init__(failure_class.value)


__all__: list[str] = []
