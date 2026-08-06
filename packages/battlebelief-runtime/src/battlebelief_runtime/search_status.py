"""Sanitized public status types for the optional native search artifact."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SAFE_TOKEN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_FAILURE = re.compile(r"^[a-z][a-z0-9_]*$")
_STATUSES = frozenset(
    {
        "available",
        "extra_unavailable",
        "artifact_unavailable",
        "artifact_mismatch",
        "unsupported_environment",
        "import_failed",
        "sentinel_failed",
        "native_unhealthy",
    }
)
_FEATURES = ("poke-engine/gen9", "poke-engine/terastallization")


@dataclass(frozen=True, slots=True)
class EngineArtifactIdentity:
    """Canonical, path-free identity of one approved installed wheel cell."""

    artifact_index_digest: str
    source_manifest_digest: str
    build_manifest_digest: str
    wheel_sha256: str
    wheel_filename: str
    cell_id: str
    distribution_name: str
    distribution_version: str
    python_tag: str
    abi_tag: str
    platform_tag: str
    operating_system: str
    architecture: str
    features: tuple[str, ...]
    adapter_version: str
    release_tag: str
    release_asset_url: str
    sentinel_fixture_digest: str
    sentinel_result_digest: str
    sentinel_configuration_digest: str

    def __post_init__(self) -> None:
        for digest in (
            self.artifact_index_digest,
            self.source_manifest_digest,
            self.build_manifest_digest,
            self.wheel_sha256,
            self.sentinel_fixture_digest,
            self.sentinel_result_digest,
            self.sentinel_configuration_digest,
        ):
            if _DIGEST.fullmatch(digest) is None:
                raise ValueError("artifact identity digest is invalid")
        for token in (
            self.wheel_filename,
            self.cell_id,
            self.distribution_name,
            self.distribution_version,
            self.python_tag,
            self.abi_tag,
            self.platform_tag,
            self.operating_system,
            self.architecture,
            self.adapter_version,
            self.release_tag,
        ):
            if _SAFE_TOKEN.fullmatch(token) is None:
                raise ValueError("artifact identity token is invalid")
        if self.features != _FEATURES:
            raise ValueError("artifact feature identity is invalid")
        expected_url = (
            "https://github.com/chrismaghuhn/BattleBelief/releases/download/"
            f"{self.release_tag}/{self.wheel_filename}"
        )
        if self.release_asset_url != expected_url:
            raise ValueError("artifact release identity is invalid")

    def to_dict(self) -> dict[str, object]:
        """Return the canonical JSON-compatible representation."""

        return {
            "artifact_index_digest": self.artifact_index_digest,
            "source_manifest_digest": self.source_manifest_digest,
            "build_manifest_digest": self.build_manifest_digest,
            "wheel_sha256": self.wheel_sha256,
            "wheel_filename": self.wheel_filename,
            "cell_id": self.cell_id,
            "distribution_name": self.distribution_name,
            "distribution_version": self.distribution_version,
            "python_tag": self.python_tag,
            "abi_tag": self.abi_tag,
            "platform_tag": self.platform_tag,
            "operating_system": self.operating_system,
            "architecture": self.architecture,
            "features": list(self.features),
            "adapter_version": self.adapter_version,
            "release_tag": self.release_tag,
            "release_asset_url": self.release_asset_url,
            "sentinel_fixture_digest": self.sentinel_fixture_digest,
            "sentinel_result_digest": self.sentinel_result_digest,
            "sentinel_configuration_digest": self.sentinel_configuration_digest,
        }


@dataclass(frozen=True, slots=True)
class EngineAvailability:
    """Fail-closed public classification without raw exception details."""

    status: str
    identity: EngineArtifactIdentity | None
    failure_class: str | None

    def __post_init__(self) -> None:
        if self.status not in _STATUSES:
            raise ValueError("availability status is invalid")
        if self.status == "available":
            if self.identity is None:
                raise ValueError("available status requires identity")
            if self.failure_class is not None:
                raise ValueError("available status cannot carry a failure")
        else:
            if self.identity is not None:
                raise ValueError("unavailable status cannot carry identity")
            if self.failure_class is None or _FAILURE.fullmatch(self.failure_class) is None:
                raise ValueError("failure class is invalid")

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-compatible representation."""

        return {
            "status": self.status,
            "identity": None if self.identity is None else self.identity.to_dict(),
            "failure_class": self.failure_class,
        }


__all__ = ["EngineArtifactIdentity", "EngineAvailability"]
