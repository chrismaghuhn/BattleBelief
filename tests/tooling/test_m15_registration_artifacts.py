"""Acceptance tests for the frozen Task-21 registration artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from battlebelief_lab.registration_validation import (
    RegistrationValidationError,
    _git_blob_bytes,
    _validate_implementation_provenance,
    artifact_digest,
    validate_calibration_evidence,
    validate_repository_artifacts,
    validate_synthetic_fixture_manifest,
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
    implementation = _load(IMPLEMENTATION)
    assert registration["schema_version"] == 4
    assert implementation["registration_digest"] == artifact_digest(registration)
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
    assert search["world_sampling"]["count"] == 16
    assert search["budget_parameter"]["parameter_id"] == "per_world_work"
    assert search["budget_parameter"]["ordered_work_grid"] == [64, 128, 256, 512]
    assert (
        search["budget_parameter"]["total_work_formula"]
        == "world_sampling_count_times_per_world_work"
    )

    calibration = _load(CALIBRATION_SPEC)
    for profile in registration["budget_profiles"].values():
        assert profile["calibration_spec_digest"] == artifact_digest(calibration)
        assert profile["calibrated_parameter"] == "per_world_work"
        assert profile["ordered_work_grid"] == [64, 128, 256, 512]
        assert profile["total_work_formula"] == ("world_sampling_count_times_per_world_work")
        assert profile["deployment"]["work_value"] is None
        assert profile["mechanism"]["work_value"] is None

    assert registration["metric_references"] == [
        {
            "document_id": "evaluation-metrics",
            "document_version": 4,
            "document_digest": registration["metric_references"][0]["document_digest"],
            "metric_id": "battle_outcome_weighted_v1",
            "role": "primary",
        },
        {
            "document_id": "evaluation-metrics",
            "document_version": 4,
            "document_digest": registration["metric_references"][1]["document_digest"],
            "metric_id": "end_to_end_latency_ms_v1",
            "role": "diagnostic",
        },
    ]
    for comparison, gate in zip(
        registration["comparisons"], registration["decision_gates"], strict=True
    ):
        assert comparison["primary_metric_id"] == "battle_outcome_weighted_v1"
        assert comparison["direction"] == "higher_is_better"
        assert comparison["minimum_effect"] == 0.05
        assert comparison["confidence_level"] == 0.95
        assert comparison["confidence_sidedness"] == "one_sided"
        assert comparison["tie_break_metric_id"] == "end_to_end_latency_ms_v1"
        assert gate["comparison_id"] == comparison["comparison_id"]
        assert gate["go_rule_id"] == "lower_confidence_bound_at_least_minimum_effect_v1"


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
    assert run_binding["schema_version"] == 3
    assert fixture_manifest["schema_version"] == 3
    assert fixture_manifest["schedule_rows"][0]["row_id"].startswith("sha256:")
    assert "schedule_block" in fixture_manifest["schedule_rows"][0]
    assert "seed_family" in fixture_manifest["schedule_rows"][0]
    assert fixture_manifest["schedule_rows"][0]["seed_family"]["derivation_id"] == (
        "sha256-canonical-fields-v1"
    )
    assert fixture_manifest["budget_profile"]["profile_id"]
    assert fixture_manifest["budget_profile"]["deployment"]["wall_time_budget_ms"] == 2000


def test_synthetic_fixture_rejects_noncanonical_schedule_identity() -> None:
    fixture = _load(FIXTURES)
    fixture["schedule_rows"][0]["row_id"] = "sha256:" + "0" * 64

    try:
        validate_synthetic_fixture_manifest(fixture, ROOT)
    except ValueError as error:
        assert "schedule row" in str(error)
    else:
        raise AssertionError("noncanonical schedule row was accepted")


def test_heuristic_binding_declares_recomputable_source_manifests() -> None:
    implementation = _load(IMPLEMENTATION)
    assert implementation["schema_version"] == 3
    assert implementation["source_manifest"]
    assert implementation["contract_set"]
    assert implementation["package_or_wheel_source_manifest"]


def test_implementation_source_manifest_reads_the_frozen_commit_tree() -> None:
    content = _git_blob_bytes(
        ROOT,
        "ebbc648fc62908a0227e8d90ab03b3692f583aca",
        "packages/battlebelief-core/src/battlebelief_core/application/decision/heuristic_policy.py",
    )
    assert (
        "sha256:" + hashlib.sha256(content).hexdigest()
        == _load(IMPLEMENTATION)["components"]["policy"]["source_manifest"][0]["content_digest"]
    )


def test_heuristic_binding_rejects_a_tampered_policy_digest() -> None:
    implementation = _load(IMPLEMENTATION)
    implementation["components"]["policy"]["digest"] = "sha256:" + "0" * 64

    try:
        _validate_implementation_provenance(implementation, ROOT)
    except RegistrationValidationError as error:
        assert "policy digest" in str(error)
    else:
        raise AssertionError("tampered policy provenance was accepted")


def test_implementation_provenance_rejects_malformed_component_manifest() -> None:
    implementation = _load(IMPLEMENTATION)
    implementation["components"]["policy"]["source_manifest"] = [None]

    try:
        _validate_implementation_provenance(implementation, ROOT)
    except RegistrationValidationError:
        pass
    else:
        raise AssertionError("malformed component manifest was accepted")


def test_calibration_selection_requires_wall_and_cpu_limits() -> None:
    spec = _load(CALIBRATION_SPEC)
    evidence = {
        "measurement_profile_id": spec["measurement_profile_id"],
        "selection_measurement_id": spec["selection_measurement_id"],
        "runtime_limits_ms": spec["runtime_limits_ms"],
        "runtime_measurements": [
            {
                "work_value": work_value,
                "status": "completed",
                "measurements": {"wall_time_ms": 1900, "cpu_time_ms": 2600},
                "error_class": None,
            }
            for work_value in spec["ordered_work_grid"]
        ],
        "selected_work_value": 512,
    }

    try:
        validate_calibration_evidence(evidence, spec)
    except RegistrationValidationError:
        pass
    else:
        raise AssertionError("CPU-over-limit calibration was accepted")


def test_synthetic_fixture_rejects_unresolved_base_matchup_fixture() -> None:
    fixture = _load(FIXTURES)
    fixture["base_matchups"][0]["hero_team_fixture_id"] = "fixture-team-beta"

    try:
        validate_synthetic_fixture_manifest(fixture, ROOT)
    except RegistrationValidationError as error:
        assert "base matchup" in str(error)
    else:
        raise AssertionError("base matchup fixture substitution was accepted")


def test_synthetic_fixture_rejects_non_mapping_schedule_row() -> None:
    fixture = _load(FIXTURES)
    fixture["schedule_rows"].append("not-a-row")

    try:
        validate_synthetic_fixture_manifest(fixture, ROOT)
    except RegistrationValidationError as error:
        assert "schedule row" in str(error)
    else:
        raise AssertionError("non-mapping schedule row was accepted")


def test_ruleset_fixture_is_versioned_not_a_placeholder_digest() -> None:
    ruleset = _load(ROOT / "tests/fixtures/rulesets/gen9ou.json")
    assert ruleset["ruleset_digest"] != "sha256:" + "7" * 64
    assert ruleset["ruleset_id"] == "synthetic-gen9ou-ruleset-v1"
