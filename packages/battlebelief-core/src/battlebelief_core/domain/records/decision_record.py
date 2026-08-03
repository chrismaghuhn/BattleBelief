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
    evaluation_run_binding_digest: str
    run_scope_digest: str
    battle_id_digest: str
    battle_ordinal: int

    def __post_init__(self) -> None:
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
        value["schema_version"] = 1
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
        _require_digest("observed_state_digest", self.observed_state_digest)
        _require_digest("safe_submission_set_digest", self.safe_submission_set_digest)
        if not self.policy_or_arm_id:
            raise ValueError("policy_or_arm_id must not be empty")
        if self.selected_submission is None and self.submission_provenance is not None:
            raise ValueError("submission provenance requires a selected submission")
        if (
            self.selected_submission is not None
            and self.submission_provenance != self.selected_submission.provenance
        ):
            raise ValueError("submission provenance must match selected submission")

    def to_payload(self) -> dict[str, Any]:
        return {
            "record_schema_version": self.record_schema_version,
            "record_status": self.record_status.value,
            "run_context_digest": self.run_context_digest,
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
