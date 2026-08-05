"""Acceptance tests for the frozen Task-21 registration artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from battlebelief_lab.registration_validation import (
    artifact_digest,
    validate_repository_artifacts,
)

ROOT = Path(__file__).resolve().parents[2]
REGISTRATION = ROOT / "registrations/gen9ou/m1-5-core-comparisons-v1.json"
IMPLEMENTATION = ROOT / "registrations/gen9ou/bindings/heuristic_v0-implementation.json"
RUN_BINDING = ROOT / "registrations/gen9ou/bindings/heuristic_v0-m15-synthetic-run.json"
FIXTURES = ROOT / "registrations/gen9ou/synthetic/m15-acceptance-inputs-v1.json"
EXECUTION_SPEC = ROOT / "registrations/gen9ou/arm-specs/determinization-search-v0.json"
CALIBRATION_SPEC = ROOT / "registrations/gen9ou/budgets/m15-search-work-calibration-v1.json"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_task21_artifacts_exist_and_pass_the_repository_validator() -> None:
    for path in (
        REGISTRATION,
        IMPLEMENTATION,
        RUN_BINDING,
        FIXTURES,
        EXECUTION_SPEC,
        CALIBRATION_SPEC,
    ):
        assert path.is_file(), path

    assert validate_repository_artifacts(ROOT) == []


def test_registration_freezes_arms_comparisons_and_digest_references() -> None:
    registration = _load(REGISTRATION)
    assert artifact_digest(registration) == artifact_digest(dict(registration))
    assert [arm["arm_id"] for arm in registration["arms"]] == [
        "heuristic_v0",
        "determinization_search_v0",
        "information_set_duct_closed_world_v0",
        "information_set_duct_open_world_v0",
        "model_or_hybrid_v0",
    ]
    assert [comparison["comparison_id"] for comparison in registration["comparisons"]] == [
        "heuristic-vs-determinization",
        "determinization-vs-duct-closed-world",
        "duct-closed-vs-duct-open-world",
    ]
    model = next(arm for arm in registration["arms"] if arm["arm_id"] == "model_or_hybrid_v0")
    assert model["lifecycle"] == "deferred"
    assert all(
        model["arm_id"] not in {comparison["left_arm_id"], comparison["right_arm_id"]}
        for comparison in registration["comparisons"]
    )

    search = _load(EXECUTION_SPEC)
    search_arm = next(
        arm for arm in registration["arms"] if arm["arm_id"] == "determinization_search_v0"
    )
    assert search_arm["execution_spec_digest"] == artifact_digest(search)

    calibration = _load(CALIBRATION_SPEC)
    for profile in registration["budget_profiles"].values():
        assert profile["calibration_spec_digest"] == artifact_digest(calibration)
        assert profile["selected_work_value"] is None


def test_only_heuristic_is_implementation_bound() -> None:
    registration = _load(REGISTRATION)
    implementation = _load(IMPLEMENTATION)
    assert implementation["registration_id"] == registration["registration_id"]
    assert implementation["registration_digest"] == artifact_digest(registration)
    assert implementation["arm_id"] == "heuristic_v0"
    assert implementation["components"]["policy"]["state"] == "bound"
    assert implementation["components"]["fallback_and_safety"]["state"] == "bound"
    for component in ("search_algorithm", "engine", "prior", "belief", "model"):
        assert implementation["components"][component]["state"] == "not_applicable"


def test_synthetic_run_binding_uses_fixture_provenance_without_opening_pools() -> None:
    run_binding = _load(RUN_BINDING)
    fixture_manifest = _load(FIXTURES)
    implementation = _load(IMPLEMENTATION)
    assert run_binding["run_purpose"] == "synthetic_acceptance"
    assert "team_pool_digest" not in run_binding
    assert "opponent_policy_pool_digest" not in run_binding
    assert run_binding["implementation_binding_digest"] == artifact_digest(implementation)
    assert run_binding["synthetic_fixture_manifest_digest"] == artifact_digest(fixture_manifest)
    assert run_binding["calibration_evidence_digest"] is None
