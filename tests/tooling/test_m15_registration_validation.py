from __future__ import annotations

import hashlib
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
    _validate_search_execution_references,
    validate_calibration_evidence,
    validate_calibration_spec,
    validate_registration_semantics,
    validate_repository_artifacts,
    validate_synthetic_fixture_manifest,
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


def test_malformed_reference_lists_fail_closed_without_type_error() -> None:
    registration = _registration()
    registration["metric_references"] = None
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
                    "document_digest": "sha256:"
                    + hashlib.sha256((docs / "example.md").read_bytes()).hexdigest(),
                    "metric_id": "mean_difference_v1",
                }
            ],
            "estimand_references": [],
            "analysis_procedure_references": [],
        },
        tmp_path,
    )
    assert any("unknown metric_id" in error for error in errors)


def test_document_reference_binds_the_exact_document_digest(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    document = docs / "example.md"
    document.write_text(
        "---\ndocument_id: example-doc\ndocument_type: contract\n"
        "status: accepted\nnormative: true\nversion: 1\n---\n",
        encoding="utf-8",
    )
    reference = {
        "contract_references": [
            {
                "document_id": "example-doc",
                "document_version": 1,
                "document_digest": "sha256:" + "0" * 64,
            }
        ],
        "metric_references": [],
        "estimand_references": [],
        "analysis_procedure_references": [],
    }

    errors = _validate_registration_references(reference, tmp_path)

    assert any("document digest mismatch" in error for error in errors)


def test_document_reference_resolves_an_immutable_versioned_snapshot(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    shutil.copytree(repository_root / "schemas", tmp_path / "schemas")
    docs = tmp_path / "docs"
    docs.mkdir()
    current = docs / "example.md"
    current.write_text(
        "---\ndocument_id: example-doc\ndocument_type: contract\n"
        "status: accepted\nnormative: true\nversion: 2\n---\nnew\n",
        encoding="utf-8",
    )
    snapshots = docs / "archive/document-snapshots"
    snapshots.mkdir(parents=True)
    snapshot = snapshots / "example-doc.v1.md"
    snapshot.write_bytes(b"historical document bytes\n")
    digest = "sha256:" + hashlib.sha256(snapshot.read_bytes()).hexdigest()
    (snapshots / "example-doc.v1.metadata.json").write_text(
        json.dumps(
            {
                "document_id": "example-doc",
                "document_version": 1,
                "document_type": "contract",
                "status": "accepted",
                "normative": True,
                "source_path": "docs/example.md",
                "source_digest": digest,
                "snapshot_path": "docs/archive/document-snapshots/example-doc.v1.md",
                "snapshot_digest": digest,
            }
        ),
        encoding="utf-8",
    )
    reference = {
        "contract_references": [
            {
                "document_id": "example-doc",
                "document_version": 1,
                "document_digest": digest,
            }
        ],
        "metric_references": [],
        "estimand_references": [],
        "analysis_procedure_references": [],
    }

    errors = _validate_registration_references(reference, tmp_path)

    assert errors == []

    reference["contract_references"][0]["document_digest"] = "sha256:" + "0" * 64
    errors = _validate_registration_references(reference, tmp_path)

    assert any("document digest mismatch" in error for error in errors)


def test_registration_semantics_use_the_exact_referenced_metric_snapshot(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / "schemas", tmp_path / "schemas")
    shutil.copytree(root / "docs", tmp_path / "docs")
    registration = json.loads(
        (root / "schemas/examples/experiment-registration.example.json").read_text()
    )
    metrics_path = tmp_path / "docs/evaluation/metrics.md"
    historical_metrics = metrics_path.read_bytes()
    snapshots = tmp_path / "docs/archive/document-snapshots"
    snapshots.mkdir(parents=True)
    (snapshots / "evaluation-metrics.v4.md").write_bytes(historical_metrics)
    metrics_digest = "sha256:" + hashlib.sha256(historical_metrics).hexdigest()
    (snapshots / "evaluation-metrics.v4.metadata.json").write_text(
        json.dumps(
            {
                "document_id": "evaluation-metrics",
                "document_version": 4,
                "document_type": "contract",
                "status": "accepted",
                "normative": True,
                "source_path": "docs/evaluation/metrics.md",
                "source_digest": metrics_digest,
                "snapshot_path": "docs/archive/document-snapshots/evaluation-metrics.v4.md",
                "snapshot_digest": metrics_digest,
            }
        ),
        encoding="utf-8",
    )
    current_metrics = metrics_path.read_text(encoding="utf-8")
    current_metrics = current_metrics.replace("version: 4", "version: 5", 1).replace(
        "niedriger ist besser", "höher ist besser", 1
    )
    current_metrics = current_metrics.replace("version: 5", "version: 4", 1)
    metrics_path.write_text(current_metrics, encoding="utf-8")

    validate_registration_semantics(registration, tmp_path)


def test_non_normative_roadmap_snapshot_resolves_for_search_spec(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / "schemas", tmp_path / "schemas")
    shutil.copytree(root / "docs", tmp_path / "docs")
    roadmap_path = tmp_path / "docs/roadmap/research-strategy-and-experiments.md"
    historical_roadmap = roadmap_path.read_bytes()
    snapshots = tmp_path / "docs/archive/document-snapshots"
    snapshots.mkdir(parents=True)
    snapshot = snapshots / "roadmap-research-strategy-and-experiments.v1.md"
    snapshot.write_bytes(historical_roadmap)
    digest = "sha256:" + hashlib.sha256(historical_roadmap).hexdigest()
    (snapshots / "roadmap-research-strategy-and-experiments.v1.metadata.json").write_text(
        json.dumps(
            {
                "document_id": "roadmap-research-strategy-and-experiments",
                "document_version": 1,
                "document_type": "roadmap",
                "status": "accepted",
                "normative": False,
                "source_path": "docs/roadmap/research-strategy-and-experiments.md",
                "source_digest": digest,
                "snapshot_path": (
                    "docs/archive/document-snapshots/"
                    "roadmap-research-strategy-and-experiments.v1.md"
                ),
                "snapshot_digest": digest,
            }
        ),
        encoding="utf-8",
    )
    current = roadmap_path.read_text(encoding="utf-8").replace("version: 1", "version: 2", 1)
    roadmap_path.write_text(current, encoding="utf-8")
    specification = json.loads(
        (root / "schemas/examples/search-execution-spec.example.json").read_text()
    )

    assert _validate_search_execution_references(specification, tmp_path) == []


@pytest.mark.parametrize(
    ("document_type", "normative"),
    [("contract", False), ("roadmap", True)],
)
def test_snapshot_reference_enforces_document_type_and_normative_flag(
    tmp_path: Path, document_type: str, normative: bool
) -> None:
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / "schemas", tmp_path / "schemas")
    shutil.copytree(root / "docs", tmp_path / "docs")
    roadmap_path = tmp_path / "docs/roadmap/research-strategy-and-experiments.md"
    snapshot_bytes = roadmap_path.read_bytes()
    snapshots = tmp_path / "docs/archive/document-snapshots"
    snapshots.mkdir(parents=True)
    snapshot = snapshots / "roadmap-research-strategy-and-experiments.v1.md"
    snapshot.write_bytes(snapshot_bytes)
    digest = "sha256:" + hashlib.sha256(snapshot_bytes).hexdigest()
    (snapshots / "roadmap-research-strategy-and-experiments.v1.metadata.json").write_text(
        json.dumps(
            {
                "document_id": "roadmap-research-strategy-and-experiments",
                "document_version": 1,
                "document_type": document_type,
                "status": "accepted",
                "normative": normative,
                "source_path": "docs/roadmap/research-strategy-and-experiments.md",
                "source_digest": digest,
                "snapshot_path": (
                    "docs/archive/document-snapshots/"
                    "roadmap-research-strategy-and-experiments.v1.md"
                ),
                "snapshot_digest": digest,
            }
        ),
        encoding="utf-8",
    )
    roadmap_path.write_text(
        roadmap_path.read_text(encoding="utf-8").replace("version: 1", "version: 2", 1),
        encoding="utf-8",
    )
    specification = json.loads(
        (root / "schemas/examples/search-execution-spec.example.json").read_text()
    )

    errors = _validate_search_execution_references(specification, tmp_path)

    assert any(
        "document type mismatch" in error or "document must be non-normative" in error
        for error in errors
    )


@pytest.mark.parametrize(
    "missing_document_id",
    ["evaluation-target-population", "evaluation-pool-separation"],
)
def test_registration_requires_target_population_and_pool_contracts(
    missing_document_id: str,
) -> None:
    root = Path(__file__).resolve().parents[2]
    registration = json.loads(
        (root / "schemas/examples/experiment-registration.example.json").read_text()
    )
    registration["contract_references"] = [
        reference
        for reference in registration["contract_references"]
        if reference["document_id"] != missing_document_id
    ]

    with pytest.raises(RegistrationValidationError, match=missing_document_id):
        validate_registration_semantics(registration, root)


def test_registration_references_require_unique_ids_and_document_owners() -> None:
    root = Path(__file__).resolve().parents[2]
    registration = json.loads(
        (root / "schemas/examples/experiment-registration.example.json").read_text()
    )
    registration["metric_references"].append(
        {**registration["metric_references"][0], "document_version": 3}
    )
    with pytest.raises(RegistrationValidationError, match="duplicate metric_id"):
        validate_registration_semantics(registration, root)

    registration = json.loads(
        (root / "schemas/examples/experiment-registration.example.json").read_text()
    )
    registration["contract_references"].append(
        dict(
            next(
                reference
                for reference in registration["contract_references"]
                if reference["document_id"] == "experiment-registration"
            )
        )
    )
    with pytest.raises(RegistrationValidationError, match="duplicate contract reference"):
        validate_registration_semantics(registration, root)

    registration = json.loads(
        (root / "schemas/examples/experiment-registration.example.json").read_text()
    )
    registration["metric_references"][0]["document_id"] = "experiment-registration"
    with pytest.raises(RegistrationValidationError, match="metric_references must reference"):
        validate_registration_semantics(registration, root)


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
    shutil.copytree(root / "tests/fixtures", tmp_path / "tests/fixtures")
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
        "schema_version": 2,
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
        "schema_version": 2,
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
    assert not any("schema violation" in error for error in errors)
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


def test_schema_invalid_registration_is_not_hashed_or_used_as_fallback(tmp_path: Path) -> None:
    root, registration = _repository_fixture(tmp_path)
    registration["artifact_version"] = "not-an-integer"
    (root / "registrations/registration.json").write_text(json.dumps(registration))
    binding = _implementation_binding(registration, "implementation-a")
    binding["registration_digest"] = manifest_digest(registration)
    (root / "registrations/implementation.json").write_text(json.dumps(binding))

    errors = validate_repository_artifacts(root)

    assert any("registration.json: schema violation" in error for error in errors)
    assert any("binding references unknown registration" in error for error in errors)
    assert not any("TypeError" in error for error in errors)


def test_binding_versions_can_form_a_single_supersession_chain(tmp_path: Path) -> None:
    root, registration = _repository_fixture(tmp_path)
    first = _implementation_binding(registration, "implementation-a")
    first_path = root / "registrations/implementation-v1.json"
    first_path.write_text(json.dumps(first))
    second = deepcopy(first)
    second["artifact_version"] = 2
    second["supersedes_digest"] = manifest_digest(first)
    second_path = root / "registrations/implementation-v2.json"
    second_path.write_text(json.dumps(second))

    errors = validate_repository_artifacts(root)

    assert not any("duplicate binding_id" in error for error in errors)
    assert not any("identity mismatch" in error for error in errors)


def test_binding_versions_cannot_branch_from_one_predecessor(tmp_path: Path) -> None:
    root, registration = _repository_fixture(tmp_path)
    first = _implementation_binding(registration, "implementation-a")
    (root / "registrations/implementation-v1.json").write_text(json.dumps(first))
    first_digest = manifest_digest(first)
    for name, digest in (("v2a", "9"), ("v2b", "a")):
        successor = deepcopy(first)
        successor["artifact_version"] = 2
        successor["supersedes_digest"] = first_digest
        successor["canonicalizer_digest"] = "sha256:" + digest * 64
        (root / f"registrations/implementation-{name}.json").write_text(json.dumps(successor))

    errors = validate_repository_artifacts(root)

    assert any("multiple successors" in error for error in errors)


def test_calibration_spec_rejects_unknown_selection_rule() -> None:
    spec = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "schemas/examples/budget-calibration-spec.example.json"
        ).read_text()
    )
    spec["selection_rule_id"] = "unknown-rule"

    with pytest.raises(RegistrationValidationError, match="selection_rule_id"):
        validate_calibration_spec(spec)


