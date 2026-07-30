from __future__ import annotations

import hashlib
import itertools
import json
from typing import Any

from battlebelief_core.domain.actions.decision_request import DecisionRequest, RequestKind
from battlebelief_core.domain.actions.submission import (
    ActionKind,
    ActionProvenance,
    BattleSubmission,
    RequestIdentity,
    SafeSubmissionSet,
)
from battlebelief_runtime.errors.protocol import MalformedProtocolMessage

# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------


def _canonical_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_rqid(payload: dict[str, Any]) -> int:
    if "rqid" not in payload:
        raise MalformedProtocolMessage("request missing rqid")
    rqid = payload["rqid"]
    if not isinstance(rqid, int) or isinstance(rqid, bool) or rqid < 0:
        raise MalformedProtocolMessage(f"invalid rqid: {rqid!r}")
    return rqid


def _pokemon_fainted(condition: str) -> bool:
    return condition.rstrip().endswith(" fnt") or condition.strip() == "0 fnt"


def _nickname_from_ident(ident: str) -> str:
    if ": " not in ident:
        raise MalformedProtocolMessage(f"invalid pokemon ident: {ident!r}")
    return ident.split(": ", 1)[1]


def _default_submission() -> BattleSubmission:
    return BattleSubmission(kind=ActionKind.DEFAULT, provenance=ActionProvenance.SERVER_DEFAULT)


def _require_pokemon_list(side: Any) -> list[dict[str, Any]]:
    if not isinstance(side, dict) or "pokemon" not in side:
        raise MalformedProtocolMessage("request missing side.pokemon")
    pokemon_list = side["pokemon"]
    if not isinstance(pokemon_list, list):
        raise MalformedProtocolMessage("side.pokemon must be a list")
    for entry in pokemon_list:
        if not isinstance(entry, dict):
            raise MalformedProtocolMessage("side.pokemon entries must be objects")
    return pokemon_list


# ---------------------------------------------------------------------------
# reader
# ---------------------------------------------------------------------------


def read_request(room_id: str, payload: str) -> DecisionRequest:
    """Parse a single `|request|` JSON payload into an immutable
    DecisionRequest with its derived SafeSubmissionSet.

    Detection order is binding: wait -> teamPreview -> active member with
    reviving=true -> forceSwitch -> normal move request.
    """
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise MalformedProtocolMessage(f"invalid request json: {exc}") from exc
    if not isinstance(data, dict):
        raise MalformedProtocolMessage("request json must be an object")

    rqid = _require_rqid(data)
    digest = _canonical_digest(data)
    identity = RequestIdentity(room_id=room_id, rqid=rqid, request_digest=digest)

    if data.get("wait") is True:
        return DecisionRequest(
            identity=identity,
            kind=RequestKind.WAIT,
            side_id=_side_id_or_empty(data),
            team_member_count=_team_member_count(data),
            active_identity=None,
            safe_submissions=SafeSubmissionSet(request_identity=identity, submissions=()),
            is_update=False,
        )

    side = data.get("side")
    if not isinstance(side, dict) or "id" not in side:
        raise MalformedProtocolMessage("request missing side.id")
    side_id = side["id"]
    pokemon_list = _require_pokemon_list(side)

    if data.get("teamPreview") is True:
        return _read_team_preview(identity, side_id, pokemon_list, data)

    active_pv = next((p for p in pokemon_list if p.get("active")), None)
    active_identity = _nickname_from_ident(active_pv["ident"]) if active_pv else None

    if active_pv is not None and active_pv.get("reviving") is True:
        return _read_revival(identity, side_id, pokemon_list, active_identity)

    if "forceSwitch" in data:
        return _read_forced_switch(identity, side_id, pokemon_list, active_identity)

    return _read_normal_move(identity, side_id, pokemon_list, active_identity, data)


def _side_id_or_empty(data: dict[str, Any]) -> str:
    side = data.get("side")
    if isinstance(side, dict):
        side_id = side.get("id")
        if isinstance(side_id, str):
            return side_id
    return ""


def _team_member_count(data: dict[str, Any]) -> int:
    side = data.get("side")
    if isinstance(side, dict) and isinstance(side.get("pokemon"), list):
        return len(side["pokemon"])
    return 0


