"""Immutable Decision Records and their non-circular deterministic identities."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from battlebelief_core.canonicalization import canonicalize, manifest_digest
from battlebelief_core.domain.actions.submission import (
    ActionProvenance,
    BattleSubmission,
    RequestIdentity,
)
from battlebelief_core.domain.records.public_projection import (
    PublicRequestIdentity,
    _thaw,
    project_battle_submission,
    project_request_identity,
)

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ARM_ID_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
_ERROR_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MAX_SAFE_INTEGER = 9_007_199_254_740_991


def _require_safe_integer(name: str, value: object) -> None:
    if type(value) is not int or not (0 <= value <= _MAX_SAFE_INTEGER):
        raise ValueError(f"{name} must be a JCS-safe non-negative integer")


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
    FRESHNESS_INVALIDATED = "freshness_invalidated"


class DecisionRecordErrorCode(StrEnum):
    """Versioned, public error taxonomy for terminal Decision Records."""

    NO_LEGAL_ACTION_AVAILABLE = "no_legal_action_available"
    LOCAL_ACTION_GATE_REJECTION = "local_action_gate_rejection"
    COMMAND_ENCODING_FAILED = "command_encoding_failed"
    SEND_FAILED = "send_failed"
    SERVER_INVALID_CHOICE = "server_invalid_choice"
    SERVER_UNAVAILABLE_CHOICE = "server_unavailable_choice"
    REQUEST_STATE_RECONCILIATION_MISMATCH = "request_state_reconciliation_mismatch"
    STALE_RQID = "stale_rqid"
    DISCONNECT = "disconnect"
    TRANSPORT_TIMEOUT = "transport_timeout"
    TIMER_OR_FORFEIT = "timer_or_forfeit"
    UNKNOWN_PROTOCOL_EVENT = "unknown_protocol_event"
    MALFORMED_PROTOCOL_MESSAGE = "malformed_protocol_message"
    REDUCER_INVARIANT_FAILURE = "reducer_invariant_failure"


STATUS_ERROR_CODES = MappingProxyType(
    {
        DecisionRecordStatus.POLICY_REJECTED: frozenset(
            {DecisionRecordErrorCode.NO_LEGAL_ACTION_AVAILABLE}
        ),
        DecisionRecordStatus.ACTION_GATE_REJECTED: frozenset(
            {DecisionRecordErrorCode.LOCAL_ACTION_GATE_REJECTION}
        ),
        DecisionRecordStatus.COMMAND_ENCODING_FAILED: frozenset(
            {DecisionRecordErrorCode.COMMAND_ENCODING_FAILED}
        ),
        DecisionRecordStatus.SEND_FAILED: frozenset(
            {
                DecisionRecordErrorCode.SEND_FAILED,
                DecisionRecordErrorCode.SERVER_INVALID_CHOICE,
                DecisionRecordErrorCode.SERVER_UNAVAILABLE_CHOICE,
            }
        ),
        DecisionRecordStatus.SESSION_ABORTED: frozenset(
            {
                DecisionRecordErrorCode.DISCONNECT,
                DecisionRecordErrorCode.TRANSPORT_TIMEOUT,
                DecisionRecordErrorCode.TIMER_OR_FORFEIT,
                DecisionRecordErrorCode.UNKNOWN_PROTOCOL_EVENT,
                DecisionRecordErrorCode.MALFORMED_PROTOCOL_MESSAGE,
                DecisionRecordErrorCode.REDUCER_INVARIANT_FAILURE,
            }
        ),
        DecisionRecordStatus.RECONCILIATION_REJECTED: frozenset(
            {
                DecisionRecordErrorCode.REQUEST_STATE_RECONCILIATION_MISMATCH,
                DecisionRecordErrorCode.STALE_RQID,
            }
        ),
    }
)


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
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("unsupported measurement-run schema version")
        for name, value in (
            ("evaluation_run_binding_digest", self.evaluation_run_binding_digest),
            ("run_scope_digest", self.run_scope_digest),
            ("battle_id_digest", self.battle_id_digest),
        ):
            _require_digest(name, value)
        _require_safe_integer("battle_ordinal", self.battle_ordinal)

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
class ResolvedDecisionRecordBinding:
    """Resolved provenance identities from one immutable evaluation binding."""

    evaluation_run_binding_digest: str
    registration_digest: str
    arm_binding_digest: str
    schedule_digest: str
    budget_profile_digest: str
    seed_family_digest: str
    arm_id: str
    runtime_and_contract_digests: RuntimeAndContractDigests

    def __post_init__(self) -> None:
        for name, value in (
            ("evaluation_run_binding_digest", self.evaluation_run_binding_digest),
            ("registration_digest", self.registration_digest),
            ("arm_binding_digest", self.arm_binding_digest),
            ("schedule_digest", self.schedule_digest),
            ("budget_profile_digest", self.budget_profile_digest),
            ("seed_family_digest", self.seed_family_digest),
        ):
            _require_digest(name, value)
        if (
            type(self.arm_id) is not str
            or len(self.arm_id) > 128
            or not _ARM_ID_RE.fullmatch(self.arm_id)
        ):
            raise ValueError("arm_id must be a valid arm ID")


@dataclass(frozen=True, slots=True)
class MeasurementRunContext:
    payload: RunContextPayload
    run_context_digest: str
    run_scope: RunScopePayload = field(repr=False, compare=False)
    resolved_binding: ResolvedDecisionRecordBinding | None = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        _require_digest("run_context_digest", self.run_context_digest)
        expected = manifest_digest(self.payload.to_dict())
        if self.run_context_digest != expected:
            raise ValueError("run_context_digest does not match payload")
        if self.resolved_binding is None:
            raise ValueError("run context has no resolved binding")
        if self.payload.evaluation_run_binding_digest != (
            self.resolved_binding.evaluation_run_binding_digest
        ):
            raise ValueError("run context does not match resolved evaluation binding")
        if derive_run_scope_digest(self.run_scope) != self.payload.run_scope_digest:
            raise ValueError("run context scope does not match its digest")
        expected_battle_id = derive_battle_id_digest(
            self.payload.run_scope_digest,
            self.run_scope.schedule_row_id,
            self.payload.battle_ordinal,
        )
        if self.payload.battle_id_digest != expected_battle_id:
            raise ValueError("run context battle ID does not match its scope")
        expected_scope = {
            "registration_digest": self.resolved_binding.registration_digest,
            "arm_binding_digest": self.resolved_binding.arm_binding_digest,
            "schedule_digest": self.resolved_binding.schedule_digest,
            "budget_profile_digest": self.resolved_binding.budget_profile_digest,
            "seed_family_digest": self.resolved_binding.seed_family_digest,
            "runtime_digest": self.resolved_binding.runtime_and_contract_digests.runtime_digest,
            "contract_set_digest": self.resolved_binding.runtime_and_contract_digests.contract_set_digest,
        }
        for field_name, expected_value in expected_scope.items():
            if getattr(self.run_scope, field_name) != expected_value:
                raise ValueError(f"run context {field_name} does not match binding")

    def to_dict(self) -> dict[str, object]:
        value = self.payload.to_dict()
        value["run_context_digest"] = self.run_context_digest
        return value

    @classmethod
    def create(
        cls,
        *,
        resolved_binding: ResolvedDecisionRecordBinding,
        run_scope: RunScopePayload,
        battle_ordinal: int,
    ) -> MeasurementRunContext:
        run_scope_digest = derive_run_scope_digest(run_scope)
        expected_scope = {
            "registration_digest": resolved_binding.registration_digest,
            "arm_binding_digest": resolved_binding.arm_binding_digest,
            "schedule_digest": resolved_binding.schedule_digest,
            "budget_profile_digest": resolved_binding.budget_profile_digest,
            "seed_family_digest": resolved_binding.seed_family_digest,
            "runtime_digest": resolved_binding.runtime_and_contract_digests.runtime_digest,
            "contract_set_digest": resolved_binding.runtime_and_contract_digests.contract_set_digest,
        }
        for field_name, expected_value in expected_scope.items():
            if getattr(run_scope, field_name) != expected_value:
                raise ValueError(f"run scope {field_name} does not match resolved binding")
        battle_id_digest = derive_battle_id_digest(
            run_scope_digest, run_scope.schedule_row_id, battle_ordinal
        )
        payload = RunContextPayload(
            schema_version=1,
            evaluation_run_binding_digest=resolved_binding.evaluation_run_binding_digest,
            run_scope_digest=run_scope_digest,
            battle_id_digest=battle_id_digest,
            battle_ordinal=battle_ordinal,
        )
        return cls(
            payload=payload,
            run_context_digest=manifest_digest(payload.to_dict()),
            run_scope=run_scope,
            resolved_binding=resolved_binding,
        )


def derive_run_scope_digest(run_scope: RunScopePayload) -> str:
    """Hash only the non-circular, canonical run-scope payload."""

    return manifest_digest(run_scope.to_dict())


def derive_battle_id_digest(
    run_scope_digest: str, schedule_row_id: str, battle_ordinal: int
) -> str:
    _require_safe_integer("battle_ordinal", battle_ordinal)
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
    _require_safe_integer("decision_index", decision_index)
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


@dataclass(frozen=True, slots=True, init=False)
class DecisionRecord:
    record_schema_version: int
    record_status: DecisionRecordStatus
    run_context_digest: str
    battle_id_digest: str
    decision_index: int
    request_identity: PublicRequestIdentity
    observed_state_digest: str
    safe_submission_set_digest: str
    selected_submission: BattleSubmission | None
    submission_provenance: ActionProvenance | None
    fallback_or_error_class: DecisionRecordErrorCode | None
    policy_or_arm_id: str
    runtime_and_contract_digests: RuntimeAndContractDigests
    _run_context: MeasurementRunContext = field(repr=False, compare=False)
    _resolved_binding: ResolvedDecisionRecordBinding = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        record_schema_version: int,
        record_status: DecisionRecordStatus,
        run_context: MeasurementRunContext,
        resolved_binding: ResolvedDecisionRecordBinding,
        decision_index: int,
        request_identity: RequestIdentity | PublicRequestIdentity,
        observed_state_digest: str,
        safe_submission_set_digest: str,
        selected_submission: BattleSubmission | None,
        submission_provenance: ActionProvenance | None,
        fallback_or_error_class: str | DecisionRecordErrorCode | None,
    ) -> None:
        context_binding = run_context.resolved_binding
        if context_binding is None:
            raise ValueError("run context has no resolved binding")
        if context_binding != resolved_binding:
            raise ValueError("record binding does not match resolved run context")
        object.__setattr__(self, "record_schema_version", record_schema_version)
        object.__setattr__(self, "record_status", record_status)
        object.__setattr__(self, "run_context_digest", run_context.run_context_digest)
        object.__setattr__(self, "battle_id_digest", run_context.payload.battle_id_digest)
        object.__setattr__(self, "decision_index", decision_index)
        object.__setattr__(self, "request_identity", request_identity)
        object.__setattr__(self, "observed_state_digest", observed_state_digest)
        object.__setattr__(self, "safe_submission_set_digest", safe_submission_set_digest)
        object.__setattr__(self, "selected_submission", selected_submission)
        object.__setattr__(self, "submission_provenance", submission_provenance)
        object.__setattr__(self, "fallback_or_error_class", fallback_or_error_class)
        object.__setattr__(self, "policy_or_arm_id", resolved_binding.arm_id)
        object.__setattr__(
            self,
            "runtime_and_contract_digests",
            resolved_binding.runtime_and_contract_digests,
        )
        object.__setattr__(self, "_run_context", run_context)
        object.__setattr__(self, "_resolved_binding", resolved_binding)
        self.__post_init__()

    @classmethod
    def create(cls, **kwargs: Any) -> DecisionRecord:
        return cls(**kwargs)

    def with_updates(self, **changes: Any) -> DecisionRecord:
        allowed = {
            "record_schema_version",
            "record_status",
            "decision_index",
            "request_identity",
            "observed_state_digest",
            "safe_submission_set_digest",
            "selected_submission",
            "submission_provenance",
            "fallback_or_error_class",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise TypeError(f"unsupported DecisionRecord updates: {sorted(unknown)}")
        values = {name: getattr(self, name) for name in allowed}
        values.update(changes)
        return type(self)(
            **values,
            run_context=self._run_context,
            resolved_binding=self._resolved_binding,
        )

    def __post_init__(self) -> None:
        if type(self.record_schema_version) is not int or self.record_schema_version != 1:
            raise ValueError("unsupported Decision-Record schema version")
        _require_safe_integer("decision_index", self.decision_index)
        if isinstance(self.request_identity, RequestIdentity):
            object.__setattr__(
                self,
                "request_identity",
                PublicRequestIdentity.from_internal(self.request_identity),
            )
        elif not isinstance(self.request_identity, PublicRequestIdentity):
            raise ValueError("request_identity must be a public request identity")
        if not isinstance(self.record_status, DecisionRecordStatus):
            raise ValueError("record_status must be a DecisionRecordStatus")
        if self.submission_provenance is not None and not isinstance(
            self.submission_provenance, ActionProvenance
        ):
            raise ValueError("submission_provenance must be an ActionProvenance")
        _require_digest("run_context_digest", self.run_context_digest)
        _require_digest("battle_id_digest", self.battle_id_digest)
        _require_digest("request_digest", self.request_identity.request_digest)
        _require_digest("observed_state_digest", self.observed_state_digest)
        _require_digest("safe_submission_set_digest", self.safe_submission_set_digest)
        if type(self.policy_or_arm_id) is not str or not _ARM_ID_RE.fullmatch(
            self.policy_or_arm_id
        ):
            raise ValueError("policy_or_arm_id must be a valid arm ID")
        if self.fallback_or_error_class is not None:
            if not isinstance(self.fallback_or_error_class, str) or not _ERROR_CODE_RE.fullmatch(
                self.fallback_or_error_class
            ):
                raise ValueError("fallback_or_error_class must be a stable code")
            try:
                error_code = DecisionRecordErrorCode(self.fallback_or_error_class)
            except ValueError as exc:
                raise ValueError("fallback_or_error_class is not an allowed code") from exc
            object.__setattr__(self, "fallback_or_error_class", error_code)
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
            DecisionRecordStatus.FRESHNESS_INVALIDATED,
        }
        error_forbidden = {
            DecisionRecordStatus.SUBMITTED,
            DecisionRecordStatus.WAIT_NOOP,
            DecisionRecordStatus.SUPERSEDED_BEFORE_SELECTION,
            DecisionRecordStatus.TERMINALLY_DISCARDED,
            DecisionRecordStatus.FRESHNESS_INVALIDATED,
        }
        error_required = set(STATUS_ERROR_CODES)
        if self.record_status in selected_required and self.selected_submission is None:
            raise ValueError("record status requires selected_submission")
        if self.record_status in selection_forbidden and self.selected_submission is not None:
            raise ValueError("record status must not contain selected_submission")
        if self.record_status in error_forbidden and self.fallback_or_error_class is not None:
            raise ValueError("record status must not contain an error class")
        if self.record_status in error_required and self.fallback_or_error_class is None:
            raise ValueError("record status requires an error class")
        if self.record_status in STATUS_ERROR_CODES and (
            self.fallback_or_error_class not in STATUS_ERROR_CODES[self.record_status]
        ):
            raise ValueError("error class is not valid for record status")

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
            "fallback_or_error_class": (
                None if self.fallback_or_error_class is None else self.fallback_or_error_class.value
            ),
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
