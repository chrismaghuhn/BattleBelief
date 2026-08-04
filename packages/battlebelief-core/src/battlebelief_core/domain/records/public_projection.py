"""Explicit public projections used by deterministic Decision Records."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, cast

from battlebelief_core.canonicalization import canonicalize, manifest_digest
from battlebelief_core.domain.actions.submission import (
    BattleSubmission,
    RequestIdentity,
    SafeSubmissionSet,
)
from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_core.domain.state.pokemon_view import PokemonView
from battlebelief_core.domain.state.side_view import SideView
from battlebelief_core.domain.state.values import EvidenceInterval, HpObservation, PreviewPokemon

PublicValue = Any
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_MAX_SAFE_INTEGER = 9_007_199_254_740_991
_ANNOTATION_TYPES = frozenset({"already", "from", "of", "silent", "still", "upkeep", "wisher"})
_EFFECT_TYPES = frozenset({"ability", "condition", "item", "move"})


@dataclass(frozen=True, slots=True)
class PublicRequestIdentity:
    """Request identity safe to retain in a Decision Record."""

    rqid: int
    request_digest: str

    def __post_init__(self) -> None:
        if type(self.rqid) is not int or not (0 <= self.rqid <= _MAX_SAFE_INTEGER):
            raise ValueError("rqid must be a JCS-safe non-negative integer")
        if not _DIGEST_RE.fullmatch(self.request_digest):
            raise ValueError("request_digest must be a sha256 digest")

    @classmethod
    def from_internal(cls, identity: RequestIdentity) -> PublicRequestIdentity:
        return cls(rqid=identity.rqid, request_digest=identity.request_digest)


def _freeze(value: PublicValue) -> PublicValue:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: PublicValue) -> PublicValue:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def canonical_public_bytes(value: Mapping[str, PublicValue] | PublicValue) -> bytes:
    """Return JCS bytes for an immutable public projection."""

    return canonicalize(_thaw(value))


def _digest(value: Mapping[str, PublicValue]) -> str:
    return manifest_digest(_thaw(value))


def project_request_identity(
    identity: RequestIdentity | PublicRequestIdentity,
) -> Mapping[str, PublicValue]:
    """Project an identity without serializing its room identifier."""

    public_identity = (
        PublicRequestIdentity.from_internal(identity)
        if isinstance(identity, RequestIdentity)
        else identity
    )
    if not isinstance(public_identity, PublicRequestIdentity):
        raise ValueError("identity must be a RequestIdentity or PublicRequestIdentity")

    return cast(
        Mapping[str, PublicValue],
        _freeze(
            {
                "rqid": public_identity.rqid,
                "request_digest": public_identity.request_digest,
            }
        ),
    )


def request_identity_digest(identity: RequestIdentity) -> str:
    return _digest(project_request_identity(identity))


def project_battle_submission(submission: BattleSubmission) -> Mapping[str, PublicValue]:
    return cast(
        Mapping[str, PublicValue],
        _freeze(
            {
                "kind": submission.kind.value,
                "provenance": submission.provenance.value,
                "slot": submission.slot,
                "move_id": submission.move_id,
                "terastallize": submission.terastallize,
                "team_order": list(submission.team_order),
            }
        ),
    )


def battle_submission_digest(submission: BattleSubmission) -> str:
    return _digest(project_battle_submission(submission))


def project_safe_submission_set(safe_set: SafeSubmissionSet) -> Mapping[str, PublicValue]:
    return cast(
        Mapping[str, PublicValue],
        _freeze(
            {
                "request_identity": _thaw(project_request_identity(safe_set.request_identity)),
                # Submission order is semantic: it is a policy tie-break input.
                "submissions": [
                    _thaw(project_battle_submission(item)) for item in safe_set.submissions
                ],
            }
        ),
    )


def safe_submission_set_digest(safe_set: SafeSubmissionSet) -> str:
    return _digest(project_safe_submission_set(safe_set))


def _project_interval(interval: EvidenceInterval) -> dict[str, PublicValue]:
    return {
        "value": interval.value,
        "source_event_index": interval.source_event_index,
        "valid_from": interval.valid_from,
        "valid_until": interval.valid_until,
    }


def _project_hp(hp: HpObservation | None) -> dict[str, PublicValue] | None:
    if hp is None:
        return None
    return {
        "current": hp.current,
        "maximum": hp.maximum,
        "precision": hp.precision.value,
        "fainted": hp.fainted,
    }


def _project_preview(item: PreviewPokemon) -> dict[str, PublicValue]:
    return {"details": item.details, "has_item": item.has_item}


def _project_pokemon(item: PokemonView) -> dict[str, PublicValue]:
    # Nicknames, side/user IDs and the internal switch key are intentionally
    # excluded. The remaining fields represent public observed evidence.
    return {
        "identity_intervals": [_project_interval(value) for value in item.identity_intervals],
        "preview_details": item.preview_details,
        "current_details": item.current_details,
        "active": item.active,
        "hp": _project_hp(item.hp),
        "status": item.status,
        "fainted": item.fainted,
        "revealed_moves": list(item.revealed_moves),
        "item_intervals": [_project_interval(value) for value in item.item_intervals],
        "ability_intervals": [_project_interval(value) for value in item.ability_intervals],
        "tera_type": item.tera_type,
        "boosts": list(item.boosts),
        "volatiles": list(item.volatiles),
        "recharging": item.recharging,
        "transformed": item.transform_target is not None,
    }


def _project_side(side: SideView) -> dict[str, PublicValue]:
    return {
        "side_id": side.side_id,
        "team_size": side.team_size,
        "preview_roster": [_project_preview(item) for item in side.preview_roster],
        "active_slot": side.active_slot,
        "pokemon": [_project_pokemon(item) for item in side.pokemon],
        "side_conditions": [
            {"condition": condition, "count": count} for condition, count in side.side_conditions
        ],
    }


def _winner_projection(state: ObservedState) -> str | None:
    if state.tied:
        return "tie"
    if state.winner is None:
        return None
    winner = _showdown_id(state.winner)
    our_user = _showdown_id(state.our_user_id)
    if winner == our_user:
        return "our_side"
    for side in (state.p1, state.p2):
        if side.user_id is not None and winner == _showdown_id(side.user_id):
            return "our_side" if side.side_id == state.our_side else "opponent_side"
    return None


def _showdown_id(value: str) -> str:
    """Apply the same ASCII ``toID`` normalization as Showdown's parser."""

    return "".join(
        character for character in value.lower() if character.isascii() and character.isalnum()
    )


