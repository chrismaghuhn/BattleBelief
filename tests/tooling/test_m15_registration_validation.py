from __future__ import annotations

import json
from pathlib import Path

import pytest

from battlebelief_lab.registration_validation import (
    RegistrationValidationError,
    validate_registration_semantics,
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
            }
        ],
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
