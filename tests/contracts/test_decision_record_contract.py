from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from tools.check_schemas import EXAMPLE_SCHEMA_MAP, collect_schema_errors

from battlebelief_core.canonicalization import canonicalize, manifest_digest
from battlebelief_core.domain.actions.submission import (
    ActionKind,
    ActionProvenance,
    BattleSubmission,
    RequestIdentity,
)
from battlebelief_core.domain.records.decision_record import (
    DecisionRecord,
    DecisionRecordStatus,
    RuntimeAndContractDigests,
)

ROOT = Path(__file__).resolve().parents[2]


def test_record_schemas_and_examples_are_explicitly_registered() -> None:
    assert EXAMPLE_SCHEMA_MAP["decision-record.example.json"] == "decision-record.schema.json"
    assert (
        EXAMPLE_SCHEMA_MAP["decision-record-payload.example.json"]
        == "decision-record-payload.schema.json"
    )
    assert EXAMPLE_SCHEMA_MAP["measurement-run.example.json"] == "measurement-run.schema.json"


def test_record_examples_validate_against_their_schema() -> None:
    for example_name in (
        "decision-record.example.json",
        "decision-record-payload.example.json",
        "measurement-run.example.json",
    ):
        schema_name = EXAMPLE_SCHEMA_MAP[example_name]
        schema = json.loads(
            (ROOT / "schemas" / "records" / schema_name).read_text(encoding="utf-8")
        )
        example = json.loads(
            (ROOT / "schemas" / "examples" / example_name).read_text(encoding="utf-8")
        )
        errors = list(Draft202012Validator(schema).iter_errors(example))
        assert errors == [], [error.message for error in errors]


def test_schema_checker_accepts_the_task_18_artifacts() -> None:
    errors = collect_schema_errors(ROOT)
    assert errors == [], "\n".join(errors)


def test_decision_record_rejects_unknown_fields() -> None:
    schema = json.loads(
        (ROOT / "schemas" / "records" / "decision-record.schema.json").read_text(encoding="utf-8")
    )
    example = json.loads(
        (ROOT / "schemas" / "examples" / "decision-record.example.json").read_text(encoding="utf-8")
    )
    example["payload"]["password"] = "must-not-serialize"
    errors = list(Draft202012Validator(schema).iter_errors(example))
    assert any("password" in error.message for error in errors)


def test_decision_record_cross_version_vector_is_stable() -> None:
    vectors = json.loads(
        (ROOT / "schemas" / "canonicalization" / "decision-record-test-vectors.json").read_text(
            encoding="utf-8"
        )
    )
    for vector in vectors:
        assert canonicalize(vector["value"]) == vector["canonical_utf8"].encode("utf-8")
        assert manifest_digest(vector["value"]) == "sha256:" + vector["sha256"]


def test_domain_record_serialization_is_envelope_schema_valid() -> None:
    digest = "sha256:" + "a" * 64
    record = DecisionRecord(
        record_schema_version=1,
        record_status=DecisionRecordStatus.SUBMITTED,
        run_context_digest=digest,
        battle_id_digest=digest,
        decision_index=0,
        request_identity=RequestIdentity("battle-room", 1, digest),
        observed_state_digest=digest,
        safe_submission_set_digest=digest,
        selected_submission=BattleSubmission(
            kind=ActionKind.MOVE,
            provenance=ActionProvenance.EXPLICIT_REQUEST,
            slot=1,
            move_id="tackle",
        ),
        submission_provenance=ActionProvenance.EXPLICIT_REQUEST,
        fallback_or_error_class=None,
        policy_or_arm_id="heuristic_v0",
        runtime_and_contract_digests=RuntimeAndContractDigests(
            runtime_digest=digest,
            contract_set_digest=digest,
            policy_digest=digest,
            fallback_and_safety_digest=digest,
        ),
    )
    schema = json.loads(
        (ROOT / "schemas/records/decision-record.schema.json").read_text(encoding="utf-8")
    )
    errors = list(Draft202012Validator(schema).iter_errors(record.to_envelope()))
    assert errors == [], [error.message for error in errors]