def _project_visible_evidence(evidence: Any) -> dict[str, PublicValue]:
    """Retain structured public effects while excluding raw identifiers."""

    projection: dict[str, PublicValue] = {
        "event_index": evidence.event_index,
        "kind": evidence.kind,
        "side_id": evidence.side_id,
        "slot": evidence.slot,
    }
    if evidence.kind == "hitcount":
        try:
            hit_count = int(evidence.effect or "")
        except ValueError:
            hit_count = None
        if hit_count is not None and 0 <= hit_count <= _MAX_SAFE_INTEGER:
            projection["hit_count"] = hit_count
    elif evidence.kind in {"activate", "block", "prepare", "fieldactivate"}:
        effect = evidence.effect or ""
        if ":" in effect:
            effect_type, effect_value = effect.split(":", 1)
            normalized_type = _showdown_id(effect_type)
            normalized_value = _showdown_id(effect_value.strip())
            if normalized_type in _EFFECT_TYPES and normalized_value:
                projection["effect_type"] = normalized_type
                projection["effect_id"] = normalized_value
    if evidence.annotations:
        projection["annotations"] = [_project_annotation(value) for value in evidence.annotations]
    return projection


def _project_annotation(annotation: str) -> dict[str, PublicValue]:
    """Project an annotation label and optional side/slot without its nickname."""

    if not annotation.startswith("[") or "]" not in annotation:
        return {"type": "unknown"}
    label, remainder = annotation[1:].split("]", 1)
    normalized_label = _showdown_id(label)
    projection: dict[str, PublicValue] = {
        "type": normalized_label if normalized_label in _ANNOTATION_TYPES else "unknown"
    }
    target = remainder.strip()
    if ": " in target:
        position = target.split(": ", 1)[0]
        if len(position) == 3 and position[:2] in {"p1", "p2"} and position[2] == "a":
            projection["side_id"] = position[:2]
            projection["slot"] = 1
    return projection


def project_observed_state(state: ObservedState) -> Mapping[str, PublicValue]:
    """Project only the documented public battle observation fields."""

    return cast(
        Mapping[str, PublicValue],
        _freeze(
            {
                "event_index": state.event_index,
                "room_initialized": state.room_initialized,
                "generation": state.generation,
                "game_type": state.game_type,
                "tier": state.tier,
                "rated": state.rated,
                "rules": list(state.rules),
                "turn": state.turn,
                "battle_started": state.battle_started,
                "team_preview_started": state.team_preview_started,
                "winner": _winner_projection(state),
                "tied": state.tied,
                "our_side": state.our_side,
                "p1": _project_side(state.p1),
                "p2": _project_side(state.p2),
                "weather": state.weather,
                "field_conditions": list(state.field_conditions),
                "visible_evidence": [
                    _project_visible_evidence(evidence) for evidence in state.visible_evidence
                ],
                "ignored_display_count": state.ignored_display_count,
            }
        ),
    )


def observed_state_digest(state: ObservedState) -> str:
    return _digest(project_observed_state(state))
