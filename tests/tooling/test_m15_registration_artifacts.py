"""Acceptance tests for the frozen Task-21 registration artifacts."""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from battlebelief_core.canonicalization import manifest_digest
from battlebelief_core.domain.records.decision_record import (
    MeasurementRunContext,
    ResolvedDecisionRecordBinding,
    RunScopePayload,
    RuntimeAndContractDigests,
)
from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_lab.evaluation.measurement_runner import MeasurementRunner
from battlebelief_lab.evaluation.schedule import ScheduleRow, SideAssignment
from battlebelief_lab.evaluation.seed_families import SeedFamily
from battlebelief_lab.registration_validation import (
    RegistrationValidationError,
    _git_blob_bytes,
    _validate_implementation_provenance,
    artifact_digest,
    validate_calibration_environment_manifest,
    validate_calibration_evidence,
    validate_calibration_state_manifest,
    validate_repository_artifacts,
    validate_synthetic_fixture_manifest,
)

ROOT = Path(__file__).resolve().parents[2]
REGISTRATION = ROOT / "registrations/gen9ou/m1-5-core-comparisons-v1.json"
IMPLEMENTATION = ROOT / "registrations/gen9ou/bindings/heuristic_v0-implementation-v2.json"
RUN_BINDING = ROOT / "registrations/gen9ou/bindings/heuristic_v0-m15-synthetic-run-p1.json"
RUN_BINDING_DIR = ROOT / "registrations/gen9ou/bindings"
FIXTURES = ROOT / "registrations/gen9ou/synthetic/m15-acceptance-inputs-v1.json"
EXECUTION_SPEC = ROOT / "registrations/gen9ou/arm-specs/determinization-search-v0-v4.json"
CALIBRATION_SPEC = ROOT / "registrations/gen9ou/budgets/m15-search-work-calibration-v2.json"
CALIBRATION_ENVIRONMENT = (
    ROOT / "registrations/gen9ou/calibration/m15-calibration-environment-v2.json"
)


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
    assert run_binding["schema_version"] == 4
    assert fixture_manifest["schema_version"] == 3
    assert fixture_manifest["schedule_rows"][0]["row_id"].startswith("sha256:")
    assert "schedule_block" in fixture_manifest["schedule_rows"][0]
    assert "seed_family" in fixture_manifest["schedule_rows"][0]
    assert fixture_manifest["schedule_rows"][0]["seed_family"]["derivation_id"] == (
        "sha256-canonical-fields-v1"
    )
    assert fixture_manifest["budget_profile"]["profile_id"]
    assert fixture_manifest["budget_profile"]["deployment"]["wall_time_budget_ms"] == 2000


def test_each_synthetic_run_binding_resolves_one_schedule_row_and_seed_family() -> None:
    bindings = sorted(RUN_BINDING_DIR.glob("heuristic_v0-m15-synthetic-run-*.json"))
    assert len(bindings) == 2

    fixture_manifest = _load(FIXTURES)
    rows = {row["row_id"]: row for row in fixture_manifest["schedule_rows"]}
    assert len(rows) == 2

    for binding_path in bindings:
        binding = _load(binding_path)
        row = rows[binding["schedule_row_id"]]
        assert binding["seed_family_digest"] == manifest_digest(row["seed_family"])

    assert validate_repository_artifacts(ROOT) == []


def test_synthetic_fixture_rejects_noncanonical_schedule_identity() -> None:
    fixture = _load(FIXTURES)
    fixture["schedule_rows"][0]["row_id"] = "sha256:" + "0" * 64

    with pytest.raises(RegistrationValidationError, match="schedule row"):
        validate_synthetic_fixture_manifest(fixture, ROOT)


def test_heuristic_binding_declares_recomputable_source_manifests() -> None:
    implementation = _load(IMPLEMENTATION)
    assert implementation["schema_version"] == 4
    assert implementation["source_manifest"]
    assert implementation["contract_set"]
    assert implementation["package_or_wheel_source_manifest"]
    assert implementation["runtime_source_manifest"]


def test_implementation_provenance_validates_every_bound_component() -> None:
    implementation = _load(IMPLEMENTATION)
    implementation["components"]["search_algorithm"] = {
        "state": "bound",
        "digest": "sha256:" + "0" * 64,
        "source_manifest": implementation["components"]["policy"]["source_manifest"],
    }

    with pytest.raises(RegistrationValidationError, match="search_algorithm"):
        _validate_implementation_provenance(implementation, ROOT)


def test_implementation_binding_declares_runtime_source_identity() -> None:
    implementation = _load(IMPLEMENTATION)
    assert implementation["runtime_source_manifest"]
    assert implementation["runtime_digest"].startswith("sha256:")


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

    with pytest.raises(RegistrationValidationError, match="policy digest"):
        _validate_implementation_provenance(implementation, ROOT)