def test_calibration_spec_rejects_inconsistent_measurement_sets() -> None:
    spec = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "schemas/examples/budget-calibration-spec.example.json"
        ).read_text()
    )
    spec["required_measurement_ids"] = ["wall_time_ms", "quality"]
    spec["allowed_runtime_measurements"] = ["wall_time_ms", "cpu_time_ms", "quality"]
    spec["forbidden_quality_measurements"] = ["quality"]

    with pytest.raises(RegistrationValidationError, match="runtime and quality"):
        validate_calibration_spec(spec)


def test_calibration_evidence_rejects_status_runtime_inconsistency() -> None:
    root = Path(__file__).resolve().parents[2]
    spec = json.loads((root / "schemas/examples/budget-calibration-spec.example.json").read_text())
    evidence = json.loads(
        (root / "schemas/examples/budget-calibration-evidence.example.json").read_text()
    )
    evidence["runtime_measurements"][1]["status"] = "over_limit"
    evidence["runtime_measurements"][1]["measurements"]["wall_time_ms"] = 2.5

    with pytest.raises(RegistrationValidationError, match="over_limit"):
        validate_calibration_evidence(evidence, spec)


def test_synthetic_run_binding_must_match_fixture_components(tmp_path: Path) -> None:
    root, registration = _repository_fixture(tmp_path)
    implementation = _implementation_binding(registration, "implementation-a")
    implementation_path = root / "registrations/implementation.json"
    implementation_path.write_text(json.dumps(implementation))
    fixture = json.loads(
        (root / "schemas/examples/synthetic-fixture-manifest.example.json").read_text()
    )
    fixture_path = root / "registrations/synthetic-fixture.json"
    fixture_path.write_text(json.dumps(fixture))
    run = {
        "schema_version": 2,
        "binding_id": "run-a",
        "binding_kind": "run",
        "artifact_version": 1,
        "supersedes_digest": None,
        "run_purpose": "synthetic_acceptance",
        "registration_id": registration["registration_id"],
        "registration_digest": manifest_digest(registration),
        "implementation_binding_digest": manifest_digest(implementation),
        "schedule_digest": "sha256:" + "1" * 64,
        "seed_family_digest": manifest_digest(fixture["seed_family"]),
        "budget_profile_digest": manifest_digest(fixture["budget_profile"]),
        "runtime_environment_digest": manifest_digest(fixture["runtime_environment"]),
        "ruleset_digest": manifest_digest(fixture["ruleset_snapshot"]),
        "synthetic_fixture_manifest_digest": manifest_digest(fixture),
    }
    (root / "registrations/run.json").write_text(json.dumps(run))

    errors = validate_repository_artifacts(root)

    assert any("synthetic fixture schedule_digest mismatch" in error for error in errors)


