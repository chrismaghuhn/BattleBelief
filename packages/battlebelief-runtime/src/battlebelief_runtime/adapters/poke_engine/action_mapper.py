"""Safe-root and engine-neutral deep action mapping."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal, NoReturn

from battlebelief_core.canonicalization import manifest_digest
from battlebelief_core.domain.actions import (
    ActionKind,
    ActionProvenance,
    BattleSubmission,
    RequestIdentity,
    SafeSubmissionSet,
)
from battlebelief_core.domain.engine_capabilities import CapabilityCatalog, CapabilityId
from battlebelief_core.domain.records.public_projection import battle_submission_digest
from battlebelief_core.domain.search import PreparedRootIdentity, SearchAction

_MOVE_CHOICE = re.compile(r"^[a-z0-9]+(?:-tera)?$")
_SWITCH_CHOICE = re.compile(r"^switch [a-z0-9]+$")


class _ActionMappingError(ValueError):
    def __init__(self, failure_class: str) -> None:
        self.failure_class = failure_class
        super().__init__(failure_class)


def _fail(failure_class: str) -> NoReturn:
    raise _ActionMappingError(failure_class)


@dataclass(frozen=True, slots=True)
class _ActionBinding:
    action: SearchAction
    native_choice: str = field(repr=False)
    submission: BattleSubmission | None = field(default=None, repr=False)


def safe_submissions_from_document(document: Mapping[str, object]) -> SafeSubmissionSet:
    if not isinstance(document, Mapping):
        _fail("missing_field")
    request_value = document.get("request")
    submissions_value = document.get("safe_submissions")
    if not isinstance(request_value, Mapping) or not isinstance(submissions_value, Sequence):
        _fail("missing_field")
    if set(request_value) != {"room_id", "rqid", "request_digest"}:
        _fail("unsupported_mapping")
    room_id = request_value["room_id"]
    rqid = request_value["rqid"]
    request_digest = request_value["request_digest"]
    if type(room_id) is not str or type(rqid) is not int or type(request_digest) is not str:
        _fail("unsupported_mapping")
    submissions: list[BattleSubmission] = []
    for value in submissions_value:
        if not isinstance(value, Mapping):
            _fail("unsupported_mapping")
        kind = value.get("kind")
        try:
            if kind == "move" and set(value) == {"kind", "slot", "move_id", "terastallize"}:
                submissions.append(
                    BattleSubmission(
                        kind=ActionKind.MOVE,
                        provenance=ActionProvenance.EXPLICIT_REQUEST,
                        slot=value["slot"],
                        move_id=value["move_id"],
                        terastallize=value["terastallize"],
                    )
                )
            elif kind == "switch" and set(value) == {"kind", "slot"}:
                submissions.append(
                    BattleSubmission(
                        kind=ActionKind.SWITCH,
                        provenance=ActionProvenance.EXPLICIT_REQUEST,
                        slot=value["slot"],
                    )
                )
            else:
                _fail("unsupported_mapping")
        except (TypeError, ValueError):
            _fail("unsupported_mapping")
    try:
        return SafeSubmissionSet(
            request_identity=RequestIdentity(
                room_id=room_id, rqid=rqid, request_digest=request_digest
            ),
            submissions=tuple(submissions),
        )
    except (TypeError, ValueError):
        _fail("unsupported_mapping")


def _capabilities(catalog: CapabilityCatalog, *values: str) -> tuple[CapabilityId, ...]:
    try:
        return tuple(catalog.id_for(value) for value in sorted(set(values)))
    except ValueError:
        _fail("capability_ambiguity")


def _submission_choice(
    submission: BattleSubmission,
    team_ids: tuple[str, ...],
    active_move_ids: tuple[str, ...],
) -> str:
    if submission.kind is ActionKind.MOVE:
        assert submission.move_id is not None
        assert submission.slot is not None
        if (
            submission.slot > len(active_move_ids)
            or active_move_ids[submission.slot - 1] != submission.move_id
        ):
            _fail("safe_submission_mismatch")
        return submission.move_id + ("-tera" if submission.terastallize else "")
    if submission.kind is ActionKind.SWITCH:
        assert submission.slot is not None
        if submission.slot > len(team_ids):
            _fail("safe_submission_mismatch")
        return f"switch {team_ids[submission.slot - 1]}"
    _fail("unsupported_mapping")


def map_root_actions(
    *,
    safe_set: SafeSubmissionSet,
    root_identity: PreparedRootIdentity,
    native_choices: tuple[str, ...],
    team_ids: tuple[str, ...],
    active_move_ids: tuple[str, ...],
    force_switch: bool,
    catalog: CapabilityCatalog,
) -> tuple[_ActionBinding, ...]:
    if not isinstance(safe_set, SafeSubmissionSet) or not safe_set.submissions:
        _fail("safe_submission_mismatch")
    if len(set(safe_set.submissions)) != len(safe_set.submissions):
        _fail("safe_submission_mismatch")
    bindings: list[_ActionBinding] = []
    for index, submission in enumerate(safe_set.submissions):
        native = _submission_choice(submission, team_ids, active_move_ids)
        if native not in native_choices:
            _fail("safe_submission_mismatch")
        values: tuple[str, ...]
        kind: Literal["move", "switch", "pass"]
        if submission.kind is ActionKind.MOVE:
            kind = "move"
            values = ("gen9.legality.move.selection",)
            if submission.terastallize:
                values += ("gen9.legality.terastallization.activation",)
        else:
            kind = "switch"
            values = (
                "gen9.legality.switch.forced" if force_switch else "gen9.legality.switch.voluntary",
            )
        submission_digest = battle_submission_digest(submission)
        action = SearchAction(
            action_id=manifest_digest(
                {
                    "safe_submission_index": index,
                    "submission_digest": submission_digest,
                }
            ),
            kind=kind,
            required_capabilities=_capabilities(catalog, *values),
            root_submission_index=index,
            root_identity=root_identity,
        )
        bindings.append(_ActionBinding(action=action, native_choice=native, submission=submission))
    if len({binding.native_choice for binding in bindings}) != len(bindings):
        _fail("safe_submission_mismatch")
    return tuple(bindings)


def map_native_actions(
    *,
    native_choices: tuple[str, ...],
    force_switch: bool,
    catalog: CapabilityCatalog,
) -> tuple[_ActionBinding, ...]:
    if not native_choices or len(set(native_choices)) != len(native_choices):
        _fail("malformed_native_result")
    bindings: list[_ActionBinding] = []
    for native in native_choices:
        if type(native) is not str or not native or not native.isascii():
            _fail("unknown_native_choice")
        if native == "No Move":
            kind: Literal["move", "switch", "pass"] = "pass"
            capabilities: tuple[CapabilityId, ...] = ()
        elif _SWITCH_CHOICE.fullmatch(native) is not None:
            kind = "switch"
            capabilities = _capabilities(
                catalog,
                "gen9.legality.switch.forced" if force_switch else "gen9.legality.switch.voluntary",
            )
        elif _MOVE_CHOICE.fullmatch(native) is not None:
            kind = "move"
            values = ["gen9.legality.move.selection"]
            if native.endswith("-tera"):
                values.append("gen9.legality.terastallization.activation")
            capabilities = _capabilities(catalog, *values)
        else:
            _fail("unknown_native_choice")
        action = SearchAction(
            action_id=manifest_digest({"kind": kind, "native_choice": native}),
            kind=kind,
            required_capabilities=capabilities,
        )
        bindings.append(_ActionBinding(action=action, native_choice=native))
    return tuple(bindings)


def binding_for_action(
    bindings: tuple[_ActionBinding, ...], action: SearchAction
) -> _ActionBinding:
    matches = tuple(binding for binding in bindings if binding.action == action)
    if len(matches) != 1:
        _fail("invalid_joint_action")
    return matches[0]


__all__: list[str] = []