def _read_team_preview(
    identity: RequestIdentity,
    side_id: str,
    pokemon_list: list[dict[str, Any]],
    data: dict[str, Any],
) -> DecisionRequest:
    team_size = len(pokemon_list)
    max_chosen = data.get("maxChosenTeamSize", team_size)
    if not isinstance(max_chosen, int) or isinstance(max_chosen, bool) or max_chosen < 1:
        raise MalformedProtocolMessage(f"invalid maxChosenTeamSize: {max_chosen!r}")
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
        team_member_count=max_chosen,
        active_identity=None,
        safe_submissions=SafeSubmissionSet(request_identity=identity, submissions=submissions),
        is_update=False,
    )


def _read_revival(
    identity: RequestIdentity,
    side_id: str,
    pokemon_list: list[dict[str, Any]],
    active_identity: str | None,
) -> DecisionRequest:
    candidates = [
        slot
        for slot, p in enumerate(pokemon_list, start=1)
        if not p.get("active") and _pokemon_fainted(p.get("condition", ""))
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
        is_update=False,
    )


def _read_forced_switch(
    identity: RequestIdentity,
    side_id: str,
    pokemon_list: list[dict[str, Any]],
    active_identity: str | None,
) -> DecisionRequest:
    candidates = [
        slot
        for slot, p in enumerate(pokemon_list, start=1)
        if not p.get("active") and not _pokemon_fainted(p.get("condition", ""))
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
        is_update=False,
    )


def _read_normal_move(
    identity: RequestIdentity,
    side_id: str,
    pokemon_list: list[dict[str, Any]],
    active_identity: str | None,
    data: dict[str, Any],
) -> DecisionRequest:
    active_list = data.get("active")
    if not isinstance(active_list, list) or not active_list or not isinstance(active_list[0], dict):
        raise MalformedProtocolMessage("move request missing active[0]")
    active_info = active_list[0]

    if active_info.get("maybeDisabled") or active_info.get("maybeLocked"):
        submissions: tuple[BattleSubmission, ...] = (_default_submission(),)
    else:
        moves = active_info.get("moves")
        if not isinstance(moves, list):
            raise MalformedProtocolMessage("active[0].moves must be a list")
        tera_type = active_info.get("canTerastallize")
        can_tera = isinstance(tera_type, str) and tera_type != ""

        move_submissions: list[BattleSubmission] = []
        for idx, move in enumerate(moves, start=1):
            if not isinstance(move, dict):
                raise MalformedProtocolMessage("invalid move entry")
            if move.get("disabled"):
                continue
            move_id = move.get("id")
            if not isinstance(move_id, str) or not move_id:
                raise MalformedProtocolMessage(f"invalid move id: {move_id!r}")
            move_submissions.append(
                BattleSubmission(
                    kind=ActionKind.MOVE,
                    provenance=ActionProvenance.EXPLICIT_REQUEST,
                    slot=idx,
                    move_id=move_id,
                )
            )
            if can_tera:
                move_submissions.append(
                    BattleSubmission(
                        kind=ActionKind.MOVE,
                        provenance=ActionProvenance.EXPLICIT_REQUEST,
                        slot=idx,
                        move_id=move_id,
                        terastallize=True,
                    )
                )

        switch_submissions: list[BattleSubmission] = []
        trapped = bool(active_info.get("trapped")) or bool(active_info.get("maybeTrapped"))
        if not trapped:
            switch_submissions = [
                BattleSubmission(
                    kind=ActionKind.SWITCH, provenance=ActionProvenance.EXPLICIT_REQUEST, slot=slot
                )
                for slot, p in enumerate(pokemon_list, start=1)
                if not p.get("active") and not _pokemon_fainted(p.get("condition", ""))
            ]

        submissions = tuple(move_submissions) + tuple(switch_submissions) + (_default_submission(),)

    return DecisionRequest(
        identity=identity,
        kind=RequestKind.MOVE,
        side_id=side_id,
        team_member_count=len(pokemon_list),
        active_identity=active_identity,
        safe_submissions=SafeSubmissionSet(request_identity=identity, submissions=submissions),
        is_update=False,
    )
