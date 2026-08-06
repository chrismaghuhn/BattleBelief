from __future__ import annotations

import battlebelief_runtime.public_api as public_api


def test_task25_public_exports_are_curated() -> None:
    new_exports = {
        "EngineArtifactIdentity",
        "EngineAvailability",
        "run_gen9_sentinel",
    }

    assert new_exports <= set(public_api.__all__)
    assert not {
        "native_probe",
        "State",
        "SearchAction",
        "TransitionModel",
        "PreparedWorld",
        "MappingFailure",
    } & set(public_api.__all__)
