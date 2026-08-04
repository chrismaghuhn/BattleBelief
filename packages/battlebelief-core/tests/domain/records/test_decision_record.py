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
    ResolvedDecisionRecordBinding,
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
    binding = ResolvedDecisionRecordBinding(
        evaluation_run_binding_digest="sha256:" + "8" * 64,
        registration_digest="sha256:" + "1" * 64,
        arm_binding_digest="sha256:" + "2" * 64,
        schedule_digest="sha256:" + "3" * 64,
        budget_profile_digest="sha256:" + "4" * 64,
        seed_family_digest="sha256:" + "5" * 64,
        arm_id="heuristic_v0",
        runtime_and_contract_digests=RuntimeAndContractDigests(
            runtime_digest="sha256:" + "f" * 64,
            contract_set_digest="sha256:" + "1" * 64,
            policy_digest="sha256:" + "2" * 64,
            fallback_and_safety_digest="sha256:" + "3" * 64,
        ),
    )
    context = MeasurementRunContext.create(
        resolved_binding=binding,
        run_scope=RunScopePayload(
            registration_digest="sha256:" + "1" * 64,
            arm_binding_digest="sha256:" + "2" * 64,
            schedule_digest="sha256:" + "3" * 64,
            schedule_row_id="row-0",
            budget_profile_digest="sha256:" + "4" * 64,
            seed_family_digest="sha256:" + "5" * 64,
            runtime_digest="sha256:" + "f" * 64,
            contract_set_digest="sha256:" + "1" * 64,
        ),
        battle_ordinal=0,
    )
    return DecisionRecord.create(
        record_schema_version=1,
        record_status=DecisionRecordStatus.SUBMITTED,
        run_context=context,
        resolved_binding=binding,
        decision_index=0,
        request_identity=_identity(),
        observed_state_digest="sha256:" + "d" * 64,
        safe_submission_set_digest="sha256:" + "e" * 64,
        selected_submission=_move(),
        submission_provenance=ActionProvenance.EXPLICIT_REQUEST,
        fallback_or_error_class=None,
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
        resolved_binding=ResolvedDecisionRecordBinding(
            evaluation_run_binding_digest="sha256:" + "8" * 64,
            registration_digest="sha256:" + "1" * 64,
            arm_binding_digest="sha256:" + "2" * 64,
            schedule_digest="sha256:" + "3" * 64,
            budget_profile_digest="sha256:" + "4" * 64,
            seed_family_digest="sha256:" + "5" * 64,
            arm_id="heuristic_v0",
            runtime_and_contract_digests=RuntimeAndContractDigests(
                runtime_digest="sha256:" + "6" * 64,
                contract_set_digest="sha256:" + "7" * 64,
                policy_digest="sha256:" + "1" * 64,
                fallback_and_safety_digest="sha256:" + "2" * 64,
            ),
        ),
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
    assert not hasattr(record.request_identity, "room_id")
    assert "battle-private-room" not in repr(record)
    assert b"battle-private-room" not in encoded
    assert b"secret" not in encoded


def test_command_encoding_failure_keeps_selected_submission_without_send_claim() -> None:
    record = _record()
    encoding_failure = record.with_updates(
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
        resolved_binding=ResolvedDecisionRecordBinding(
            evaluation_run_binding_digest="sha256:" + "8" * 64,
            registration_digest="sha256:" + "1" * 64,
            arm_binding_digest="sha256:" + "2" * 64,
            schedule_digest="sha256:" + "3" * 64,
            budget_profile_digest="sha256:" + "4" * 64,
            seed_family_digest="sha256:" + "5" * 64,
            arm_id="heuristic_v0",
            runtime_and_contract_digests=RuntimeAndContractDigests(
                runtime_digest="sha256:" + "6" * 64,
                contract_set_digest="sha256:" + "7" * 64,
                policy_digest="sha256:" + "1" * 64,
                fallback_and_safety_digest="sha256:" + "2" * 64,
            ),
        ),
        run_scope=scope,
        battle_ordinal=0,
    )

    assert context.payload.to_dict()["schema_version"] == 1
    assert context.to_dict()["run_context_digest"] == context.run_context_digest

    with pytest.raises(ValueError):
        MeasurementRunContext.create(
            resolved_binding=ResolvedDecisionRecordBinding(
                evaluation_run_binding_digest="sha256:" + "8" * 64,
                registration_digest="sha256:" + "1" * 64,
                arm_binding_digest="sha256:" + "2" * 64,
                schedule_digest="sha256:" + "3" * 64,
                budget_profile_digest="sha256:" + "4" * 64,
                seed_family_digest="sha256:" + "5" * 64,
                arm_id="heuristic_v0",
                runtime_and_contract_digests=RuntimeAndContractDigests(
                    runtime_digest="sha256:" + "6" * 64,
                    contract_set_digest="sha256:" + "7" * 64,
                    policy_digest="sha256:" + "1" * 64,
                    fallback_and_safety_digest="sha256:" + "2" * 64,
                ),
            ),
            run_scope=scope,
            battle_ordinal=True,  # type: ignore[arg-type]
        )


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
        (
            DecisionRecordStatus.TERMINALLY_DISCARDED,
            _move(),
            ActionProvenance.EXPLICIT_REQUEST,
            None,
        ),
        (
            DecisionRecordStatus.RECONCILIATION_REJECTED,
            _move(),
            ActionProvenance.EXPLICIT_REQUEST,
            "rejected",
        ),
        (
            DecisionRecordStatus.FRESHNESS_INVALIDATED,
            _move(),
            ActionProvenance.EXPLICIT_REQUEST,
            None,
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
        _record().with_updates(
            record_status=status,
            selected_submission=selected,
            submission_provenance=provenance,
            fallback_or_error_class=error,
        )


def test_fallback_or_error_class_rejects_raw_error_text_and_negative_rqid() -> None:
    with pytest.raises(ValueError, match="stable code"):
        _record().with_updates(
            record_status=DecisionRecordStatus.SEND_FAILED,
            fallback_or_error_class="Timeout: /var/run/showdown.sock",
        )
    with pytest.raises(ValueError):
        _record().with_updates(request_identity=_identity_with_rqid(-1))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("record_schema_version", True),
        ("decision_index", True),
        ("record_status", "submitted"),
        ("submission_provenance", "explicit_request"),
    ],
)
def test_domain_rejects_schema_type_and_arm_id_mismatches(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        _record().with_updates(**{field: value})


def test_domain_accepts_decision_record_schema_v2() -> None:
    record = _record().with_updates(record_schema_version=2)
    assert record.to_payload()["record_schema_version"] == 2


def test_error_codes_are_status_bound_and_disposition_only_statuses_are_null() -> None:
    with pytest.raises(ValueError):
        _record().with_updates(
            record_status=DecisionRecordStatus.POLICY_REJECTED,
            fallback_or_error_class="disconnect",
        )
    with pytest.raises(ValueError):
        _record().with_updates(
            record_status=DecisionRecordStatus.SESSION_ABORTED,
            fallback_or_error_class="no_legal_action_available",
        )
    with pytest.raises(ValueError):
        _record().with_updates(
            record_status=DecisionRecordStatus.TERMINALLY_DISCARDED,
            fallback_or_error_class="disconnect",
        )

    for status in (
        DecisionRecordStatus.SUPERSEDED_BEFORE_SELECTION,
        DecisionRecordStatus.TERMINALLY_DISCARDED,
    ):
        with pytest.raises(ValueError, match="must not contain an error class"):
            _record().with_updates(
                record_status=status,
                selected_submission=None,
                submission_provenance=None,
                fallback_or_error_class="disconnect",
            )

    with pytest.raises(ValueError, match="must not contain an error class"):
        _record().with_updates(
            record_schema_version=2,
            record_status=DecisionRecordStatus.FRESHNESS_INVALIDATED,
            selected_submission=None,
            submission_provenance=None,
            fallback_or_error_class="disconnect",
        )

    discarded = _record().with_updates(
        record_status=DecisionRecordStatus.TERMINALLY_DISCARDED,
        selected_submission=None,
        submission_provenance=None,
        fallback_or_error_class=None,
    )
    assert discarded.to_payload()["fallback_or_error_class"] is None

    invalidated = _record().with_updates(
        record_schema_version=2,
        record_status=DecisionRecordStatus.FRESHNESS_INVALIDATED,
        selected_submission=None,
        submission_provenance=None,
        fallback_or_error_class=None,
    )
    assert invalidated.to_payload()["record_status"] == "freshness_invalidated"

    with pytest.raises(ValueError, match="schema v2"):
        _record().with_updates(
            record_status=DecisionRecordStatus.FRESHNESS_INVALIDATED,
            selected_submission=None,
            submission_provenance=None,
            fallback_or_error_class=None,
        )


@pytest.mark.parametrize("arm_id", [True, "/tmp/private", "internal.example.com", "a" * 129])
def test_resolved_binding_rejects_invalid_arm_ids(arm_id: object) -> None:
    with pytest.raises(ValueError):
        ResolvedDecisionRecordBinding(
            evaluation_run_binding_digest=_DIGEST,
            registration_digest=_DIGEST,
            arm_binding_digest=_DIGEST,
            schedule_digest=_DIGEST,
            budget_profile_digest=_DIGEST,
            seed_family_digest=_DIGEST,
            arm_id=arm_id,  # type: ignore[arg-type]
            runtime_and_contract_digests=RuntimeAndContractDigests(
                runtime_digest=_DIGEST,
                contract_set_digest=_DIGEST,
                policy_digest=_DIGEST,
                fallback_and_safety_digest=_DIGEST,
            ),
        )


def test_record_rejects_a_different_resolved_binding_with_the_same_run_digest() -> None:
    first = _record()
    other = ResolvedDecisionRecordBinding(
        evaluation_run_binding_digest=first._resolved_binding.evaluation_run_binding_digest,
        registration_digest=first._resolved_binding.registration_digest,
        arm_binding_digest=first._resolved_binding.arm_binding_digest,
        schedule_digest=first._resolved_binding.schedule_digest,
        budget_profile_digest=first._resolved_binding.budget_profile_digest,
        seed_family_digest=first._resolved_binding.seed_family_digest,
        arm_id="another_arm",
        runtime_and_contract_digests=RuntimeAndContractDigests(
            runtime_digest=_DIGEST,
            contract_set_digest=_DIGEST,
            policy_digest=_DIGEST,
            fallback_and_safety_digest=_DIGEST,
        ),
    )
    with pytest.raises(ValueError, match="does not match"):
        DecisionRecord.create(
            record_schema_version=1,
            record_status=DecisionRecordStatus.SUBMITTED,
            run_context=first._run_context,
            resolved_binding=other,
            decision_index=0,
            request_identity=_identity(),
            observed_state_digest=_DIGEST,
            safe_submission_set_digest=_DIGEST,
            selected_submission=_move(),
            submission_provenance=ActionProvenance.EXPLICIT_REQUEST,
            fallback_or_error_class=None,
        )


def test_run_context_rejects_scope_identities_not_from_the_binding() -> None:
    first = _record()
    with pytest.raises(ValueError, match="registration_digest"):
        MeasurementRunContext.create(
            resolved_binding=first._resolved_binding,
            run_scope=replace(
                first._run_context.run_scope,
                registration_digest="sha256:" + "9" * 64,
            ),
            battle_ordinal=first._run_context.payload.battle_ordinal,
        )


def test_record_rejects_a_context_without_a_resolved_binding() -> None:
    first = _record()
    with pytest.raises(ValueError, match="resolved binding"):
        MeasurementRunContext(
            payload=first._run_context.payload,
            run_context_digest=first._run_context.run_context_digest,
            run_scope=first._run_context.run_scope,
            resolved_binding=None,
        )


def _identity_with_rqid(rqid: int) -> RequestIdentity:
    return RequestIdentity(room_id="battle-private-room", rqid=rqid, request_digest=_DIGEST)
