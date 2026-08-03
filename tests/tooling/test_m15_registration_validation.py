from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from battlebelief_core.canonicalization import manifest_digest
from battlebelief_lab.registration_validation import (
    RegistrationValidationError,
    _schema_for_artifact,
    _validate_registration_references,
    validate_registration_semantics,
    validate_repository_artifacts,
)


def _registration() -> dict[str, object]:
    return {
        "schema_version": 1,
        "registration_id": "m15-test-v1",
        "registration_status": "frozen",
        "hypothesis": "The registered comparison has a measurable effect.",
        "null_hypotheses": ["The registered comparison has no effect."],
        "arms": [
            {
                "arm_id": "heuristic_v0",
                "policy_kind": "heuristic",
                "search_algorithm_id": None,
                "world_distribution_or_belief_mode": "not_applicable",
                "lifecycle": "active",
            },
            {
                "arm_id": "determinization_search_v0",
                "policy_kind": "search",
                "search_algorithm_id": "determinization_search_v0",
                "world_distribution_or_belief_mode": "closed_world_v0",
                "lifecycle": "active",
            },
        ],
        "comparisons": [
            {
                "comparison_id": "heuristic-vs-search",
                "left_arm_id": "heuristic_v0",
                "right_arm_id": "determinization_search_v0",
                "primary_metric_id": "metric_v1",
                "estimand_id": "estimand_v1",
                "analysis_procedure_id": "analysis_v1",
                "direction": "higher_is_better",
                "confidence_level": 0.95,
                "technical_outcome_treatment_id": "analysis_v1",
                "minimum_effect": 0.0,
                "tie_break_rule_id": "tie_v1",
            }
        ],
        "metric_references": [{"metric_id": "metric_v1"}],
        "estimand_references": [{"estimand_id": "estimand_v1"}],
        "analysis_procedure_references": [{"analysis_procedure_id": "analysis_v1"}],
    }


def test_duplicate_arm_ids_are_rejected_by_semantic_validation() -> None:
    registration = _registration()
    arms = registration["arms"]
    assert isinstance(arms, list)
    arms.append(dict(arms[0]))
    with pytest.raises(RegistrationValidationError, match="duplicate arm_id"):
        validate_registration_semantics(registration)


def test_unknown_comparison_arm_is_rejected() -> None:
    registration = _registration()
    comparisons = registration["comparisons"]
    assert isinstance(comparisons, list)
    comparisons[0]["right_arm_id"] = "unknown_arm"
    with pytest.raises(RegistrationValidationError, match="unknown arm"):
        validate_registration_semantics(registration)


def test_information_set_arm_requires_pinned_search_id() -> None:
    registration = _registration()
    arms = registration["arms"]
    assert isinstance(arms, list)
    arms[1]["arm_id"] = "information_set_duct_open_world_v0"
    arms[1]["search_algorithm_id"] = "other_search"
    with pytest.raises(RegistrationValidationError, match="information_set_duct"):
        validate_registration_semantics(registration)


def test_comparison_references_must_be_declared() -> None:
    registration = _registration()
    registration["metric_references"] = [{"metric_id": "declared"}]
    registration["estimand_references"] = [{"estimand_id": "declared"}]
    registration["analysis_procedure_references"] = [{"analysis_procedure_id": "declared"}]
    registration["comparisons"][0].update(
        {
            "primary_metric_id": "missing",
            "estimand_id": "missing",
            "analysis_procedure_id": "missing",
        }
    )
    with pytest.raises(RegistrationValidationError, match="primary_metric_id"):
        validate_registration_semantics(registration)


def test_search_execution_schema_classification_is_structural() -> None:
    root = Path(__file__).resolve().parents[2]
    value = {
        "spec_id": "information-set-duct-v0-execution-v1",
        "arm_id": "information_set_duct_v0",
        "world_sampling": {},
        "lookahead": {},
    }
    result = _schema_for_artifact(root / "registrations/spec.json", value, root)
    assert result is not None
    assert result[1] == "search_execution"


def test_reference_matching_does_not_accept_identifier_substrings(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "example.md").write_text(
        "---\ndocument_id: example-doc\nversion: 1\n---\n\n`paired_mean_difference_v1`\n",
        encoding="utf-8",
    )
    errors = _validate_registration_references(
        {
            "contract_references": [],
            "metric_references": [
                {
                    "document_id": "example-doc",
                    "document_version": 1,
                    "metric_id": "mean_difference_v1",
                }
            ],
            "estimand_references": [],
            "analysis_procedure_references": [],
        },
        tmp_path,
    )
    assert any("unknown metric_id" in error for error in errors)


