"""Hatch build hook for bundling Task-28 schemas in editable lab installs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hatchling.builders.config import BuilderConfigBound
from hatchling.builders.hooks.plugin.interface import BuildHookInterface

_SCHEMA_FILENAMES = (
    "differential-corpus.schema.json",
    "differential-fixture.schema.json",
    "differential-result.schema.json",
    "capability-qualification.schema.json",
)
_SCHEMA_TARGET_DIRECTORY = "battlebelief_lab/differential/schemas"


class CustomBuildHook(BuildHookInterface[BuilderConfigBound]):
    """Map repository schemas into the editable wheel without changing sdist paths."""

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if version != "editable":
            return

        schema_directory = Path(self.root).parents[1] / "schemas" / "evaluation"
        build_data["force_include_editable"] = {
            str(schema_directory / filename): f"{_SCHEMA_TARGET_DIRECTORY}/{filename}"
            for filename in _SCHEMA_FILENAMES
        }
