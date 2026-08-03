from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

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
    RunScopePayload,
    RuntimeAndContractDigests,
    derive_record_id,
    derive_run_scope_digest,
    digest_record_envelope,
)
from battlebelief_core.domain.records.public_projection import project_request_identity

_DIGEST = "sha256:" + "a" * 64


def _identity() -> RequestIdentity:
    return RequestIdentity(room_id="battle-private-room", rqid=3, request_digest=_DIGEST)


def _move() -> BattleSubmission:
    return BattleSubmission(
        kind=ActionKind.MOVE,
        provenance=ActionProvenance.EXPLICIT_REQUEST,
        slot=1,
        move_id="tackle",
    )


def _record() -> DecisionRecord:
    return DecisionRecord(
        record_schema_version=1,
        record_status=DecisionRecordStatus.SUBMITTED,
        run_context_digest="sha256:" + "b" * 64,
        battle_id_digest="sha256:" + "c" * 64,
        decision_index=0,
        request_identity=_identity(),
        observed_state_digest="sha256:" + "d" * 64,
        safe_submission_set_digest="sha256:" + "e" * 64,
        selected_submission=_move(),
        submission_provenance=ActionProvenance.EXPLICIT_REQUEST,
        fallback_or_error_class=None,
        policy_or_arm_id="heuristic_v0",
        runtime_and_contract_digests=RuntimeAndContractDigests(
            runtime_digest="sha256:" + "f" * 64,
            contract_set_digest="sha256:" + "1" * 64,
            policy_digest="sha256:" + "2" * 64,
            fallback_and_safety_digest="sha256:" + "3" * 64,
        ),
    )


def test_record_id_and_digest_are_non_circular_and_bind_identity() -> None:
    record = _record()
    envelope = record.to_envelope()

    assert envelope["record_id"] == derive_record_id(
        record.run_context_digest,
        record.battle_id_digest,
        record.decision_index,
        project_request_identity(record.request_identity),
    )
    assert envelope["record_digest"] == digest_record_envelope(
        envelope["record_id"], envelope["payload"]
    )

    changed_id_digest = digest_record_envelope(
        "sha256:" + "9" * 64,
        envelope["payload"],
    )
    assert changed_id_digest != envelope["record_digest"]
    assert envelope["payload"]["battle_id_digest"] == record.battle_id_digest


def test_run_scope_and_context_derivation_is_explicit_and_room_independent() -> None:
    scope = RunScopePayload(
        registration_digest="sha256:" + "1" * 64,
        arm_binding_digest="sha256:" + "2" * 64,
        schedule_digest="sha256:" + "3" * 64,
        schedule_row_id="row-0",
        budget_profile_digest="sha256:" + "4" * 64,
        seed_family_digest="sha256:" + "5" * 64,
        runtime_digest="sha256:" + "6" * 64,
        contract_set_digest="sha256:" + "7" * 64,
    )
    first = derive_run_scope_digest(scope)
    second = derive_run_scope_digest(scope)
    assert first == second
    assert "room" not in str(scope.to_dict()).casefold()
    context = MeasurementRunContext.create(
        evaluation_run_binding_digest="sha256:" + "8" * 64,
        run_scope=scope,
        battle_ordinal=0,
    )
    assert context.to_dict()["run_context_digest"] == context.run_context_digest
    assert "battle-private-room" not in str(context.to_dict())


def test_record_is_immutable_and_does_not_expose_room_or_account_data() -> None:
    record = _record()
    with pytest.raises(FrozenInstanceError):
        record.decision_index = 1  # type: ignore[misc]

    encoded = record.canonical_envelope_bytes()
    assert b"battle-private-room" not in encoded
    assert b"secret" not in encoded


def test_command_encoding_failure_keeps_selected_submission_without_send_claim() -> None:
    record = _record()
    encoding_failure = replace(
        record,
        record_status=DecisionRecordStatus.COMMAND_ENCODING_FAILED,
        fallback_or_error_class="command_encoding_failed",
    )

    payload = encoding_failure.to_payload()
    assert payload["record_status"] == "command_encoding_failed"
    assert payload["selected_submission"] is not None
    assert payload["fallback_or_error_class"] == "command_encoding_failed"


def test_run_context_schema_version_is_part_of_its_digest() -> None:
    scope = RunScopePayload(
        registration_digest="sha256:" + "1" * 64,
        arm_binding_digest="sha256:" + "2" * 64,
        schedule_digest="sha256:" + "3" * 64,
        schedule_row_id="row-0",
        budget_profile_digest="sha256:" + "4" * 64,
        seed_family_digest="sha256:" + "5" * 64,
        runtime_digest="sha256:" + "6" * 64,
        contract_set_digest="sha256:" + "7" * 64,
    )
    context = MeasurementRunContext.create(
        evaluation_run_binding_digest="sha256:" + "8" * 64,
        run_scope=scope,
        battle_ordinal=0,
    )

    assert context.payload.to_dict()["schema_version"] == 1
    assert context.to_dict()["run_context_digest"] == context.run_context_digest


@pytest.mark.parametrize(
    ("status", "selected", "provenance", "error"),
    [
        (DecisionRecordStatus.SUBMITTED, None, None, None),
        (DecisionRecordStatus.WAIT_NOOP, _move(), ActionProvenance.EXPLICIT_REQUEST, None),
        (DecisionRecordStatus.POLICY_REJECTED, None, None, None),
        (
            DecisionRecordStatus.ACTION_GATE_REJECTED,
            _move(),
            ActionProvenance.EXPLICIT_REQUEST,
            None,
        ),
        (
            DecisionRecordStatus.COMMAND_ENCODING_FAILED,
            _move(),
            ActionProvenance.EXPLICIT_REQUEST,
            None,
        ),
        (DecisionRecordStatus.SEND_FAILED, _move(), ActionProvenance.EXPLICIT_REQUEST, None),
        (
            DecisionRecordStatus.SUPERSEDED_BEFORE_SELECTION,
            _move(),
            ActionProvenance.EXPLICIT_REQUEST,
            "superseded",
        ),
        (DecisionRecordStatus.TERMINALLY_DISCARDED, None, None, None),
        (
            DecisionRecordStatus.RECONCILIATION_REJECTED,
            _move(),
            ActionProvenance.EXPLICIT_REQUEST,
            "rejected",
        ),
    ],
)
def test_terminal_status_matrix_rejects_impossible_records(
    status: DecisionRecordStatus,
    selected: BattleSubmission | None,
    provenance: ActionProvenance | None,
    error: str | None,
) -> None:
    with pytest.raises(ValueError):
        replace(
            _record(),
            record_status=status,
            selected_submission=selected,
            submission_provenance=provenance,
            fallback_or_error_class=error,
        )


def test_fallback_or_error_class_rejects_raw_error_text_and_negative_rqid() -> None:
    with pytest.raises(ValueError):
        replace(_record(), fallback_or_error_class="Timeout: /var/run/showdown.sock")
    with pytest.raises(ValueError):
        replace(_record(), request_identity=_identity_with_rqid(-1))


def _identity_with_rqid(rqid: int) -> RequestIdentity:
    return RequestIdentity(room_id="battle-private-room", rqid=rqid, request_digest=_DIGEST)
