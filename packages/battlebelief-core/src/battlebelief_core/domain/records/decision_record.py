"""Immutable Decision Records and their non-circular deterministic identities."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from battlebelief_core.canonicalization import canonicalize, manifest_digest
from battlebelief_core.domain.actions.submission import (
    ActionProvenance,
    BattleSubmission,
    RequestIdentity,
)
from battlebelief_core.domain.records.public_projection import (
    _thaw,
    project_battle_submission,
    project_request_identity,
)

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class DecisionRecordStatus(StrEnum):
    SUBMITTED = "submitted"
    WAIT_NOOP = "wait_noop"
    POLICY_REJECTED = "policy_rejected"
    ACTION_GATE_REJECTED = "action_gate_rejected"
    COMMAND_ENCODING_FAILED = "command_encoding_failed"
    SEND_FAILED = "send_failed"
    SESSION_ABORTED = "session_aborted"
    SUPERSEDED_BEFORE_SELECTION = "superseded_before_selection"
    TERMINALLY_DISCARDED = "terminally_discarded"
    RECONCILIATION_REJECTED = "reconciliation_rejected"


def _require_digest(name: str, value: str) -> None:
    if not _DIGEST_RE.fullmatch(value):
        raise ValueError(f"{name} must be a sha256 digest")


@dataclass(frozen=True, slots=True)
class RuntimeAndContractDigests:
    runtime_digest: str
    contract_set_digest: str
    policy_digest: str
    fallback_and_safety_digest: str

    def __post_init__(self) -> None:
        for name, value in (
            ("runtime_digest", self.runtime_digest),
            ("contract_set_digest", self.contract_set_digest),
            ("policy_digest", self.policy_digest),
            ("fallback_and_safety_digest", self.fallback_and_safety_digest),
        ):
            _require_digest(name, value)

    def to_dict(self) -> dict[str, str]:
        return {
            "runtime_digest": self.runtime_digest,
            "contract_set_digest": self.contract_set_digest,
            "policy_digest": self.policy_digest,
            "fallback_and_safety_digest": self.fallback_and_safety_digest,
        }


@dataclass(frozen=True, slots=True)
class RunContextPayload:
    schema_version: int
    evaluation_run_binding_digest: str
    run_scope_digest: str
    battle_id_digest: str
    battle_ordinal: int

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported measurement-run schema version")
        for name, value in (
            ("evaluation_run_binding_digest", self.evaluation_run_binding_digest),
            ("run_scope_digest", self.run_scope_digest),
            ("battle_id_digest", self.battle_id_digest),
        ):
            _require_digest(name, value)
        if self.battle_ordinal < 0:
            raise ValueError("battle_ordinal must be non-negative")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "evaluation_run_binding_digest": self.evaluation_run_binding_digest,
            "run_scope_digest": self.run_scope_digest,
            "battle_id_digest": self.battle_id_digest,
            "battle_ordinal": self.battle_ordinal,
        }


@dataclass(frozen=True, slots=True)
class RunScopePayload:
    registration_digest: str
    arm_binding_digest: str
    schedule_digest: str
    schedule_row_id: str
    budget_profile_digest: str
    seed_family_digest: str
    runtime_digest: str
    contract_set_digest: str

    def __post_init__(self) -> None:
        for name, value in (
            ("registration_digest", self.registration_digest),
            ("arm_binding_digest", self.arm_binding_digest),
            ("schedule_digest", self.schedule_digest),
            ("budget_profile_digest", self.budget_profile_digest),
            ("seed_family_digest", self.seed_family_digest),
            ("runtime_digest", self.runtime_digest),
            ("contract_set_digest", self.contract_set_digest),
        ):
            _require_digest(name, value)
        if not self.schedule_row_id:
            raise ValueError("schedule_row_id must not be empty")

    def to_dict(self) -> dict[str, str]:
        return {
            "registration_digest": self.registration_digest,
            "arm_binding_digest": self.arm_binding_digest,
            "schedule_digest": self.schedule_digest,
            "schedule_row_id": self.schedule_row_id,
            "budget_profile_digest": self.budget_profile_digest,
            "seed_family_digest": self.seed_family_digest,
            "runtime_digest": self.runtime_digest,
            "contract_set_digest": self.contract_set_digest,
        }


@dataclass(frozen=True, slots=True)
class MeasurementRunContext:
    payload: RunContextPayload
    run_context_digest: str

    def __post_init__(self) -> None:
        _require_digest("run_context_digest", self.run_context_digest)
        expected = manifest_digest(self.payload.to_dict())
        if self.run_context_digest != expected:
            raise ValueError("run_context_digest does not match payload")

    def to_dict(self) -> dict[str, object]:
        value = self.payload.to_dict()
        value["run_context_digest"] = self.run_context_digest
        return value

    @classmethod
    def create(
        cls,
        *,
        evaluation_run_binding_digest: str,
        run_scope: RunScopePayload,
        battle_ordinal: int,
    ) -> MeasurementRunContext:
        run_scope_digest = derive_run_scope_digest(run_scope)
        battle_id_digest = derive_battle_id_digest(
            run_scope_digest, run_scope.schedule_row_id, battle_ordinal
        )
        payload = RunContextPayload(
            schema_version=1,
            evaluation_run_binding_digest=evaluation_run_binding_digest,
            run_scope_digest=run_scope_digest,
            battle_id_digest=battle_id_digest,
            battle_ordinal=battle_ordinal,
        )
        return cls(payload=payload, run_context_digest=manifest_digest(payload.to_dict()))


def derive_run_scope_digest(run_scope: RunScopePayload) -> str:
    """Hash only the non-circular, canonical run-scope payload."""

    return manifest_digest(run_scope.to_dict())


def derive_battle_id_digest(
    run_scope_digest: str, schedule_row_id: str, battle_ordinal: int
) -> str:
    return manifest_digest(
        {
            "run_scope_digest": run_scope_digest,
            "schedule_row_id": schedule_row_id,
            "battle_ordinal": battle_ordinal,
        }
    )


def derive_record_id(
    run_context_digest: str,
    battle_id_digest: str,
    decision_index: int,
    request_identity: Mapping[str, Any],
) -> str:
    return manifest_digest(
        {
            "run_context_digest": run_context_digest,
            "battle_id_digest": battle_id_digest,
            "decision_index": decision_index,
            "request_identity": dict(_thaw(request_identity)),
        }
    )


def digest_record_envelope(record_id: str, payload: Mapping[str, Any]) -> str:
    """Digest the envelope identity and payload, excluding only the digest itself."""

    return manifest_digest({"record_id": record_id, "payload": dict(payload)})


def validate_measurement_run_context(document: Mapping[str, Any]) -> list[str]:
    """Validate measurement-run digest identities after schema validation."""

    required = {
        "schema_version",
        "evaluation_run_binding_digest",
        "run_scope_digest",
        "battle_id_digest",
        "battle_ordinal",
        "run_context_digest",
    }
    if not required.issubset(document):
        return ["measurement-run document is missing required fields"]
    try:
        payload = RunContextPayload(
            schema_version=document["schema_version"],
            evaluation_run_binding_digest=document["evaluation_run_binding_digest"],
            run_scope_digest=document["run_scope_digest"],
            battle_id_digest=document["battle_id_digest"],
            battle_ordinal=document["battle_ordinal"],
        )
        expected = manifest_digest(payload.to_dict())
    except (TypeError, ValueError):
        return ["measurement-run payload is invalid"]
    if document["run_context_digest"] != expected:
        return ["run_context_digest does not match measurement-run payload"]
    return []


def validate_decision_record_envelope(document: Mapping[str, Any]) -> list[str]:
    """Validate record and envelope digest identities after schema validation."""

    payload = document.get("payload")
    if not isinstance(payload, Mapping):
        return ["decision-record payload is missing"]
    required = {
        "run_context_digest",
        "battle_id_digest",
        "decision_index",
        "request_identity",
    }
    if (
        not required.issubset(payload)
        or "record_id" not in document
        or "record_digest" not in document
    ):
        return ["decision-record envelope is missing identity fields"]
    try:
        expected_id = derive_record_id(
            payload["run_context_digest"],
            payload["battle_id_digest"],
            payload["decision_index"],
            payload["request_identity"],
        )
        expected_digest = digest_record_envelope(expected_id, payload)
    except (TypeError, ValueError):
        return ["decision-record identity fields are invalid"]
    errors: list[str] = []
    if document["record_id"] != expected_id:
        errors.append("record_id does not match decision-record identity")
    if document["record_digest"] != expected_digest:
        errors.append("record_digest does not match decision-record envelope")
    return errors


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    record_schema_version: int
    record_status: DecisionRecordStatus
    run_context_digest: str
    battle_id_digest: str
    decision_index: int
    request_identity: RequestIdentity
    observed_state_digest: str
    safe_submission_set_digest: str
    selected_submission: BattleSubmission | None
    submission_provenance: ActionProvenance | None
    fallback_or_error_class: str | None
    policy_or_arm_id: str
    runtime_and_contract_digests: RuntimeAndContractDigests

    def __post_init__(self) -> None:
        if self.record_schema_version != 1:
            raise ValueError("unsupported Decision-Record schema version")
        if self.decision_index < 0:
            raise ValueError("decision_index must be non-negative")
        _require_digest("run_context_digest", self.run_context_digest)
        _require_digest("battle_id_digest", self.battle_id_digest)
        _require_digest("request_digest", self.request_identity.request_digest)
        if (
            isinstance(self.request_identity.rqid, bool)
            or not isinstance(self.request_identity.rqid, int)
            or self.request_identity.rqid < 0
        ):
            raise ValueError("rqid must be a non-negative integer")
        _require_digest("observed_state_digest", self.observed_state_digest)
        _require_digest("safe_submission_set_digest", self.safe_submission_set_digest)
        if not self.policy_or_arm_id:
            raise ValueError("policy_or_arm_id must not be empty")
        if self.fallback_or_error_class is not None and not re.fullmatch(
            r"[a-z][a-z0-9_.:-]*", self.fallback_or_error_class
        ):
            raise ValueError("fallback_or_error_class must be a stable code")
        if self.selected_submission is None and self.submission_provenance is not None:
            raise ValueError("submission provenance requires a selected submission")
        if (
            self.selected_submission is not None
            and self.submission_provenance != self.selected_submission.provenance
        ):
            raise ValueError("submission provenance must match selected submission")
        selected_required = {
            DecisionRecordStatus.SUBMITTED,
            DecisionRecordStatus.ACTION_GATE_REJECTED,
            DecisionRecordStatus.COMMAND_ENCODING_FAILED,
            DecisionRecordStatus.SEND_FAILED,
        }
        selection_forbidden = {
            DecisionRecordStatus.WAIT_NOOP,
            DecisionRecordStatus.POLICY_REJECTED,
            DecisionRecordStatus.SUPERSEDED_BEFORE_SELECTION,
            DecisionRecordStatus.TERMINALLY_DISCARDED,
            DecisionRecordStatus.RECONCILIATION_REJECTED,
        }
        error_forbidden = {
            DecisionRecordStatus.SUBMITTED,
            DecisionRecordStatus.WAIT_NOOP,
        }
        error_required = set(DecisionRecordStatus) - error_forbidden
        if self.record_status in selected_required and self.selected_submission is None:
            raise ValueError("record status requires selected_submission")
        if self.record_status in selection_forbidden and self.selected_submission is not None:
            raise ValueError("record status must not contain selected_submission")
        if self.record_status in error_forbidden and self.fallback_or_error_class is not None:
            raise ValueError("record status must not contain an error class")
        if self.record_status in error_required and self.fallback_or_error_class is None:
            raise ValueError("record status requires an error class")

    def to_payload(self) -> dict[str, Any]:
        return {
            "record_schema_version": self.record_schema_version,
            "record_status": self.record_status.value,
            "run_context_digest": self.run_context_digest,
            "battle_id_digest": self.battle_id_digest,
            "decision_index": self.decision_index,
            "request_identity": dict(_thaw(project_request_identity(self.request_identity))),
            "observed_state_digest": self.observed_state_digest,
            "safe_submission_set_digest": self.safe_submission_set_digest,
            "selected_submission": (
                None
                if self.selected_submission is None
                else dict(_thaw(project_battle_submission(self.selected_submission)))
            ),
            "submission_provenance": (
                None if self.submission_provenance is None else self.submission_provenance.value
            ),
            "fallback_or_error_class": self.fallback_or_error_class,
            "policy_or_arm_id": self.policy_or_arm_id,
            "runtime_and_contract_digests": self.runtime_and_contract_digests.to_dict(),
        }

    @property
    def record_id(self) -> str:
        return derive_record_id(
            self.run_context_digest,
            self.battle_id_digest,
            self.decision_index,
            project_request_identity(self.request_identity),
        )

    @property
    def record_digest(self) -> str:
        return digest_record_envelope(self.record_id, self.to_payload())

    def to_envelope(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "record_digest": self.record_digest,
            "payload": self.to_payload(),
        }

    def canonical_envelope_bytes(self) -> bytes:
        return canonicalize(self.to_envelope())