def test_duplicate_registration_ids_are_reported(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / "schemas", tmp_path / "schemas")
    shutil.copytree(root / "docs", tmp_path / "docs")
    registrations = tmp_path / "registrations"
    registrations.mkdir()
    source = root / "schemas/examples/experiment-registration.example.json"
    for name in ("one.json", "two.json"):
        (registrations / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    errors = validate_repository_artifacts(tmp_path)
    assert any("duplicate registration_id" in error for error in errors)


def test_unsealed_registration_cannot_contain_implementation_digest() -> None:
    registration = _registration()
    registration["policy_digest"] = (
        "sha256:1111111111111111111111111111111111111111111111111111111111111111"
    )
    with pytest.raises(RegistrationValidationError, match="implementation digest"):
        validate_registration_semantics(registration)


def test_budget_profile_mode_requires_matching_artifact_state() -> None:
    registration = _registration()
    registration["budget_profiles"] = {
        "deployment_utility": {
            "budget_mode": "fixed",
            "selected_work_value": None,
            "calibration_spec_digest": None,
            "benchmark_spec_digest": None,
        }
    }
    with pytest.raises(RegistrationValidationError, match="fixed budget"):
        validate_registration_semantics(registration)


def test_strict_loader_rejects_duplicate_keys_and_non_nfc(tmp_path: Path) -> None:
    from battlebelief_lab.registration_validation import load_json_strict

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"a": 1, "a": 2}', encoding="utf-8")
    with pytest.raises(RegistrationValidationError, match="duplicate JSON key"):
        load_json_strict(duplicate)

    non_nfc = tmp_path / "non-nfc.json"
    non_nfc.write_text(json.dumps({"value": "e\u0301"}), encoding="utf-8")
    with pytest.raises(RegistrationValidationError, match="NFC"):
        load_json_strict(non_nfc)


def _repository_fixture(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / "schemas", tmp_path / "schemas")
    shutil.copytree(root / "docs", tmp_path / "docs")
    registration = json.loads(
        (root / "schemas/examples/experiment-registration.example.json").read_text()
    )
    registration["registration_id"] = "m15-test-registration-v1"
    registration["arms"][1]["execution_spec_digest"] = None
    (tmp_path / "registrations").mkdir()
    (tmp_path / "registrations/registration.json").write_text(json.dumps(registration))
    return tmp_path, registration


def _implementation_binding(registration: dict[str, object], binding_id: str) -> dict[str, object]:
    registration_digest = manifest_digest(registration)
    digest = "sha256:" + "1" * 64
    return {
        "schema_version": 1,
        "binding_id": binding_id,
        "binding_kind": "implementation",
        "artifact_version": 1,
        "supersedes_digest": None,
        "registration_id": registration["registration_id"],
        "registration_digest": registration_digest,
        "arm_id": "heuristic_v0",
        "source_commit": "0" * 40,
        "package_or_wheel_digest": digest,
        "components": {
            "policy": {"state": "bound", "digest": digest},
            "fallback_and_safety": {"state": "bound", "digest": digest},
            "search_algorithm": {"state": "not_applicable"},
            "engine": {"state": "not_applicable"},
            "prior": {"state": "not_applicable"},
            "belief": {"state": "not_applicable"},
            "model": {"state": "not_applicable"},
        },
        "decision_record_schema_digest": digest,
        "canonicalizer_digest": digest,
        "contract_set_digest": digest,
    }


def test_run_binding_must_use_an_implementation_from_the_same_registration(
    tmp_path: Path,
) -> None:
    root, registration = _repository_fixture(tmp_path)
    second = deepcopy(registration)
    second["registration_id"] = "m15-other-registration-v1"
    (root / "registrations/other-registration.json").write_text(json.dumps(second))
    first_impl = _implementation_binding(registration, "implementation-a")
    second_impl = _implementation_binding(second, "implementation-b")
    (root / "registrations/implementation-a.json").write_text(json.dumps(first_impl))
    (root / "registrations/implementation-b.json").write_text(json.dumps(second_impl))
    run = {
        "schema_version": 1,
        "binding_id": "run-a",
        "binding_kind": "run",
        "artifact_version": 1,
        "supersedes_digest": None,
        "run_purpose": "synthetic_acceptance",
        "registration_id": registration["registration_id"],
        "registration_digest": manifest_digest(registration),
        "implementation_binding_digest": manifest_digest(second_impl),
        "schedule_digest": "sha256:" + "2" * 64,
        "seed_family_digest": "sha256:" + "3" * 64,
        "budget_profile_digest": "sha256:" + "4" * 64,
        "runtime_environment_digest": "sha256:" + "5" * 64,
        "ruleset_digest": "sha256:" + "6" * 64,
        "synthetic_fixture_manifest_digest": "sha256:" + "7" * 64,
    }
    (root / "registrations/run-a.json").write_text(json.dumps(run))
    errors = validate_repository_artifacts(root)
    assert any(
        "implementation binding belongs to another registration" in error for error in errors
    )


