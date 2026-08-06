from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from battlebelief_runtime.search_status import EngineArtifactIdentity, EngineAvailability


def _identity() -> EngineArtifactIdentity:
    digest = "sha256:" + "a" * 64
    return EngineArtifactIdentity(
        artifact_index_digest=digest,
        source_manifest_digest=digest,
        build_manifest_digest=digest,
        wheel_sha256=digest,
        wheel_filename="poke_engine-0.0.48-cp314-none-win_amd64.whl",
        cell_id="windows-2025-x86_64-cp314",
        distribution_name="poke-engine",
        distribution_version="0.0.48",
        python_tag="cp314",
        abi_tag="none",
        platform_tag="win_amd64",
        operating_system="windows-2025",
        architecture="x86_64",
        features=("poke-engine/gen9", "poke-engine/terastallization"),
        adapter_version="battlebelief-poke-engine-v1",
        release_tag="engine-poke-engine-v0.0.48-bcf13823-v1",
        release_asset_url=(
            "https://github.com/chrismaghuhn/BattleBelief/releases/download/"
            "engine-poke-engine-v0.0.48-bcf13823-v1/"
            "poke_engine-0.0.48-cp314-none-win_amd64.whl"
        ),
        sentinel_fixture_digest=digest,
        sentinel_result_digest=digest,
        sentinel_configuration_digest=digest,
    )


def test_engine_identity_and_availability_are_frozen_and_canonical() -> None:
    identity = _identity()
    availability = EngineAvailability(status="available", identity=identity, failure_class=None)

    assert availability.to_dict()["identity"]["features"] == [
        "poke-engine/gen9",
        "poke-engine/terastallization",
    ]
    with pytest.raises(FrozenInstanceError):
        identity.cell_id = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        availability.status = "changed"  # type: ignore[misc]


def test_unavailable_status_cannot_carry_identity_or_unsafe_failure_text() -> None:
    with pytest.raises(ValueError, match="unavailable status cannot carry identity"):
        EngineAvailability(
            status="artifact_mismatch", identity=_identity(), failure_class="wheel_digest_mismatch"
        )
    with pytest.raises(ValueError, match="failure class is invalid"):
        EngineAvailability(
            status="artifact_mismatch",
            identity=None,
            failure_class="C:\\Users\\alice\\wheel mismatch",
        )


def test_available_status_requires_identity_without_failure() -> None:
    with pytest.raises(ValueError, match="available status requires identity"):
        EngineAvailability(status="available", identity=None, failure_class=None)
    with pytest.raises(ValueError, match="available status cannot carry a failure"):
        EngineAvailability(
            status="available", identity=_identity(), failure_class="sentinel_failed"
        )
