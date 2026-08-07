"""Strict observed/full-world mapping without crossing hidden-information boundaries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, NoReturn, cast

from battlebelief_core.canonicalization import manifest_digest
from battlebelief_core.domain.records.public_projection import observed_state_digest
from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_core.domain.state.values import HpPrecision


class _StateMappingError(ValueError):
    def __init__(self, failure_class: str) -> None:
        self.failure_class = failure_class
        super().__init__(failure_class)


def _fail(failure_class: str) -> NoReturn:
    raise _StateMappingError(failure_class)


def _exact_keys(
    value: object, required: frozenset[str], optional: frozenset[str] = frozenset()
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail("missing_field")
    keys = set(value)
    if not required.issubset(keys):
        _fail("missing_field")
    if not keys.issubset(required | optional) or any(type(key) is not str for key in keys):
        _fail("unsupported_mapping")
    return cast(Mapping[str, object], value)


def _integer(value: object, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail("unsupported_mapping")
    return value


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        _fail("unsupported_mapping")
    return value


def _token(value: object) -> str:
    if type(value) is not str or not value or not value.isascii():
        _fail("unsupported_mapping")
    return value


@dataclass(frozen=True, slots=True)
class _ObservedRoot:
    root_player: Literal["p1", "p2"]
    digest: str = field(repr=False)
    public_hp: tuple[tuple[str, int], tuple[str, int]] = field(repr=False)


@dataclass(frozen=True, slots=True)
class _MappedNativeState:
    native_state: str = field(repr=False)
    view_digests: tuple[str, str] = field(repr=False)
    active_indexes: tuple[int, int]
    active_types: tuple[tuple[str, str], tuple[str, str]]
    terastallized: tuple[bool, bool]
    terminal_outcome: Literal["p1", "p2", "tie"] | None
    public_hp: tuple[tuple[str, int], tuple[str, int]] = field(repr=False)


def _observed_hp_precision(state: ObservedState, player: Literal["p1", "p2"]) -> tuple[str, int]:
    side = state.side(player)
    if side.active_slot is not None and 1 <= side.active_slot <= len(side.pokemon):
        observation = side.pokemon[side.active_slot - 1].hp
        if observation is not None:
            return observation.precision.value, observation.maximum
    return HpPrecision.PERCENT.value, 100


def map_observed_root(state: ObservedState) -> _ObservedRoot:
    """Validate the public observation without enriching or rewriting it."""

    if not isinstance(state, ObservedState):
        _fail("missing_field")
    if (
        state.generation != 9
        or state.game_type != "singles"
        or state.tier != "gen9ou"
        or not state.room_initialized
        or not state.battle_started
        or state.our_side not in {"p1", "p2"}
    ):
        _fail("unsupported_mapping")
    public_hp = []
    for player in ("p1", "p2"):
        if player == state.our_side:
            public_hp.append((HpPrecision.PERCENT.value, 100))
        else:
            public_hp.append(_observed_hp_precision(state, player))
    return _ObservedRoot(
        root_player=cast(Literal["p1", "p2"], state.our_side),
        digest=observed_state_digest(state),
        public_hp=cast(tuple[tuple[str, int], tuple[str, int]], tuple(public_hp)),
    )


_WORLD_KEYS = frozenset({"schema_version", "fixture_id", "generation", "format", "field", "sides"})
_FIELD_KEYS = frozenset(
    {
        "weather",
        "weather_turns_remaining",
        "terrain",
        "terrain_turns_remaining",
        "trick_room",
        "trick_room_turns_remaining",
    }
)
_SIDE_KEYS = frozenset(
    {
        "pokemon",
        "active_index",
        "force_switch",
        "force_trapped",
        "side_conditions",
    }
)
_POKEMON_KEYS = frozenset(
    {
        "id",
        "level",
        "types",
        "base_types",
        "hp",
        "maxhp",
        "ability",
        "base_ability",
        "item",
        "nature",
        "evs",
        "attack",
        "defense",
        "special_attack",
        "special_defense",
        "speed",
        "status",
        "tera_type",
        "terastallized",
        "moves",
    }
)
_MOVE_KEYS = frozenset({"id", "pp", "disabled"})
_SIDE_CONDITIONS = frozenset(
    {
        "spikes",
        "toxic_spikes",
        "stealth_rock",
        "sticky_web",
        "tailwind",
        "reflect",
        "light_screen",
        "aurora_veil",
        "safeguard",
        "mist",
        "toxic_count",
    }
)


def _pair(value: object) -> tuple[str, str]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or len(value) != 2
    ):
        _fail("unsupported_mapping")
    return (_token(value[0]), _token(value[1]))


def _evs(value: object) -> tuple[int, int, int, int, int, int]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or len(value) != 6
    ):
        _fail("unsupported_mapping")
    result = tuple(_integer(item) for item in value)
    if any(item > 252 for item in result):
        _fail("unsupported_mapping")
    return cast(tuple[int, int, int, int, int, int], result)


def _pokemon(native: Any, value: object) -> Any:
    document = _exact_keys(value, _POKEMON_KEYS)
    moves_value = document["moves"]
    if (
        not isinstance(moves_value, Sequence)
        or isinstance(moves_value, (str, bytes, bytearray))
        or not 1 <= len(moves_value) <= 4
    ):
        _fail("unsupported_mapping")
    moves = []
    for raw_move in moves_value:
        move = _exact_keys(raw_move, _MOVE_KEYS)
        moves.append(
            native.Move(
                id=_token(move["id"]),
                pp=_integer(move["pp"]),
                disabled=_boolean(move["disabled"]),
            )
        )
    if len({move.id for move in moves}) != len(moves):
        _fail("unsupported_mapping")
    hp = _integer(document["hp"])
    maxhp = _integer(document["maxhp"], minimum=1)
    if hp > maxhp:
        _fail("unsupported_mapping")
    try:
        return native.Pokemon(
            id=_token(document["id"]),
            level=_integer(document["level"], minimum=1),
            types=_pair(document["types"]),
            base_types=_pair(document["base_types"]),
            hp=hp,
            maxhp=maxhp,
            ability=_token(document["ability"]),
            base_ability=_token(document["base_ability"]),
            item=_token(document["item"]),
            nature=_token(document["nature"]),
            evs=_evs(document["evs"]),
            attack=_integer(document["attack"], minimum=1),
            defense=_integer(document["defense"], minimum=1),
            special_attack=_integer(document["special_attack"], minimum=1),
            special_defense=_integer(document["special_defense"], minimum=1),
            speed=_integer(document["speed"], minimum=1),
            status=_token(document["status"]),
            tera_type=_token(document["tera_type"]),
            terastallized=_boolean(document["terastallized"]),
            moves=moves,
        )
    except BaseException as error:
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        _fail("native_exception")


def _side(native: Any, value: object) -> Any:
    document = _exact_keys(value, _SIDE_KEYS)
    pokemon_value = document["pokemon"]
    if (
        not isinstance(pokemon_value, Sequence)
        or isinstance(pokemon_value, (str, bytes, bytearray))
        or not 1 <= len(pokemon_value) <= 6
    ):
        _fail("unsupported_mapping")
    pokemon = [_pokemon(native, item) for item in pokemon_value]
    active_index = _integer(document["active_index"])
    if active_index >= len(pokemon):
        _fail("unsupported_mapping")
    conditions_document = _exact_keys(document["side_conditions"], frozenset(), _SIDE_CONDITIONS)
    conditions: dict[str, int] = {}
    for name, raw_count in conditions_document.items():
        conditions[name] = _integer(raw_count)
    try:
        index = getattr(native.PokemonIndex, f"P{active_index}")
        return native.Side(
            pokemon=pokemon,
            active_index=index,
            force_switch=_boolean(document["force_switch"]),
            force_trapped=_boolean(document["force_trapped"]),
            side_conditions=native.SideConditions(**conditions),
        )
    except BaseException as error:
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        _fail("native_exception")


def map_complete_world(
    native: Any,
    document: Mapping[str, object],
    observed_digest: str,
    *,
    public_hp: tuple[tuple[str, int], tuple[str, int]] = (
        (HpPrecision.PERCENT.value, 100),
        (HpPrecision.PERCENT.value, 100),
    ),
) -> _MappedNativeState:
    """Map a complete hypothetical world through a path distinct from observation."""

    world = _exact_keys(document, _WORLD_KEYS)
    if world["schema_version"] != 1 or world["generation"] != 9 or world["format"] != "gen9ou":
        _fail("unsupported_mapping")
    _token(world["fixture_id"])
    field_document = _exact_keys(world["field"], _FIELD_KEYS)
    sides = _exact_keys(world["sides"], frozenset({"p1", "p2"}))
    try:
        weather = getattr(native.Weather, _token(field_document["weather"]).upper())
        terrain = getattr(native.Terrain, _token(field_document["terrain"]).upper())
    except (AttributeError, TypeError):
        _fail("unsupported_mapping")
    try:
        state = native.State(
            side_one=_side(native, sides["p1"]),
            side_two=_side(native, sides["p2"]),
            weather=weather,
            weather_turns_remaining=_integer(field_document["weather_turns_remaining"]),
            terrain=terrain,
            terrain_turns_remaining=_integer(field_document["terrain_turns_remaining"]),
            trick_room=_boolean(field_document["trick_room"]),
            trick_room_turns_remaining=_integer(field_document["trick_room_turns_remaining"]),
        )
    except _StateMappingError:
        raise
    except BaseException as error:
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        _fail("native_exception")
    return map_native_state(native, state, observed_digest, public_hp=public_hp)


def map_serialized_state(
    native: Any,
    state_value: str,
    observed_digest: str,
    *,
    public_hp: tuple[tuple[str, int], tuple[str, int]] = (
        (HpPrecision.PERCENT.value, 100),
        (HpPrecision.PERCENT.value, 100),
    ),
) -> _MappedNativeState:
    if type(state_value) is not str or not state_value:
        _fail("malformed_native_result")
    try:
        state = native.State.from_string(state_value)
    except BaseException as error:
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        _fail("malformed_native_result")
    return map_native_state(native, state, observed_digest, public_hp=public_hp)


def map_native_state(
    native: Any,
    state: Any,
    observed_digest: str,
    *,
    prior_view_digests: tuple[str, str] | None = None,
    source_state: Any | None = None,
    public_hp: tuple[tuple[str, int], tuple[str, int]] = (
        (HpPrecision.PERCENT.value, 100),
        (HpPrecision.PERCENT.value, 100),
    ),
) -> _MappedNativeState:
    """Freeze a native state and derive separate, leakage-resistant player views."""

    try:
        serialized = state.to_string()
        if type(serialized) is not str or not serialized:
            _fail("malformed_native_result")
        sides = (state.side_one, state.side_two)
        indexes = tuple(int(side.active_index) for side in sides)
        terastallized = tuple(
            bool(side.pokemon[index].terastallized)
            for side, index in zip(sides, indexes, strict=True)
        )
        active_types = tuple(
            tuple(_effective_types(side.pokemon[index]))
            for side, index in zip(sides, indexes, strict=True)
        )
        defeated = tuple(all(int(pokemon.hp) <= 0 for pokemon in side.pokemon) for side in sides)
        terminal: Literal["p1", "p2", "tie"] | None
        if defeated == (True, True):
            terminal = "tie"
        elif defeated[1]:
            terminal = "p1"
        elif defeated[0]:
            terminal = "p2"
        else:
            terminal = None
        if (prior_view_digests is None) != (source_state is None):
            _fail("inconsistent_player_view")
        players: tuple[Literal["p1", "p2"], Literal["p1", "p2"]] = ("p1", "p2")
        views = tuple(
            _view_digest(
                state,
                observed_digest,
                player,
                None if prior_view_digests is None else prior_view_digests[index],
                source_state,
                public_hp,
            )
            for index, player in enumerate(players)
        )
        return _MappedNativeState(
            native_state=serialized,
            view_digests=cast(tuple[str, str], views),
            active_indexes=cast(tuple[int, int], indexes),
            active_types=cast(tuple[tuple[str, str], tuple[str, str]], active_types),
            terastallized=cast(tuple[bool, bool], terastallized),
            terminal_outcome=terminal,
            public_hp=public_hp,
        )
    except _StateMappingError:
        raise
    except BaseException as error:
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        _fail("malformed_native_result")


def _view_digest(
    state: Any,
    observed_digest: str,
    player: Literal["p1", "p2"],
    prior_view_digest: str | None,
    source_state: Any | None,
    public_hp: tuple[tuple[str, int], tuple[str, int]],
) -> str:
    own_index = 0 if player == "p1" else 1
    sides = (state.side_one, state.side_two)
    own = sides[own_index]
    private = {
        "active_index": int(own.active_index),
        "pokemon": [
            {
                "id": pokemon.id,
                "hp": int(pokemon.hp),
                "maxhp": int(pokemon.maxhp),
                "ability": pokemon.ability,
                "item": pokemon.item,
                "moves": [
                    {"id": move.id, "pp": int(move.pp), "disabled": bool(move.disabled)}
                    for move in pokemon.moves
                ],
                "tera_type": pokemon.tera_type,
                "terastallized": bool(pokemon.terastallized),
                "stats": [
                    int(pokemon.attack),
                    int(pokemon.defense),
                    int(pokemon.special_attack),
                    int(pokemon.special_defense),
                    int(pokemon.speed),
                ],
            }
            for pokemon in own.pokemon
        ],
    }
    if prior_view_digest is None:
        view_document = {
            "observed_state_digest": observed_digest,
            "player": player,
            "own_private": private,
        }
    else:
        view_document = {
            "prior_view_digest": prior_view_digest,
            "player": player,
            "own_private": private,
            "public_transition_delta": _public_transition_delta(
                source_state, state, player=player, public_hp=public_hp
            ),
        }
    return manifest_digest(view_document)


def _public_active(
    side: Any,
    *,
    own: bool,
    hp_precision: str,
    hp_maximum: int,
) -> dict[str, object]:
    index = int(side.active_index)
    active = side.pokemon[index]
    hp = int(active.hp)
    maxhp = int(active.maxhp)
    if own or hp_precision == HpPrecision.EXACT.value:
        hp_value: object = [hp, maxhp]
    else:
        denominator = hp_maximum if hp_precision == HpPrecision.PIXEL.value else 100
        hp_value = round((hp / maxhp) * denominator)
    return {
        "active_index": index,
        "id": active.id,
        "hp": {"current": hp_value, "precision": hp_precision},
        "status": active.status,
        "types": _effective_types(active),
        "terastallized": bool(active.terastallized),
        "tera_type": active.tera_type if bool(active.terastallized) else None,
    }


def _effective_types(active: Any) -> list[str]:
    if bool(active.terastallized):
        return [str(active.tera_type).lower(), "typeless"]
    return [str(value).lower() for value in active.types]


def _public_transition_delta(
    source: Any,
    target: Any,
    *,
    player: Literal["p1", "p2"],
    public_hp: tuple[tuple[str, int], tuple[str, int]],
) -> dict[str, object]:
    delta: dict[str, object] = {}
    side_deltas: dict[str, object] = {}
    for side_id, source_side, target_side in (
        ("p1", source.side_one, target.side_one),
        ("p2", source.side_two, target.side_two),
    ):
        side_index = 0 if side_id == "p1" else 1
        precision, maximum = public_hp[side_index]
        before = _public_active(
            source_side,
            own=side_id == player,
            hp_precision=precision,
            hp_maximum=maximum,
        )
        after = _public_active(
            target_side,
            own=side_id == player,
            hp_precision=precision,
            hp_maximum=maximum,
        )
        changed = {key: value for key, value in after.items() if before.get(key) != value}
        if changed:
            side_deltas[side_id] = changed
    if side_deltas:
        delta["sides"] = side_deltas
    for name in ("weather", "terrain", "trick_room"):
        before = getattr(source, name)
        after = getattr(target, name)
        if before != after:
            delta[name] = after
    return delta


__all__: list[str] = []
