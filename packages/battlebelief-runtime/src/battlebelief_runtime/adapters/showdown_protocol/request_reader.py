from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass
from typing import Any, cast

from battlebelief_core.domain.actions.decision_request import DecisionRequest, RequestKind
from battlebelief_core.domain.actions.submission import (
    ActionKind,
    ActionProvenance,
    BattleSubmission,
    RequestIdentity,
    SafeSubmissionSet,
)
from battlebelief_runtime.errors.protocol import (
    MalformedProtocolMessage,
    RequestStateReconciliationMismatch,
)

_MIN_TEAM_SIZE = 1
_MAX_TEAM_SIZE = 6


@dataclass(frozen=True, slots=True)
class _RequestPokemon:
    ident: str
    details: str
    condition: str
    active: bool
    reviving: bool


@dataclass(frozen=True, slots=True)
class _RequestMove:
    move_id: str
    disabled: bool


@dataclass(frozen=True, slots=True)
class _ActiveRequest:
    moves: tuple[_RequestMove, ...]
    can_terastallize: str
    trapped: bool
    maybe_trapped: bool
    maybe_disabled: bool
    maybe_locked: bool


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------


def _canonical_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_rqid(payload: dict[str, Any]) -> int:
    if "rqid" not in payload:
        raise RequestStateReconciliationMismatch("request missing rqid")
    rqid = payload["rqid"]
    if not isinstance(rqid, int) or isinstance(rqid, bool) or rqid < 0:
        raise RequestStateReconciliationMismatch(f"invalid rqid: {rqid!r}")
    return rqid


def _require_object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MalformedProtocolMessage(f"{context} must be an object")
    return cast(dict[str, Any], value)


def _require_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or value == "":
        raise MalformedProtocolMessage(f"{context} must be a non-empty string")
    return value


def _require_string_value(value: Any, context: str) -> str:
    if not isinstance(value, str):
        raise MalformedProtocolMessage(f"{context} must be a string")
    return value


def _require_bool(value: Any, context: str) -> bool:
    if not isinstance(value, bool):
        raise MalformedProtocolMessage(f"{context} must be a boolean")
    return value


def _optional_bool(payload: dict[str, Any], key: str, default: bool = False) -> bool:
    if key not in payload:
        return default
    return _require_bool(payload[key], key)


