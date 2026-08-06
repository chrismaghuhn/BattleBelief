from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from battlebelief_core.canonicalization import manifest_digest
from battlebelief_runtime.adapters.poke_engine.artifact import VerifiedEngineArtifact
from battlebelief_runtime.adapters.poke_engine.errors import (
    EngineArtifactError,
    EngineFailureClass,
)
from battlebelief_runtime.adapters.poke_engine.native_probe import (
    execute_native_probe,
    load_fixture_bundle,
    run_native_probe,
)
from battlebelief_runtime.search_status import EngineArtifactIdentity

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "poke_engine"
DIGEST = "sha256:" + "a" * 64


class FakeMove:
    def __init__(self, *, id: str, pp: int, disabled: bool) -> None:
        self.id = id
        self.pp = pp
        self.disabled = disabled


class FakePokemon:
    def __init__(self, *, moves: list[FakeMove], **values: Any) -> None:
        self.moves = moves
        self.terastallized = False
        for key, value in values.items():
            setattr(self, key, value)


class FakeSide:
    def __init__(self, *, pokemon: list[FakePokemon]) -> None:
        self.pokemon = pokemon


class FakeState:
    def __init__(self, *, side_one: FakeSide, side_two: FakeSide) -> None:
        self.side_one = side_one
        self.side_two = side_two
        self.transition_count = 0

    def to_string(self) -> str:
        return (
            f"{self.transition_count}:"
            f"{self.side_one.pokemon[0].terastallized}:"
            f"{self.side_two.pokemon[0].terastallized}"
        )

    def apply_instructions(self, instructions: SimpleNamespace) -> FakeState:
        state = copy.deepcopy(self)
        state.transition_count += 1
        if instructions.tera:
            state.side_one.pokemon[0].terastallized = True
        return state

    def reverse_instructions(self, instructions: SimpleNamespace) -> FakeState:
        state = copy.deepcopy(self)
        state.transition_count -= 1
        if instructions.tera:
            state.side_one.pokemon[0].terastallized = False
        return state


def _native(*, fail: bool = False, total_visits: int = 1000) -> SimpleNamespace:
    def generate(
        _state: FakeState, side_one_choice: str, _side_two_choice: str
    ) -> list[SimpleNamespace]:
        if fail:
            raise RuntimeError("C:\\Users\\alice\\private native failure")
        return [SimpleNamespace(tera=side_one_choice.endswith("-tera"))]

    def search(
        _state: FakeState, *, duration_ms: int, iterations: int, threads: int
    ) -> SimpleNamespace:
        assert duration_ms == 5
        assert iterations == 1000
        assert threads == 1
        return SimpleNamespace(side_one=[object()], side_two=[object()], total_visits=total_visits)

    return SimpleNamespace(
        Move=FakeMove,
        Pokemon=FakePokemon,
        Side=FakeSide,
        State=FakeState,
        generate_instructions=generate,
        monte_carlo_tree_search=search,
    )


def _identity(
    *, fixture_digest: str, result_digest: str, config_digest: str
) -> EngineArtifactIdentity:
    return EngineArtifactIdentity(
        artifact_index_digest=DIGEST,
        source_manifest_digest=DIGEST,
        build_manifest_digest=DIGEST,
        wheel_sha256=DIGEST,
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
        sentinel_fixture_digest=fixture_digest,
        sentinel_result_digest=result_digest,
        sentinel_configuration_digest=config_digest,
    )


def test_native_probe_covers_transition_reverse_tera_choices_and_bounded_search() -> None:
    bundle = load_fixture_bundle(FIXTURE_ROOT)

    result = execute_native_probe(_native(), bundle)

    assert result["classification"] == "healthy"
    assert all(result["health"].values())
    assert "ranking" not in str(result).lower()
    assert "score" not in str(result).lower()
    assert "move_choice" not in str(result).lower()


def test_run_native_probe_accepts_only_digest_bound_stable_result(tmp_path: Path) -> None:
    bundle = load_fixture_bundle(FIXTURE_ROOT)
    result = execute_native_probe(_native(), bundle)
    identity = _identity(
        fixture_digest=bundle.fixture_digest,
        result_digest=manifest_digest(result),
        config_digest=bundle.configuration_digest,
    )
    verified = VerifiedEngineArtifact(
        identity=identity,
        package_root=tmp_path,
        extension_path=tmp_path / "poke_engine.pyd",
    )

    availability = run_native_probe(
        verified,
        fixture_root=FIXTURE_ROOT,
        native_module=_native(),
    )

    assert availability.status == "available"
    assert availability.identity == identity


def test_native_exception_and_fixture_digest_mismatch_are_sanitized(tmp_path: Path) -> None:
    bundle = load_fixture_bundle(FIXTURE_ROOT)
    healthy = execute_native_probe(_native(), bundle)
    verified = VerifiedEngineArtifact(
        identity=_identity(
            fixture_digest=DIGEST,
            result_digest=manifest_digest(healthy),
            config_digest=bundle.configuration_digest,
        ),
        package_root=tmp_path,
        extension_path=tmp_path / "poke_engine.pyd",
    )

    with pytest.raises(EngineArtifactError) as mismatch:
        run_native_probe(verified, fixture_root=FIXTURE_ROOT, native_module=_native())
    assert mismatch.value.failure_class is EngineFailureClass.SENTINEL_FAILED
    assert "alice" not in str(mismatch.value)

    verified = VerifiedEngineArtifact(
        identity=_identity(
            fixture_digest=bundle.fixture_digest,
            result_digest=manifest_digest(healthy),
            config_digest=bundle.configuration_digest,
        ),
        package_root=tmp_path,
        extension_path=tmp_path / "poke_engine.pyd",
    )
    with pytest.raises(EngineArtifactError) as unhealthy:
        run_native_probe(verified, fixture_root=FIXTURE_ROOT, native_module=_native(fail=True))
    assert unhealthy.value.failure_class is EngineFailureClass.NATIVE_UNHEALTHY
    assert "private" not in str(unhealthy.value)


def test_native_probe_rejects_a_non_exact_iteration_count() -> None:
    bundle = load_fixture_bundle(FIXTURE_ROOT)

    with pytest.raises(EngineArtifactError) as unhealthy:
        execute_native_probe(_native(total_visits=999), bundle)

    assert unhealthy.value.failure_class is EngineFailureClass.NATIVE_UNHEALTHY
