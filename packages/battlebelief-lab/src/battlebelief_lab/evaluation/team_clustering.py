"""Canonical exact-team clusters for the M1.5 synthetic harness."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from battlebelief_core.canonicalization import canonicalize, manifest_digest
from battlebelief_core.domain.records.public_projection import to_showdown_id

_STATS = ("hp", "atk", "def", "spa", "spd", "spe")
_FIELDS = frozenset(
    {
        "species",
        "form",
        "item",
        "ability",
        "nature",
        "moves",
        "evs",
        "ivs",
        "level",
        "happiness",
        "gender",
        "shiny",
        "pokeball",
        "hidden_power_type",
        "tera_type",
    }
)


def _showdown_id(value: object, *, field: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} must be a string")
    result = to_showdown_id(value)
    if not result:
        raise ValueError(f"{field} has no Showdown identifier")
    return result


def _optional_showdown_id(value: object, *, field: str) -> str:
    if value is None or value == "":
        return ""
    return _showdown_id(value, field=field)


def _stat_values(value: object, *, field: str, maximum: int) -> dict[str, int]:
    if value is None:
        default = 0 if field == "evs" else 31
        return {stat: default for stat in _STATS}
    if not isinstance(value, Mapping) or set(value) != set(_STATS):
        raise ValueError(f"{field} must define exactly the six battle stats")
    result: dict[str, int] = {}
    for stat in _STATS:
        number = value[stat]
        if type(number) is not int or not 0 <= number <= maximum:
            raise ValueError(f"{field}.{stat} is outside its allowed range")
        result[stat] = number
    return result


def _canonical_member(member: Mapping[str, Any]) -> dict[str, Any]:
    unknown = set(member).difference(_FIELDS)
    if unknown:
        raise ValueError("team member contains an unowned field")
    if "species" not in member:
        raise ValueError("team member requires species")
    moves = member.get("moves")
    if not isinstance(moves, Sequence) or isinstance(moves, (str, bytes)) or len(moves) != 4:
        raise ValueError("team member requires exactly four moves")
    canonical_moves = tuple(sorted(_showdown_id(move, field="move") for move in moves))
    if len(set(canonical_moves)) != 4:
        raise ValueError("team member moves must be unique")
    level = member.get("level", 100)
    happiness = member.get("happiness", 255)
    if type(level) is not int or not 1 <= level <= 100:
        raise ValueError("level must be between 1 and 100")
    if type(happiness) is not int or not 0 <= happiness <= 255:
        raise ValueError("happiness must be between 0 and 255")
    gender = member.get("gender")
    if gender is not None:
        gender = _showdown_id(gender, field="gender")
        if gender not in {"m", "f"}:
            raise ValueError("gender must be M, F, or null")
    shiny = member.get("shiny", False)
    if type(shiny) is not bool:
        raise ValueError("shiny must be a boolean")
    return {
        "species": _showdown_id(member["species"], field="species"),
        "form": _optional_showdown_id(member.get("form", ""), field="form"),
        "item": _optional_showdown_id(member.get("item", ""), field="item"),
        "ability": _optional_showdown_id(member.get("ability", ""), field="ability"),
        "nature": _optional_showdown_id(member.get("nature", ""), field="nature"),
        "moves": list(canonical_moves),
        "evs": _stat_values(member.get("evs"), field="evs", maximum=252),
        "ivs": _stat_values(member.get("ivs"), field="ivs", maximum=31),
        "level": level,
        "happiness": happiness,
        "gender": gender,
        "shiny": shiny,
        "pokeball": _showdown_id(member.get("pokeball", "poke ball"), field="pokeball"),
        "hidden_power_type": _optional_showdown_id(
            member.get("hidden_power_type", ""), field="hidden_power_type"
        ),
        "tera_type": _optional_showdown_id(member.get("tera_type", ""), field="tera_type"),
    }


def canonical_team_projection(team: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return the versioned, member-order-independent exact-team projection."""

    if not isinstance(team, Sequence) or isinstance(team, (str, bytes, bytearray)):
        raise ValueError("team must be a sequence of member mappings")
    if len(team) != 6:
        raise ValueError("an exact team must contain exactly six members")
    if any(not isinstance(member, Mapping) for member in team):
        raise ValueError("team must contain only member mappings")
    members = [_canonical_member(member) for member in team]
    if any(sum(member["evs"].values()) > 510 for member in members):
        raise ValueError("EV total must not exceed 510")
    canonical_keys = [canonicalize(member) for member in members]
    if len(set(canonical_keys)) != len(canonical_keys):
        raise ValueError("team contains duplicate canonical members")
    members.sort(key=lambda member: canonicalize(member))
    return {"schema_version": 1, "member_count": 6, "members": members}


def team_cluster_id(team: Sequence[Mapping[str, Any]]) -> str:
    return manifest_digest(canonical_team_projection(team))


__all__ = ["canonical_team_projection", "team_cluster_id"]