def test_synthetic_fixture_rejects_changed_team_content(tmp_path: Path) -> None:
    root, _ = _repository_fixture(tmp_path)
    fixture = json.loads(
        (root / "schemas/examples/synthetic-fixture-manifest.example.json").read_text()
    )
    team_path = root / "tests/fixtures/teams/fixture-team-alpha.txt"
    team_path.write_text("tampered team\n", encoding="utf-8")

    with pytest.raises(RegistrationValidationError, match="content digest mismatch"):
        validate_synthetic_fixture_manifest(fixture, root)


def test_synthetic_fixture_rejects_path_traversal(tmp_path: Path) -> None:
    root, _ = _repository_fixture(tmp_path)
    fixture = json.loads(
        (root / "schemas/examples/synthetic-fixture-manifest.example.json").read_text()
    )
    fixture["team_fixtures"][0]["repository_path"] = "tests/fixtures/teams/../../secret.txt"

    with pytest.raises(RegistrationValidationError, match="repository path"):
        validate_synthetic_fixture_manifest(fixture, root)


def test_synthetic_fixture_rejects_missing_ruleset_artifact(tmp_path: Path) -> None:
    root, _ = _repository_fixture(tmp_path)
    fixture = json.loads(
        (root / "schemas/examples/synthetic-fixture-manifest.example.json").read_text()
    )
    fixture["ruleset_snapshot"]["repository_path"] = "tests/fixtures/rulesets/missing.json"

    with pytest.raises(RegistrationValidationError, match="does not exist"):
        validate_synthetic_fixture_manifest(fixture, root)