def test_git_blob_timeout_is_reported_as_registration_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timeout(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise subprocess.TimeoutExpired(cmd="git show", timeout=30)

    monkeypatch.setattr(subprocess, "run", timeout)

    with pytest.raises(RegistrationValidationError, match="timed out"):
        _git_blob_bytes(ROOT, "ebbc648fc62908a0227e8d90ab03b3692f583aca", "file.txt")


def test_implementation_provenance_rejects_malformed_component_manifest() -> None:
    implementation = _load(IMPLEMENTATION)
    implementation["components"]["policy"]["source_manifest"] = [None]

    with pytest.raises(RegistrationValidationError):
        _validate_implementation_provenance(implementation, ROOT)


def test_calibration_state_manifest_matches_complete_frozen_product() -> None:
    manifest = _load(
        ROOT / "registrations/gen9ou/calibration/m15-synthetic-calibration-states-v2.json"
    )

    incomplete = json.loads(json.dumps(manifest))
    incomplete["states"].pop()

    with pytest.raises(
        RegistrationValidationError,
        match=r"calibration executable inputs|state construction",
    ):
        validate_calibration_state_manifest(incomplete)

    reordered = json.loads(json.dumps(manifest))
    reordered["states"][0], reordered["states"][1] = (
        reordered["states"][1],
        reordered["states"][0],
    )

    with pytest.raises(
        RegistrationValidationError,
        match="calibration executable inputs",
    ):
        validate_calibration_state_manifest(reordered)


def test_calibration_states_bind_executable_public_inputs() -> None:
    manifest = _load(
        ROOT / "registrations/gen9ou/calibration/m15-synthetic-calibration-states-v2.json"
    )
    for state in manifest["states"]:
        assert "public_observed_state" in state
        assert "decision_request" in state
        assert "safe_submission_set" in state
        assert state["public_state"]["active_slot_count"] == 1
        assert state["public_observed_state"]["p1"]["active_slot"] == 1
        assert state["public_observed_state"]["p2"]["active_slot"] == 1
    assert len(manifest["states"]) == 12


def test_calibration_environment_matches_reference_and_implementation() -> None:
    specification = _load(CALIBRATION_SPEC)
    environment = _load(CALIBRATION_ENVIRONMENT)
    implementation = _load(IMPLEMENTATION)

    validate_calibration_environment_manifest(environment)
    assert environment["implementation_binding_digest"] == artifact_digest(implementation)
    assert environment["runtime_digest"] == implementation["runtime_digest"]
    for field, expected in specification["reference_environment_specification"].items():
        assert environment["runtime_environment"][field] == expected
    assert validate_repository_artifacts(ROOT) == []

    wrong_python = json.loads(json.dumps(environment))
    wrong_python["runtime_environment"]["python"] = "3.13"
    wrong_python["runtime_environment_digest"] = manifest_digest(
        wrong_python["runtime_environment"]
    )
    with pytest.raises(RegistrationValidationError, match="reference environment"):
        validate_calibration_evidence(
            {
                "calibration_spec_digest": artifact_digest(specification),
                "measurement_profile_id": specification["measurement_profile_id"],
                "selection_measurement_id": specification["selection_measurement_id"],
                "runtime_limits_ms": specification["runtime_limits_ms"],
                "actual_environment_digest": artifact_digest(wrong_python),
                "actual_calibration_state_digest": specification[
                    "calibration_state_manifest_digest"
                ],
                "runtime_measurements": [],
                "selected_work_value": None,
            },
            specification,
            environment_manifest=wrong_python,
            implementation_binding=implementation,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [("platform", "windows-2025"), ("runtime_profile", "other-profile")],
)
def test_calibration_environment_rejects_reference_mismatches(field: str, value: str) -> None:
    specification = _load(CALIBRATION_SPEC)
    environment = _load(CALIBRATION_ENVIRONMENT)
    implementation = _load(IMPLEMENTATION)
    environment["runtime_environment"][field] = value
    environment["runtime_environment_digest"] = manifest_digest(environment["runtime_environment"])
    evidence = {
        "calibration_spec_digest": artifact_digest(specification),
        "measurement_profile_id": specification["measurement_profile_id"],
        "selection_measurement_id": specification["selection_measurement_id"],
        "runtime_limits_ms": specification["runtime_limits_ms"],
        "actual_environment_digest": artifact_digest(environment),
        "actual_calibration_state_digest": specification["calibration_state_manifest_digest"],
        "runtime_measurements": [],
        "selected_work_value": None,
    }
    with pytest.raises(RegistrationValidationError, match="calibration"):
        validate_calibration_evidence(
            evidence,
            specification,
            environment_manifest=environment,
            implementation_binding=implementation,
        )


def test_calibration_environment_rejects_unrelated_runtime_digest() -> None:
    specification = _load(CALIBRATION_SPEC)
    environment = _load(CALIBRATION_ENVIRONMENT)
    implementation = _load(IMPLEMENTATION)
    environment["runtime_digest"] = "sha256:" + "0" * 64
    evidence = {
        "calibration_spec_digest": artifact_digest(specification),
        "measurement_profile_id": specification["measurement_profile_id"],
        "selection_measurement_id": specification["selection_measurement_id"],
        "runtime_limits_ms": specification["runtime_limits_ms"],
        "actual_environment_digest": artifact_digest(environment),
        "actual_calibration_state_digest": specification["calibration_state_manifest_digest"],
        "runtime_measurements": [],
        "selected_work_value": None,
    }
    with pytest.raises(RegistrationValidationError, match="runtime digest"):
        validate_calibration_evidence(
            evidence,
            specification,
            environment_manifest=environment,
            implementation_binding=implementation,
        )


def test_each_synthetic_row_builds_a_core_run_context_and_runner() -> None:
    fixture = _load(FIXTURES)
    implementation = _load(IMPLEMENTATION)
    implementation_digest = artifact_digest(implementation)
    for binding_path in sorted(RUN_BINDING_DIR.glob("heuristic_v0-m15-synthetic-run-*.json")):
        binding = _load(binding_path)
        row_value = next(
            row for row in fixture["schedule_rows"] if row["row_id"] == binding["schedule_row_id"]
        )
        row = ScheduleRow(
            row_id=row_value["row_id"],
            base_matchup_id=row_value["base_matchup_id"],
            side_assignment=SideAssignment(row_value["side_assignment"]),
            schedule_block=row_value["schedule_block"],
            seed_family=SeedFamily(**row_value["seed_family"]),
            repetition_index=row_value["repetition_index"],
        )
        digests = RuntimeAndContractDigests(
            runtime_digest=implementation["runtime_digest"],
            contract_set_digest=implementation["contract_set_digest"],
            policy_digest=implementation["components"]["policy"]["digest"],
            fallback_and_safety_digest=implementation["components"]["fallback_and_safety"][
                "digest"
            ],
        )
        resolved = ResolvedDecisionRecordBinding(
            evaluation_run_binding_digest=artifact_digest(binding),
            registration_digest=binding["registration_digest"],
            arm_binding_digest=implementation_digest,
            schedule_digest=binding["schedule_digest"],
            budget_profile_digest=binding["budget_profile_digest"],
            seed_family_digest=binding["seed_family_digest"],
            arm_id="heuristic_v0",
            runtime_and_contract_digests=digests,
        )
        context = MeasurementRunContext.create(
            resolved_binding=resolved,
            run_scope=RunScopePayload(
                registration_digest=binding["registration_digest"],
                arm_binding_digest=implementation_digest,
                schedule_digest=binding["schedule_digest"],
                schedule_row_id=row.row_id,
                budget_profile_digest=binding["budget_profile_digest"],
                seed_family_digest=row.seed_family.digest,
                runtime_digest=implementation["runtime_digest"],
                contract_set_digest=implementation["contract_set_digest"],
            ),
            battle_ordinal=0,
        )
        sink = SimpleNamespace(records=(), accepted_record_count=0, accepted_record_digests=())

        class _NoRequestSession:
            def __init__(self, trace_sink: Any) -> None:
                self.trace_sink = trace_sink

            async def run(self) -> Any:
                return SimpleNamespace(
                    trace_error=None,
                    record_error=None,
                    primary_error=None,
                    state=ObservedState.initial("ash"),
                    explicit_request_submissions=0,
                    default_submissions=0,
                    room_control_or_chat_count=0,
                )

            def failure_result(self, error: BaseException) -> Any:
                del error
                return SimpleNamespace(
                    trace_error=None,
                    record_error=None,
                    primary_error=None,
                    state=ObservedState.initial("ash"),
                    explicit_request_submissions=0,
                    default_submissions=0,
                    room_control_or_chat_count=0,
                )

            def flush_trace(self) -> None:
                return None

            def close_trace(self) -> None:
                return None

        session = _NoRequestSession(sink)
        runner = MeasurementRunner(
            session=session,
            trace_sink=sink,
            run_context=context,
            schedule_row=row,
        )
        result = asyncio.run(runner.run())
        assert result.run_context_digest == context.run_context_digest
        assert result.run_status.value == "no_request"


def test_search_fallback_resolves_to_registered_heuristic_arm() -> None:
    specification = _load(EXECUTION_SPEC)
    assert specification["fallback_arm_id"] == "heuristic_v0"


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