def test_duplicate_binding_ids_are_reported(tmp_path: Path) -> None:
    root, registration = _repository_fixture(tmp_path)
    binding = _implementation_binding(registration, "same-binding")
    (root / "registrations/implementation-a.json").write_text(json.dumps(binding))
    (root / "registrations/implementation-b.json").write_text(json.dumps(binding))
    errors = validate_repository_artifacts(root)
    assert any("duplicate binding_id" in error for error in errors)


def test_heuristic_binding_cannot_bind_a_search_component(tmp_path: Path) -> None:
    root, registration = _repository_fixture(tmp_path)
    binding = _implementation_binding(registration, "heuristic-with-search")
    binding["components"]["search_algorithm"] = {
        "state": "bound",
        "digest": "sha256:" + "8" * 64,
    }
    (root / "registrations/implementation.json").write_text(json.dumps(binding))
    errors = validate_repository_artifacts(root)
    assert any("heuristic arm cannot bind search_algorithm" in error for error in errors)


def test_registration_execution_spec_digest_must_resolve(tmp_path: Path) -> None:
    root, registration = _repository_fixture(tmp_path)
    registration["arms"][1]["execution_spec_digest"] = "sha256:" + "9" * 64
    (root / "registrations/registration.json").write_text(json.dumps(registration))
    errors = validate_repository_artifacts(root)
    assert any("execution specification digest is unresolved" in error for error in errors)


def test_calibration_spec_digest_must_resolve(tmp_path: Path) -> None:
    root, registration = _repository_fixture(tmp_path)
    registration["budget_profiles"]["deployment_utility"] = {
        "budget_mode": "calibrated_grid",
        "work_unit": "search_work_units",
        "selected_work_value": None,
        "calibration_spec_digest": "sha256:" + "a" * 64,
        "benchmark_spec_digest": None,
    }
    (root / "registrations/registration.json").write_text(json.dumps(registration))
    errors = validate_repository_artifacts(root)
    assert any("calibration digest is unresolved" in error for error in errors)


def test_superseded_artifact_requires_an_existing_predecessor(tmp_path: Path) -> None:
    root, registration = _repository_fixture(tmp_path)
    binding = _implementation_binding(registration, "implementation-v2")
    binding["artifact_version"] = 2
    binding["supersedes_digest"] = "sha256:" + "b" * 64
    (root / "registrations/implementation.json").write_text(json.dumps(binding))
    errors = validate_repository_artifacts(root)
    assert any("superseded artifact is unresolved" in error for error in errors)


def test_schema_diagnostics_do_not_echo_invalid_instance_values(tmp_path: Path) -> None:
    root, registration = _repository_fixture(tmp_path)
    registration["secret_value"] = "synthetic-secret-that-must-not-be-echoed"
    (root / "registrations/registration.json").write_text(json.dumps(registration))
    errors = validate_repository_artifacts(root)
    assert errors
    joined = "\n".join(errors)
    assert "synthetic-secret-that-must-not-be-echoed" not in joined
    assert "schema violation" in joined


def test_reference_requires_accepted_normative_contract_frontmatter(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "example.md").write_text(
        "---\ndocument_id: example-doc\ndocument_type: contract\n"
        "status: draft\nnormative: false\nversion: 1\n---\n",
        encoding="utf-8",
    )
    errors = _validate_registration_references(
        {
            "contract_references": [{"document_id": "example-doc", "document_version": 1}],
            "metric_references": [],
            "estimand_references": [],
            "analysis_procedure_references": [],
        },
        tmp_path,
    )
    assert any("not accepted" in error for error in errors)
    assert any("not normative" in error for error in errors)