def test_valid_synthetic_run_binding_accepts_array_schedule_digest(tmp_path: Path) -> None:
    root, registration = _repository_fixture(tmp_path)
    implementation = _implementation_binding(registration, "implementation-a")
    (root / "registrations/implementation.json").write_text(json.dumps(implementation))
    fixture = json.loads(
        (root / "schemas/examples/synthetic-fixture-manifest.example.json").read_text()
    )
    (root / "registrations/synthetic-fixture.json").write_text(json.dumps(fixture))
    run = {
        "schema_version": 2,
        "binding_id": "run-a",
        "binding_kind": "run",
        "artifact_version": 1,
        "supersedes_digest": None,
        "run_purpose": "synthetic_acceptance",
        "registration_id": registration["registration_id"],
        "registration_digest": manifest_digest(registration),
        "implementation_binding_digest": manifest_digest(implementation),
        "schedule_digest": manifest_digest(fixture["schedule_rows"]),
        "seed_family_digest": manifest_digest(fixture["seed_family"]),
        "budget_profile_digest": manifest_digest(fixture["budget_profile"]),
        "runtime_environment_digest": manifest_digest(fixture["runtime_environment"]),
        "ruleset_digest": manifest_digest(fixture["ruleset_snapshot"]),
        "synthetic_fixture_manifest_digest": manifest_digest(fixture),
    }
    (root / "registrations/run.json").write_text(json.dumps(run))

    errors = validate_repository_artifacts(root)

    assert errors == []


