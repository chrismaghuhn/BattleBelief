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
    MeasurementRunContext,
    ResolvedDecisionRecordBinding,
    RunScopePayload,
    RuntimeAndContractDigests,
    derive_battle_id_digest,
    derive_run_scope_digest,
    digest_record_envelope,
    validate_decision_record_envelope,
    validate_measurement_run_context,
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


def test_record_examples_have_semantically_valid_identity_digests() -> None:
    record = json.loads((ROOT / "schemas/examples/decision-record.example.json").read_text())
    run = json.loads((ROOT / "schemas/examples/measurement-run.example.json").read_text())

    assert validate_measurement_run_context(run) == []
    assert validate_decision_record_envelope(record) == []

    tampered_run = json.loads(json.dumps(run))
    tampered_run["schema_version"] = 2
    assert validate_measurement_run_context(tampered_run)

    tampered_record = json.loads(json.dumps(record))
    tampered_record["record_id"] = "sha256:" + "0" * 64
    assert validate_decision_record_envelope(tampered_record)


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


def test_submission_schema_matches_domain_action_invariants() -> None:
    schema = json.loads(
        (ROOT / "schemas/records/decision-record-payload.schema.json").read_text(encoding="utf-8")
    )
    payload = json.loads(
        (ROOT / "schemas/examples/decision-record-payload.example.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)

    invalid_move = json.loads(json.dumps(payload))
    invalid_move["selected_submission"]["slot"] = 5
    assert list(validator.iter_errors(invalid_move))

    invalid_team = json.loads(json.dumps(payload))
    invalid_team["selected_submission"] = {
        "kind": "team",
        "provenance": "explicit_request",
        "slot": None,
        "move_id": None,
        "terastallize": False,
        "team_order": [1, 1],
    }
    invalid_team["submission_provenance"] = "explicit_request"
    assert list(validator.iter_errors(invalid_team))

    invalid_status = json.loads(json.dumps(payload))
    invalid_status["record_status"] = "wait_noop"
    assert list(validator.iter_errors(invalid_status))


def test_record_schema_closes_error_taxonomy_and_status_pairings() -> None:
    schema = json.loads(
        (ROOT / "schemas/records/decision-record-payload.schema.json").read_text(encoding="utf-8")
    )
    payload = json.loads(
        (ROOT / "schemas/examples/decision-record-payload.example.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)

    unknown_code = json.loads(json.dumps(payload))
    unknown_code["fallback_or_error_class"] = "banana"
    assert list(validator.iter_errors(unknown_code))

    wrong_status_code = json.loads(json.dumps(payload))
    wrong_status_code["record_status"] = "action_gate_rejected"
    wrong_status_code["fallback_or_error_class"] = "disconnect"
    assert list(validator.iter_errors(wrong_status_code))

    terminal_disposition = json.loads(json.dumps(payload))
    terminal_disposition["record_status"] = "terminally_discarded"
    terminal_disposition["selected_submission"] = None
    terminal_disposition["submission_provenance"] = None
    terminal_disposition["fallback_or_error_class"] = None
    assert list(validator.iter_errors(terminal_disposition)) == []


def test_decision_record_cross_version_vector_is_stable() -> None:
    vectors = json.loads(
        (ROOT / "schemas" / "canonicalization" / "decision-record-test-vectors.json").read_text(
            encoding="utf-8"
        )
    )
    for vector in vectors:
        assert canonicalize(vector["value"]) == vector["canonical_utf8"].encode("utf-8")
        assert manifest_digest(vector["value"]) == "sha256:" + vector["sha256"]
        assert vector["run_context_digest"] == run_context_digest_from_document(
            vector["run_context"]
        )
        assert vector["battle_id_digest"] == vector["run_context"]["battle_id_digest"]
        assert vector["record_id"] == record_id_from_payload(vector["value"])
        assert vector["record_digest"] == digest_record_envelope(
            vector["record_id"], vector["value"]
        )
        scope = RunScopePayload(**vector["run_scope"])
        assert derive_run_scope_digest(scope) == vector["run_scope_digest"]
        assert (
            derive_battle_id_digest(
                vector["run_scope_digest"],
                scope.schedule_row_id,
                vector["battle_ordinal"],
            )
            == vector["battle_id_digest"]
        )


def test_domain_record_serialization_is_envelope_schema_valid() -> None:
    digest = "sha256:" + "a" * 64
    binding = ResolvedDecisionRecordBinding(
        evaluation_run_binding_digest=digest,
        arm_id="heuristic_v0",
        runtime_and_contract_digests=RuntimeAndContractDigests(
            runtime_digest=digest,
            contract_set_digest=digest,
            policy_digest=digest,
            fallback_and_safety_digest=digest,
        ),
    )
    context = MeasurementRunContext.create(
        resolved_binding=binding,
        run_scope=RunScopePayload(
            registration_digest=digest,
            arm_binding_digest=digest,
            schedule_digest=digest,
            schedule_row_id="row-0",
            budget_profile_digest=digest,
            seed_family_digest=digest,
            runtime_digest=digest,
            contract_set_digest=digest,
        ),
        battle_ordinal=0,
    )
    record = DecisionRecord.create(
        record_schema_version=1,
        record_status=DecisionRecordStatus.SUBMITTED,
        run_context=context,
        resolved_binding=binding,
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
    )
    schema = json.loads(
        (ROOT / "schemas/records/decision-record.schema.json").read_text(encoding="utf-8")
    )
    errors = list(Draft202012Validator(schema).iter_errors(record.to_envelope()))
    assert errors == [], [error.message for error in errors]


def run_context_digest_from_document(document: dict[str, object]) -> str:
    return manifest_digest(
        {
            "schema_version": document["schema_version"],
            "evaluation_run_binding_digest": document["evaluation_run_binding_digest"],
            "run_scope_digest": document["run_scope_digest"],
            "battle_id_digest": document["battle_id_digest"],
            "battle_ordinal": document["battle_ordinal"],
        }
    )


def record_id_from_payload(payload: dict[str, object]) -> str:
    from battlebelief_core.domain.records.decision_record import derive_record_id

    return derive_record_id(
        str(payload["run_context_digest"]),
        str(payload["battle_id_digest"]),
        int(payload["decision_index"]),
        payload["request_identity"],  # type: ignore[arg-type]
    )
