"""Lab facade over the Task-17 shared registration validator."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from battlebelief_core.canonicalization import manifest_digest
from battlebelief_lab.registration_validation import validate_repository_artifacts


def validate_registered_artifacts(root: Path | None = None) -> list[str]:
    """Use the one repository validator; do not duplicate its semantics here."""

    return validate_repository_artifacts(root)


def artifact_digest(value: Mapping[str, Any]) -> str:
    return manifest_digest(dict(value))


__all__ = ["artifact_digest", "validate_registered_artifacts"]