def test_evaluation_run_bindings_are_closed_until_pool_artifacts_exist(tmp_path: Path) -> None:
    root, registration = _repository_fixture(tmp_path)
    implementation = _implementation_binding(registration, "implementation-a")
    (root / "registrations/implementation.json").write_text(json.dumps(implementation))
    run = {
        "schema_version": 2,
        "binding_id": "evaluation-run",
        "binding_kind": "run",
        "artifact_version": 1,
        "supersedes_digest": None,
        "run_purpose": "evaluation",
        "registration_id": registration["registration_id"],
        "registration_digest": manifest_digest(registration),
        "implementation_binding_digest": manifest_digest(implementation),
        "schedule_digest": "sha256:" + "2" * 64,
        "seed_family_digest": "sha256:" + "3" * 64,
        "budget_profile_digest": "sha256:" + "4" * 64,
        "runtime_environment_digest": "sha256:" + "5" * 64,
        "ruleset_digest": "sha256:" + "6" * 64,
        "team_pool_digest": "sha256:" + "7" * 64,
        "opponent_policy_pool_digest": "sha256:" + "8" * 64,
    }
    (root / "registrations/run.json").write_text(json.dumps(run))

    errors = validate_repository_artifacts(root)

    assert any("evaluation run bindings are not enabled" in error for error in errors)