def _require_string_list(value: Any, context: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise MalformedProtocolMessage(f"{context} must be a list")
    strings: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise MalformedProtocolMessage(f"{context}[{index}] must be a string")
        strings.append(item)
    return tuple(strings)


def _parse_force_switch(payload: dict[str, Any]) -> tuple[bool, ...] | None:
    if "forceSwitch" not in payload:
        return None
    value = payload["forceSwitch"]
    if not isinstance(value, list) or len(value) != 1:
        raise MalformedProtocolMessage("forceSwitch must be a singles boolean array")
    return (_require_bool(value[0], "forceSwitch[0]"),)


def _pokemon_fainted(condition: str) -> bool:
    return condition.rstrip().endswith(" fnt") or condition.strip() == "0 fnt"


def _nickname_from_ident(ident: str) -> str:
    if ": " not in ident:
        raise MalformedProtocolMessage(f"invalid pokemon ident: {ident!r}")
    _, nickname = ident.split(": ", 1)
    if nickname == "":
        raise MalformedProtocolMessage(f"invalid pokemon ident: {ident!r}")
    return nickname


def _default_submission() -> BattleSubmission:
    return BattleSubmission(kind=ActionKind.DEFAULT, provenance=ActionProvenance.SERVER_DEFAULT)


def _parse_request_pokemon(side_id: str, value: Any, index: int) -> _RequestPokemon:
    entry = _require_object(value, f"side.pokemon[{index}]")
    ident = _require_string(entry.get("ident"), f"side.pokemon[{index}].ident")
    ident_side, _, nickname = ident.partition(": ")
    if ident_side != side_id or nickname == "":
        raise MalformedProtocolMessage(f"invalid pokemon ident: {ident!r}")
    details = _require_string(entry.get("details"), f"side.pokemon[{index}].details")
    condition = _require_string(entry.get("condition"), f"side.pokemon[{index}].condition")
    active = _require_bool(entry.get("active"), f"side.pokemon[{index}].active")
    reviving = (
        _require_bool(entry["reviving"], f"side.pokemon[{index}].reviving")
        if "reviving" in entry
        else False
    )
    for key in ("item", "ability"):
        if key in entry:
            _require_string_value(entry[key], f"side.pokemon[{index}].{key}")
    if "moves" in entry:
        _require_string_list(entry["moves"], f"side.pokemon[{index}].moves")
    return _RequestPokemon(
        ident=ident,
        details=details,
        condition=condition,
        active=active,
        reviving=reviving,
    )


def _parse_side(value: Any) -> tuple[str, tuple[_RequestPokemon, ...]]:
    side = _require_object(value, "side")
    side_id = _require_string(side.get("id"), "side.id")
    if side_id not in {"p1", "p2"}:
        raise MalformedProtocolMessage(f"invalid side.id: {side_id!r}")
    if "name" in side:
        _require_string(side["name"], "side.name")
    pokemon_value = side.get("pokemon")
    if not isinstance(pokemon_value, list):
        raise MalformedProtocolMessage("side.pokemon must be a list")
    if not _MIN_TEAM_SIZE <= len(pokemon_value) <= _MAX_TEAM_SIZE:
        raise MalformedProtocolMessage("side.pokemon must contain 1-6 entries")
    pokemon = tuple(
        _parse_request_pokemon(side_id, entry, index) for index, entry in enumerate(pokemon_value)
    )
    if sum(member.active for member in pokemon) > 1:
        raise MalformedProtocolMessage("Singles request cannot contain multiple active pokemon")
    return side_id, pokemon


def _validate_active_shape(value: Any) -> dict[str, Any]:
    if not isinstance(value, list) or len(value) != 1:
        raise MalformedProtocolMessage("active must be a singles array with one entry")
    return _require_object(value[0], "active[0]")


def _parse_active_request(payload: dict[str, Any]) -> _ActiveRequest:
    active_info = _validate_active_shape(payload.get("active"))
    moves_value = active_info.get("moves")
    if not isinstance(moves_value, list):
        raise MalformedProtocolMessage("active[0].moves must be a list")
    if not 1 <= len(moves_value) <= 4:
        raise MalformedProtocolMessage("active[0].moves must contain 1-4 entries")
    moves: list[_RequestMove] = []
    for index, value in enumerate(moves_value):
        move = _require_object(value, f"active[0].moves[{index}]")
        move_id = _require_string(move.get("id"), f"active[0].moves[{index}].id")
        raw_disabled = move.get("disabled", False)
        if isinstance(raw_disabled, bool):
            disabled = raw_disabled
        elif isinstance(raw_disabled, str):
            disabled = bool(raw_disabled)
        else:
            raise MalformedProtocolMessage(
                f"active[0].moves[{index}].disabled must be a boolean or string"
            )
        if "move" in move:
            _require_string(move["move"], f"active[0].moves[{index}].move")
        if "target" in move:
            _require_string(move["target"], f"active[0].moves[{index}].target")
        for key in ("pp", "maxpp"):
            if key in move and (
                not isinstance(move[key], int) or isinstance(move[key], bool) or move[key] < 0
            ):
                raise MalformedProtocolMessage(
                    f"active[0].moves[{index}].{key} must be a non-negative integer"
                )
        moves.append(_RequestMove(move_id=move_id, disabled=disabled))

    can_terastallize = active_info.get("canTerastallize", "")
    if not isinstance(can_terastallize, str):
        raise MalformedProtocolMessage("active[0].canTerastallize must be a string")
    return _ActiveRequest(
        moves=tuple(moves),
        can_terastallize=can_terastallize,
        trapped=_optional_bool(active_info, "trapped"),
        maybe_trapped=_optional_bool(active_info, "maybeTrapped"),
        maybe_disabled=_optional_bool(active_info, "maybeDisabled"),
        maybe_locked=_optional_bool(active_info, "maybeLocked"),
    )


# ---------------------------------------------------------------------------
# reader
# ---------------------------------------------------------------------------


def read_request(room_id: str, payload: str) -> DecisionRequest:
    """Parse one `|request|` payload into an immutable safe action request.

    Detection order is binding: wait -> teamPreview -> active member with
    reviving=true -> forceSwitch -> normal move request.
    """
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise MalformedProtocolMessage(f"invalid request json: {exc}") from exc
    if not isinstance(data, dict):
        raise MalformedProtocolMessage("request json must be an object")
    data = cast(dict[str, Any], data)

    rqid = _require_rqid(data)
    digest = _canonical_digest(data)
    identity = RequestIdentity(room_id=room_id, rqid=rqid, request_digest=digest)

    wait = _optional_bool(data, "wait")
    team_preview = _optional_bool(data, "teamPreview")
    update = _optional_bool(data, "update")
    force_switch = _parse_force_switch(data)
    if "active" in data:
        _validate_active_shape(data["active"])

    side_id, pokemon_list = _parse_side(data.get("side"))
    active_pv = next((pokemon for pokemon in pokemon_list if pokemon.active), None)
    active_identity = _nickname_from_ident(active_pv.ident) if active_pv else None

    if wait:
        return DecisionRequest(
            identity=identity,
            kind=RequestKind.WAIT,
            side_id=side_id,
            team_member_count=len(pokemon_list),
            active_identity=None,
            safe_submissions=SafeSubmissionSet(request_identity=identity, submissions=()),
            is_update=False,
        )

    if team_preview:
        return _read_team_preview(identity, side_id, pokemon_list, data)

    if active_pv is not None and active_pv.reviving:
        return _read_revival(identity, side_id, pokemon_list, active_identity, update)

    if force_switch is not None and force_switch[0]:
        return _read_forced_switch(identity, side_id, pokemon_list, active_identity, update)

    return _read_normal_move(identity, side_id, pokemon_list, active_identity, data, update)


def _read_team_preview(
    identity: RequestIdentity,
    side_id: str,
    pokemon_list: tuple[_RequestPokemon, ...],
    data: dict[str, Any],
) -> DecisionRequest:
    team_size = len(pokemon_list)
    max_chosen = data.get("maxChosenTeamSize", team_size)
    if not isinstance(max_chosen, int) or isinstance(max_chosen, bool) or max_chosen < 1:
        raise MalformedProtocolMessage(f"invalid maxChosenTeamSize: {max_chosen!r}")
    if max_chosen != team_size:
        raise RequestStateReconciliationMismatch(
            f"Bring-N team preview is outside the Gen9 OU scope: {max_chosen} of {team_size}"
        )
    permutations = tuple(
        BattleSubmission(
            kind=ActionKind.TEAM, provenance=ActionProvenance.EXPLICIT_REQUEST, team_order=perm
        )
        for perm in itertools.permutations(range(1, team_size + 1))
    )
    submissions = (*permutations, _default_submission())
    return DecisionRequest(
        identity=identity,
        kind=RequestKind.TEAM_PREVIEW,
        side_id=side_id,
        team_member_count=team_size,
        active_identity=None,
        safe_submissions=SafeSubmissionSet(request_identity=identity, submissions=submissions),
        is_update=False,
    )


def _read_revival(
    identity: RequestIdentity,
    side_id: str,
    pokemon_list: tuple[_RequestPokemon, ...],
    active_identity: str | None,
    is_update: bool,
) -> DecisionRequest:
    candidates = [
        slot
        for slot, pokemon in enumerate(pokemon_list, start=1)
        if not pokemon.active and _pokemon_fainted(pokemon.condition)
    ]
    submissions = (
        *(
            BattleSubmission(
                kind=ActionKind.REVIVE, provenance=ActionProvenance.EXPLICIT_REQUEST, slot=slot
            )
            for slot in candidates
        ),
        _default_submission(),
    )
    return DecisionRequest(
        identity=identity,
        kind=RequestKind.REVIVAL,
        side_id=side_id,
        team_member_count=len(pokemon_list),
        active_identity=active_identity,
        safe_submissions=SafeSubmissionSet(request_identity=identity, submissions=submissions),
        is_update=is_update,
    )


def _read_forced_switch(
    identity: RequestIdentity,
    side_id: str,
    pokemon_list: tuple[_RequestPokemon, ...],
    active_identity: str | None,
    is_update: bool,
) -> DecisionRequest:
    candidates = [
        slot
        for slot, pokemon in enumerate(pokemon_list, start=1)
        if not pokemon.active and not _pokemon_fainted(pokemon.condition)
    ]
    submissions = (
        *(
            BattleSubmission(
                kind=ActionKind.SWITCH, provenance=ActionProvenance.EXPLICIT_REQUEST, slot=slot
            )
            for slot in candidates
        ),
        _default_submission(),
    )
    return DecisionRequest(
        identity=identity,
        kind=RequestKind.FORCED_SWITCH,
        side_id=side_id,
        team_member_count=len(pokemon_list),
        active_identity=active_identity,
        safe_submissions=SafeSubmissionSet(request_identity=identity, submissions=submissions),
        is_update=is_update,
    )


def _read_normal_move(
    identity: RequestIdentity,
    side_id: str,
    pokemon_list: tuple[_RequestPokemon, ...],
    active_identity: str | None,
    data: dict[str, Any],
    is_update: bool,
) -> DecisionRequest:
    active_request = _parse_active_request(data)

    if active_request.maybe_disabled or active_request.maybe_locked:
        submissions: tuple[BattleSubmission, ...] = (_default_submission(),)
    else:
        can_tera = active_request.can_terastallize != ""
        move_submissions: list[BattleSubmission] = []
        for index, move in enumerate(active_request.moves, start=1):
            if move.disabled:
                continue
            move_submissions.append(
                BattleSubmission(
                    kind=ActionKind.MOVE,
                    provenance=ActionProvenance.EXPLICIT_REQUEST,
                    slot=index,
                    move_id=move.move_id,
                )
            )
            if can_tera:
                move_submissions.append(
                    BattleSubmission(
                        kind=ActionKind.MOVE,
                        provenance=ActionProvenance.EXPLICIT_REQUEST,
                        slot=index,
                        move_id=move.move_id,
                        terastallize=True,
                    )
                )

        switch_submissions: list[BattleSubmission] = []
        trapped = active_request.trapped or active_request.maybe_trapped
        if not trapped:
            switch_submissions = [
                BattleSubmission(
                    kind=ActionKind.SWITCH, provenance=ActionProvenance.EXPLICIT_REQUEST, slot=slot
                )
                for slot, pokemon in enumerate(pokemon_list, start=1)
                if not pokemon.active and not _pokemon_fainted(pokemon.condition)
            ]

        submissions = tuple(move_submissions) + tuple(switch_submissions) + (_default_submission(),)

    return DecisionRequest(
        identity=identity,
        kind=RequestKind.MOVE,
        side_id=side_id,
        team_member_count=len(pokemon_list),
        active_identity=active_identity,
        safe_submissions=SafeSubmissionSet(request_identity=identity, submissions=submissions),
        is_update=is_update,
    )
