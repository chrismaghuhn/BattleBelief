from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]


EXAMPLE_SCHEMA_MAP = {
    "dataset-manifest.example.json": "dataset-manifest.schema.json",
    "engine-capability.example.json": "engine-capability.schema.json",
    "evaluation-claim.example.json": "evaluation-claim.schema.json",
    "ruleset-snapshot.example.json": "ruleset-snapshot.schema.json",
    "search-contract.example.json": "search-contract.schema.json",
    "experiment-registration.example.json": "experiment-registration.schema.json",
    "evaluation-arm-binding.example.json": "evaluation-arm-binding.schema.json",
    "evaluation-run-binding.example.json": "evaluation-run-binding.schema.json",
    "budget-calibration-spec.example.json": "budget-calibration-spec.schema.json",
    "budget-calibration-evidence.example.json": "budget-calibration-evidence.schema.json",
    "search-execution-spec.example.json": "search-execution-spec.schema.json",
    "synthetic-fixture-manifest.example.json": "synthetic-fixture-manifest.schema.json",
}


def test_m15_examples_use_explicit_schema_mappings() -> None:
    schema_root = ROOT / "schemas"
    assert set(EXAMPLE_SCHEMA_MAP) == {
        path.name for path in (schema_root / "examples").glob("*.example.json")
    }
    for example_name, schema_name in EXAMPLE_SCHEMA_MAP.items():
        example = json.loads((schema_root / "examples" / example_name).read_text())
        schema = json.loads((schema_root / "manifests" / schema_name).read_text())
        errors = list(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(example)
        )
        assert errors == [], f"{example_name}: {errors}"


def test_m15_record_and_registration_directories_are_preconditioned() -> None:
    assert not (ROOT / "schemas/records").exists()
    assert not (ROOT / "registrations").exists()


def test_bound_component_requires_digest_and_unbound_component_forbids_it() -> None:
    schema = json.loads((ROOT / "schemas/manifests/evaluation-arm-binding.schema.json").read_text())
    example = json.loads(
        (ROOT / "schemas/examples/evaluation-arm-binding.example.json").read_text()
    )
    example["components"]["policy"] = {"state": "bound"}
    assert list(Draft202012Validator(schema).iter_errors(example))
    example["components"]["policy"] = {
        "state": "not_applicable",
        "digest": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
    }
    assert list(Draft202012Validator(schema).iter_errors(example))


def test_m15_schema_ids_use_the_repository_convention() -> None:
    for path in (ROOT / "schemas/manifests").glob("*.schema.json"):
        schema = json.loads(path.read_text())
        if path.name in {
            "experiment-registration.schema.json",
            "evaluation-arm-binding.schema.json",
            "evaluation-run-binding.schema.json",
            "budget-calibration-spec.schema.json",
            "budget-calibration-evidence.schema.json",
            "synthetic-fixture-manifest.schema.json",
            "search-execution-spec.schema.json",
        }:
            assert schema["$id"].startswith("urn:battlebelief:schema:")
            assert ":v" in schema["$id"]


def test_synthetic_run_requires_a_non_null_fixture_and_no_evaluation_pools() -> None:
    schema = json.loads((ROOT / "schemas/manifests/evaluation-run-binding.schema.json").read_text())
    example = json.loads(
        (ROOT / "schemas/examples/evaluation-run-binding.example.json").read_text()
    )

    for field in ("team_pool_digest", "opponent_policy_pool_digest"):
        candidate = dict(example)
        candidate[field] = "sha256:" + "1" * 64
        assert list(Draft202012Validator(schema).iter_errors(candidate))

    candidate = dict(example)
    candidate["synthetic_fixture_manifest_digest"] = None
    assert list(Draft202012Validator(schema).iter_errors(candidate))


def test_registration_requires_pool_and_comparison_analysis_fields() -> None:
    schema = json.loads(
        (ROOT / "schemas/manifests/experiment-registration.schema.json").read_text()
    )
    example = json.loads(
        (ROOT / "schemas/examples/experiment-registration.example.json").read_text()
    )
    example["pool_rules"] = {}
    example["comparisons"][0].pop("direction", None)
    example["budget_profiles"]["deployment_utility"].pop("work_unit", None)
    assert list(Draft202012Validator(schema).iter_errors(example))


def test_calibration_examples_bind_a_measurement_profile_and_measurements() -> None:
    schema = json.loads(
        (ROOT / "schemas/manifests/budget-calibration-spec.schema.json").read_text()
    )
    example = json.loads(
        (ROOT / "schemas/examples/budget-calibration-spec.example.json").read_text()
    )
    example.pop("measurement_profile_id", None)
    assert list(Draft202012Validator(schema).iter_errors(example))