def test_registration_rule_references_are_field_typed(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    registration = json.loads(
        (root / "schemas/examples/experiment-registration.example.json").read_text()
    )
    registration["pool_rules"]["construction_rule_id"] = "no_effect_stop_v1"

    with pytest.raises(RegistrationValidationError, match="construction_rule_id"):
        validate_registration_semantics(registration, root)


def test_registration_analysis_references_are_field_typed(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    registration = json.loads(
        (root / "schemas/examples/experiment-registration.example.json").read_text()
    )
    registration["comparisons"][0]["technical_outcome_treatment_id"] = (
        "weighted_cluster_bootstrap_v1"
    )

    with pytest.raises(RegistrationValidationError, match="technical outcome treatment"):
        validate_registration_semantics(registration, root)


def test_execution_spec_must_match_registered_arm(tmp_path: Path) -> None:
    root, registration = _repository_fixture(tmp_path)
    specification = json.loads(
        (root / "schemas/examples/search-execution-spec.example.json").read_text()
    )
    specification_digest = manifest_digest(specification)
    (root / "registrations/search-spec.json").write_text(json.dumps(specification))
    arms = registration["arms"]
    assert isinstance(arms, list)
    arms[1]["arm_id"] = "other_search_v0"
    registration["comparisons"][0]["right_arm_id"] = "other_search_v0"
    arms[1]["execution_spec_digest"] = specification_digest
    (root / "registrations/registration.json").write_text(json.dumps(registration))

    errors = validate_repository_artifacts(root)

    assert any("execution specification arm mismatch" in error for error in errors)


def test_registration_semantics_rejects_wrong_metric_direction() -> None:
    root = Path(__file__).resolve().parents[2]
    registration = json.loads(
        (root / "schemas/examples/experiment-registration.example.json").read_text()
    )
    registration["comparisons"][0]["direction"] = "higher_is_better"

    with pytest.raises(RegistrationValidationError, match="direction"):
        validate_registration_semantics(registration, root)


def test_registration_semantics_rejects_non_primary_metric_role() -> None:
    root = Path(__file__).resolve().parents[2]
    registration = json.loads(
        (root / "schemas/examples/experiment-registration.example.json").read_text()
    )
    registration["metric_references"][0]["role"] = "diagnostic"

    with pytest.raises(RegistrationValidationError, match="cannot be used with role"):
        validate_registration_semantics(registration, root)


def test_reference_requires_accepted_normative_contract_frontmatter(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "example.md").write_text(
        "---\ndocument_id: example-doc\ndocument_type: contract\n"
        "status: draft\nnormative: false\nversion: 1\n---\n",
        encoding="utf-8",
    )
    document_digest = "sha256:" + hashlib.sha256((docs / "example.md").read_bytes()).hexdigest()
    errors = _validate_registration_references(
        {
            "contract_references": [
                {
                    "document_id": "example-doc",
                    "document_version": 1,
                    "document_digest": document_digest,
                }
            ],
            "metric_references": [],
            "estimand_references": [],
            "analysis_procedure_references": [],
        },
        tmp_path,
    )
    assert any("not accepted" in error for error in errors)
    assert any("not normative" in error for error in errors)
