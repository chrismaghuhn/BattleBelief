from __future__ import annotations

from battlebelief_core.domain.events.base import BattleEvent
from battlebelief_core.domain.events.evidence import VisibleEvidence
from battlebelief_core.domain.events.field import (
    FieldConditionChanged,
    SideConditionChanged,
    SideConditionsSwapped,
    WeatherChanged,
)
from battlebelief_core.domain.events.ignored import IgnoredDisplayEvent
from battlebelief_core.domain.events.metadata import (
    BattleInit,
    BattleRated,
    GameTypeDeclared,
    GenerationDeclared,
    PlayerDeclared,
    PreviewCleared,
    PreviewPokemonDeclared,
    RuleDeclared,
    TeamPreviewStarted,
    TeamSizeDeclared,
    TierDeclared,
)
from battlebelief_core.domain.events.pokemon import (
    AbilityChanged,
    BoostChanged,
    BoostChangeMode,
    BoostsCleared,
    BoostsCopied,
    BoostsInverted,
    BoostsSwapped,
    FormChanged,
    FormChangeKind,
    HealthChanged,
    IdentityChanged,
    ItemChanged,
    MovePrevented,
    MoveUsed,
    PokemonDragged,
    PokemonFainted,
    PokemonSwitched,
    PokemonTransformed,
    RechargeChanged,
    StatusChanged,
    TeamStatusCured,
    Terastallized,
    VolatileChanged,
)
from battlebelief_core.domain.events.progress import (
    BattleStarted,
    BattleTied,
    BattleWon,
    TurnStarted,
)
from battlebelief_core.domain.state.pokemon_view import BOOST_STATS
from battlebelief_core.domain.state.values import HpToken
from battlebelief_runtime.adapters.showdown_protocol.wire_types import (
    EVIDENCE_TYPES,
    IGNORED_DISPLAY_TYPES,
)
from battlebelief_runtime.errors.protocol import (
    MalformedProtocolMessage,
    TimerOrForfeit,
    UnknownProtocolEvent,
)

# ---------------------------------------------------------------------------
# small pure helpers
# ---------------------------------------------------------------------------


def _to_id(text: str) -> str:
    """Showdown's toID(): lowercase, strip everything except a-z0-9."""
    return "".join(
        character for character in text.lower() if character.isascii() and character.isalnum()
    )


def _split(payload: str) -> tuple[str, list[str]]:
    parts = payload.split("|")
    wire_type = parts[1] if len(parts) > 1 else ""
    return wire_type, parts[2:]


def _looks_like_pokemon_ident(text: str) -> bool:
    return (
        len(text) > 1
        and text[0] == "p"
        and text[1].isdigit()
        and (": " in text or (text[2:].isdigit() is False and ":" in text))
    )


def _parse_pokemon_ident(ident: str) -> tuple[str, int | None, str]:
    """ "p1a: Garchomp" -> ("p1", 1, "Garchomp"); "p1: Garchomp" -> ("p1", None, "Garchomp")."""
    if ": " not in ident:
        raise MalformedProtocolMessage(f"invalid pokemon identifier: {ident!r}")
    position_part, nickname = ident.split(": ", 1)
    if len(position_part) < 2 or position_part[0] != "p" or not position_part[1].isdigit():
        raise MalformedProtocolMessage(f"invalid pokemon identifier: {ident!r}")
    if position_part[-1].isalpha():
        if position_part[-1] != "a":
            raise MalformedProtocolMessage(f"unsupported (non-singles) position: {ident!r}")
        side_id = position_part[:-1]
        slot: int | None = 1
    else:
        side_id = position_part
        slot = None
    if not nickname:
        raise MalformedProtocolMessage(f"invalid pokemon identifier: {ident!r}")
    return side_id, slot, nickname


def _parse_side_ident(ident: str) -> str:
    """ "p1" or "p1: Ash" -> "p1"."""
    side_id = ident.split(":", 1)[0].strip()
    if side_id not in ("p1", "p2"):
        raise MalformedProtocolMessage(f"invalid side identifier: {ident!r}")
    return side_id


def _parse_hp_token(hp_str: str) -> HpToken:
    segments = hp_str.split(" ", 1)
    hp_part = segments[0]
    trailer = segments[1] if len(segments) > 1 else None
    fainted = trailer == "fnt"
    status = trailer if trailer is not None and not fainted else None
    if "/" in hp_part:
        current_str, maximum_str = hp_part.split("/", 1)
        try:
            current = int(current_str)
            maximum = int(maximum_str)
        except ValueError as exc:
            raise MalformedProtocolMessage(f"invalid hp numbers: {hp_str!r}") from exc
    else:
        try:
            current = int(hp_part)
        except ValueError as exc:
            raise MalformedProtocolMessage(f"invalid hp value: {hp_str!r}") from exc
        maximum = 0
    if current < 0 or maximum < 0:
        raise MalformedProtocolMessage(f"invalid hp value: {hp_str!r}")
    return HpToken(current=current, maximum=maximum, status=status, fainted=fainted)


_BOOST_STAT_ALIASES = {"accuracy": "acc", "evasion": "eva"}


def _normalize_boost_stat(stat: str) -> str:
    return _BOOST_STAT_ALIASES.get(stat, stat)


def _sorted_annotations(parts: list[str]) -> tuple[str, ...]:
    return tuple(sorted(p for p in parts if p.startswith("[")))


def _require(args: list[str], count: int, wire_type: str) -> None:
    if len(args) < count:
        raise MalformedProtocolMessage(f"{wire_type}: expected at least {count} fields, got {args}")


# ---------------------------------------------------------------------------
# per-group handlers
# ---------------------------------------------------------------------------


def _parse_metadata(wire_type: str, args: list[str], ei: int) -> BattleEvent:
    if wire_type == "player":
        _require(args, 2, wire_type)
        side_id, username = args[0], args[1]
        return PlayerDeclared(
            event_index=ei, side_id=side_id, user_id=_to_id(username), display_name=username
        )
    if wire_type == "teamsize":
        _require(args, 2, wire_type)
        try:
            size = int(args[1])
        except ValueError as exc:
            raise MalformedProtocolMessage(f"teamsize: invalid size {args[1]!r}") from exc
        return TeamSizeDeclared(event_index=ei, side_id=args[0], size=size)
    if wire_type == "gametype":
        _require(args, 1, wire_type)
        return GameTypeDeclared(event_index=ei, game_type=args[0])
    if wire_type == "gen":
        _require(args, 1, wire_type)
        try:
            generation = int(args[0])
        except ValueError as exc:
            raise MalformedProtocolMessage(f"gen: invalid generation {args[0]!r}") from exc
        return GenerationDeclared(event_index=ei, generation=generation)
    if wire_type == "tier":
        _require(args, 1, wire_type)
        return TierDeclared(event_index=ei, tier="|".join(args))
    if wire_type == "rated":
        return BattleRated(event_index=ei, rated=True)
    if wire_type == "rule":
        _require(args, 1, wire_type)
        return RuleDeclared(event_index=ei, rule="|".join(args))
    raise UnknownProtocolEvent(wire_type)


def _parse_preview(wire_type: str, args: list[str], ei: int) -> BattleEvent:
    if wire_type == "clearpoke":
        return PreviewCleared(event_index=ei)
    if wire_type == "poke":
        _require(args, 2, wire_type)
        side_id, details = args[0], args[1]
        has_item = len(args) > 2 and args[2] == "item"
        return PreviewPokemonDeclared(
            event_index=ei, side_id=side_id, details=details, has_item=has_item
        )
    if wire_type == "teampreview":
        return TeamPreviewStarted(event_index=ei)
    raise UnknownProtocolEvent(wire_type)


def _parse_progress(wire_type: str, args: list[str], ei: int) -> BattleEvent:
    if wire_type == "start":
        return BattleStarted(event_index=ei)
    if wire_type == "turn":
        _require(args, 1, wire_type)
        try:
            turn = int(args[0])
        except ValueError as exc:
            raise MalformedProtocolMessage(f"turn: invalid turn {args[0]!r}") from exc
        return TurnStarted(event_index=ei, turn=turn)
    if wire_type == "win":
        _require(args, 1, wire_type)
        return BattleWon(event_index=ei, winner=args[0])
    if wire_type == "tie":
        return BattleTied(event_index=ei)
    raise UnknownProtocolEvent(wire_type)


def _parse_pokemon_identity(wire_type: str, args: list[str], ei: int) -> BattleEvent:
    if wire_type in ("switch", "drag"):
        _require(args, 3, wire_type)
        side_id, slot, nickname = _parse_pokemon_ident(args[0])
        if slot is None:
            raise MalformedProtocolMessage(f"{wire_type}: requires an active-slot identifier")
        details = args[1]
        hp = _parse_hp_token(args[2])
        cls = PokemonSwitched if wire_type == "switch" else PokemonDragged
        return cls(
            event_index=ei, side_id=side_id, slot=slot, nickname=nickname, details=details, hp=hp
        )
    if wire_type == "faint":
        _require(args, 1, wire_type)
        side_id, slot, nickname = _parse_pokemon_ident(args[0])
        if slot is None:
            raise MalformedProtocolMessage("faint: requires an active-slot identifier")
        return PokemonFainted(event_index=ei, side_id=side_id, slot=slot, nickname=nickname)
    if wire_type == "cant":
        _require(args, 2, wire_type)
        side_id, slot, nickname = _parse_pokemon_ident(args[0])
        if slot is None:
            raise MalformedProtocolMessage("cant: requires an active-slot identifier")
        reason = args[1]
        move_id = _to_id(args[2]) if len(args) > 2 and args[2] else None
        return MovePrevented(
            event_index=ei,
            side_id=side_id,
            slot=slot,
            nickname=nickname,
            reason=reason,
            move_id=move_id,
        )
    if wire_type == "detailschange":
        _require(args, 3, wire_type)
        side_id, slot, nickname = _parse_pokemon_ident(args[0])
        if slot is None:
            raise MalformedProtocolMessage("detailschange: requires an active-slot identifier")
        hp = _parse_hp_token(args[2])
        return FormChanged(
            event_index=ei,
            side_id=side_id,
            slot=slot,
            nickname=nickname,
            kind=FormChangeKind.PERSISTENT_DETAILS,
            value=args[1],
            hp=hp,
        )
    if wire_type == "replace":
        _require(args, 3, wire_type)
        side_id, slot, nickname = _parse_pokemon_ident(args[0])
        if slot is None:
            raise MalformedProtocolMessage("replace: requires an active-slot identifier")
        hp = _parse_hp_token(args[2])
        return IdentityChanged(
            event_index=ei, side_id=side_id, slot=slot, nickname=nickname, details=args[1], hp=hp
        )
    if wire_type == "move":
        _require(args, 2, wire_type)
        side_id, slot, nickname = _parse_pokemon_ident(args[0])
        if slot is None:
            raise MalformedProtocolMessage("move: requires an active-slot identifier")
        move_id = _to_id(args[1])
        rest = args[2:]
        target_side_id = target_slot = target_nickname = None
        if rest and _looks_like_pokemon_ident(rest[0]):
            target_side_id, target_slot, target_nickname = _parse_pokemon_ident(rest[0])
            rest = rest[1:]
        return MoveUsed(
            event_index=ei,
            side_id=side_id,
            slot=slot,
            nickname=nickname,
            move_id=move_id,
            target_side_id=target_side_id,
            target_slot=target_slot,
            target_nickname=target_nickname,
            annotations=_sorted_annotations(rest),
        )
    raise UnknownProtocolEvent(wire_type)


def _parse_health(wire_type: str, args: list[str], ei: int) -> BattleEvent:
    _require(args, 2, wire_type)
    side_id, slot, nickname = _parse_pokemon_ident(args[0])
    hp = _parse_hp_token(args[1])
    return HealthChanged(
        event_index=ei,
        side_id=side_id,
        slot=slot,
        nickname=nickname,
        hp=hp,
        annotations=_sorted_annotations(args[2:]),
    )


def _parse_status(wire_type: str, args: list[str], ei: int) -> BattleEvent:
    if wire_type == "-cureteam":
        _require(args, 1, wire_type)
        side_id = _parse_pokemon_ident(args[0])[0]
        return TeamStatusCured(event_index=ei, side_id=side_id)
    _require(args, 1, wire_type)
    side_id, slot, nickname = _parse_pokemon_ident(args[0])
    if slot is None:
        raise MalformedProtocolMessage(f"{wire_type}: requires an active-slot identifier")
    status = None if wire_type == "-curestatus" else (args[1] if len(args) > 1 else None)
    return StatusChanged(
        event_index=ei,
        side_id=side_id,
        slot=slot,
        nickname=nickname,
        status=status,
        annotations=_sorted_annotations(args[2:]),
    )


def _parse_boost(wire_type: str, args: list[str], ei: int) -> BattleEvent:
    if wire_type in ("-boost", "-unboost", "-setboost"):
        _require(args, 3, wire_type)
        side_id, slot, nickname = _parse_pokemon_ident(args[0])
        if slot is None:
            raise MalformedProtocolMessage(f"{wire_type}: requires an active-slot identifier")
        stat = _normalize_boost_stat(args[1])
        try:
            magnitude = int(args[2])
        except ValueError as exc:
            raise MalformedProtocolMessage(f"{wire_type}: invalid amount {args[2]!r}") from exc
        if wire_type == "-setboost":
            mode, amount = BoostChangeMode.SET, magnitude
        else:
            mode = BoostChangeMode.DELTA
            amount = magnitude if wire_type == "-boost" else -magnitude
        return BoostChanged(
            event_index=ei,
            side_id=side_id,
            slot=slot,
            nickname=nickname,
            stat=stat,
            mode=mode,
            amount=amount,
        )
    if wire_type in ("-swapboost", "-copyboost"):
        _require(args, 2, wire_type)
        first_side, first_slot, first_nick = _parse_pokemon_ident(args[0])
        second_side, second_slot, second_nick = _parse_pokemon_ident(args[1])
        if first_slot is None or second_slot is None:
            raise MalformedProtocolMessage(f"{wire_type}: requires active-slot identifiers")
        stats_arg = args[2] if len(args) > 2 else ""
        stats = (
            tuple(_normalize_boost_stat(s) for s in stats_arg.split(",") if s)
            if stats_arg
            else BOOST_STATS
        )
        if wire_type == "-swapboost":
            return BoostsSwapped(
                event_index=ei,
                side_id=first_side,
                slot=first_slot,
                nickname=first_nick,
                target_side_id=second_side,
                target_slot=second_slot,
                target_nickname=second_nick,
                stats=stats,
            )
        # -copyboost NEWPOKEMON OLDPOKEMON: first arg receives, second is source
        return BoostsCopied(
            event_index=ei,
            side_id=first_side,
            slot=first_slot,
            nickname=first_nick,
            source_side_id=second_side,
            source_slot=second_slot,
            source_nickname=second_nick,
            stats=stats,
        )
    if wire_type == "-clearallboost":
        return BoostsCleared(event_index=ei, side_id=None, slot=None, nickname=None, scope="all")
    if wire_type in ("-clearboost", "-clearpositiveboost", "-clearnegativeboost"):
        _require(args, 1, wire_type)
        side_id, slot, nickname = _parse_pokemon_ident(args[0])
        if slot is None:
            raise MalformedProtocolMessage(f"{wire_type}: requires an active-slot identifier")
        scope = {
            "-clearboost": "all",
            "-clearpositiveboost": "positive",
            "-clearnegativeboost": "negative",
        }[wire_type]
        return BoostsCleared(
            event_index=ei, side_id=side_id, slot=slot, nickname=nickname, scope=scope
        )
    if wire_type == "-invertboost":
        _require(args, 1, wire_type)
        side_id, slot, nickname = _parse_pokemon_ident(args[0])
        if slot is None:
            raise MalformedProtocolMessage("-invertboost: requires an active-slot identifier")
        return BoostsInverted(event_index=ei, side_id=side_id, slot=slot, nickname=nickname)
    raise UnknownProtocolEvent(wire_type)


def _parse_field(wire_type: str, args: list[str], ei: int) -> BattleEvent:
    if wire_type == "-weather":
        _require(args, 1, wire_type)
        weather_name = args[0]
        rest = args[1:]
        if weather_name.lower() == "none":
            return WeatherChanged(event_index=ei, weather=None, action="end")
        action = "upkeep" if "[upkeep]" in rest else "start"
        return WeatherChanged(event_index=ei, weather=weather_name, action=action)
    if wire_type in ("-fieldstart", "-fieldend"):
        _require(args, 1, wire_type)
        action = "start" if wire_type == "-fieldstart" else "end"
        return FieldConditionChanged(
            event_index=ei,
            condition=args[0],
            action=action,
            annotations=_sorted_annotations(args[1:]),
        )
    if wire_type in ("-sidestart", "-sideend"):
        _require(args, 2, wire_type)
        side_id = _parse_side_ident(args[0])
        action = "start" if wire_type == "-sidestart" else "end"
        return SideConditionChanged(
            event_index=ei, side_id=side_id, condition=args[1], action=action
        )
    if wire_type == "-swapsideconditions":
        return SideConditionsSwapped(event_index=ei)
    raise UnknownProtocolEvent(wire_type)


def _parse_volatile(wire_type: str, args: list[str], ei: int) -> BattleEvent:
    if wire_type == "-mustrecharge":
        _require(args, 1, wire_type)
        side_id, slot, nickname = _parse_pokemon_ident(args[0])
        if slot is None:
            raise MalformedProtocolMessage("-mustrecharge: requires an active-slot identifier")
        return RechargeChanged(
            event_index=ei, side_id=side_id, slot=slot, nickname=nickname, recharging=True
        )
    _require(args, 2, wire_type)
    side_id, slot, nickname = _parse_pokemon_ident(args[0])
    if slot is None:
        raise MalformedProtocolMessage(f"{wire_type}: requires an active-slot identifier")
    action = "end" if wire_type == "-end" else "start"
    return VolatileChanged(
        event_index=ei,
        side_id=side_id,
        slot=slot,
        nickname=nickname,
        volatile=args[1],
        action=action,
        annotations=_sorted_annotations(args[2:]),
    )


def _parse_item_ability(wire_type: str, args: list[str], ei: int) -> BattleEvent:
    _require(args, 1, wire_type)
    side_id, slot, nickname = _parse_pokemon_ident(args[0])
    if slot is None:
        raise MalformedProtocolMessage(f"{wire_type}: requires an active-slot identifier")
    is_set = wire_type in ("-item", "-ability")
    action = "set" if is_set else "end"
    rest = args[1:]
    if wire_type in ("-item", "-enditem"):
        item = _to_id(rest[0]) if is_set and rest else None
        return ItemChanged(
            event_index=ei,
            side_id=side_id,
            slot=slot,
            nickname=nickname,
            item=item,
            action=action,
            annotations=_sorted_annotations(rest[1:] if is_set else rest),
        )
    ability = _to_id(rest[0]) if is_set and rest else None
    return AbilityChanged(
        event_index=ei,
        side_id=side_id,
        slot=slot,
        nickname=nickname,
        ability=ability,
        action=action,
        annotations=_sorted_annotations(rest[1:] if is_set else rest),
    )


def _parse_form_tera(wire_type: str, args: list[str], ei: int) -> BattleEvent:
    if wire_type == "-transform":
        _require(args, 2, wire_type)
        side_id, slot, nickname = _parse_pokemon_ident(args[0])
        target_side_id, target_slot, target_nickname = _parse_pokemon_ident(args[1])
        if slot is None or target_slot is None:
            raise MalformedProtocolMessage("-transform: requires active-slot identifiers")
        return PokemonTransformed(
            event_index=ei,
            side_id=side_id,
            slot=slot,
            nickname=nickname,
            target_side_id=target_side_id,
            target_slot=target_slot,
            target_nickname=target_nickname,
        )
    if wire_type == "-formechange":
        _require(args, 3, wire_type)
        side_id, slot, nickname = _parse_pokemon_ident(args[0])
        if slot is None:
            raise MalformedProtocolMessage("-formechange: requires an active-slot identifier")
        hp = _parse_hp_token(args[2])
        return FormChanged(
            event_index=ei,
            side_id=side_id,
            slot=slot,
            nickname=nickname,
            kind=FormChangeKind.TEMPORARY_SPECIES,
            value=args[1],
            hp=hp,
        )
    if wire_type == "-terastallize":
        _require(args, 2, wire_type)
        side_id, slot, nickname = _parse_pokemon_ident(args[0])
        if slot is None:
            raise MalformedProtocolMessage("-terastallize: requires an active-slot identifier")
        return Terastallized(
            event_index=ei, side_id=side_id, slot=slot, nickname=nickname, tera_type=args[1]
        )
    raise UnknownProtocolEvent(wire_type)


def _parse_evidence(wire_type: str, args: list[str], ei: int) -> VisibleEvidence:
    kind = wire_type[1:]
    side_id = slot = nickname = None
    remaining = list(args)
    if remaining and _looks_like_pokemon_ident(remaining[0]):
        side_id, slot, nickname = _parse_pokemon_ident(remaining[0])
        remaining = remaining[1:]
    effect = None
    if remaining and not remaining[0].startswith("["):
        effect = remaining[0]
        remaining = remaining[1:]
    return VisibleEvidence(
        event_index=ei,
        kind=kind,
        side_id=side_id,
        slot=slot,
        nickname=nickname,
        effect=effect,
        annotations=_sorted_annotations(remaining),
    )


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------

_METADATA_TYPES = frozenset({"player", "teamsize", "gametype", "gen", "tier", "rated", "rule"})
_PREVIEW_TYPES = frozenset({"clearpoke", "poke", "teampreview"})
_PROGRESS_TYPES = frozenset({"start", "turn", "win", "tie"})
_POKEMON_IDENTITY_TYPES = frozenset(
    {"move", "switch", "drag", "faint", "cant", "detailschange", "replace"}
)
_HEALTH_TYPES = frozenset({"-damage", "-heal", "-sethp"})
_STATUS_TYPES = frozenset({"-status", "-curestatus", "-cureteam"})
_BOOST_TYPES = frozenset(
    {
        "-boost",
        "-unboost",
        "-setboost",
        "-swapboost",
        "-copyboost",
        "-clearboost",
        "-clearallboost",
        "-clearpositiveboost",
        "-clearnegativeboost",
        "-invertboost",
    }
)
_FIELD_TYPES = frozenset(
    {"-weather", "-fieldstart", "-fieldend", "-sidestart", "-sideend", "-swapsideconditions"}
)
_VOLATILE_TYPES = frozenset({"-start", "-end", "-singleturn", "-singlemove", "-mustrecharge"})
_ITEM_ABILITY_TYPES = frozenset({"-item", "-enditem", "-ability", "-endability"})
_FORM_TERA_TYPES = frozenset({"-transform", "-formechange", "-terastallize"})


def parse_battle_line(payload: str, event_index: int, *, room_id: str | None = None) -> BattleEvent:
    """Parse a single classified BATTLE_EVENT payload into a canonical Core event.

    `|request|`, `|error|`, `|inactive|`, `|inactiveoff|`, and non-battle room
    lines never reach this function — the RoomPayloadClassifier enforces that
    boundary before parse_battle_line is called.

    `room_id` is required only for `init`, since BattleInit needs the room
    identity that Task 6's frame decoder already resolved via RoomLine
    context — no other event carries a room_id field.
    """
    try:
        wire_type, args = _split(payload)

        if wire_type == "init":
            if args != ["battle"]:
                raise MalformedProtocolMessage(f"unsupported init room type: {args!r}")
            if room_id is None:
                raise MalformedProtocolMessage("init requires room_id from RoomLine context")
            return BattleInit(event_index=event_index, room_id=room_id)
        if wire_type in _METADATA_TYPES:
            return _parse_metadata(wire_type, args, event_index)
        if wire_type in _PREVIEW_TYPES:
            return _parse_preview(wire_type, args, event_index)
        if wire_type in _PROGRESS_TYPES:
            return _parse_progress(wire_type, args, event_index)
        if wire_type in _POKEMON_IDENTITY_TYPES:
            return _parse_pokemon_identity(wire_type, args, event_index)
        if wire_type in _HEALTH_TYPES:
            return _parse_health(wire_type, args, event_index)
        if wire_type in _STATUS_TYPES:
            return _parse_status(wire_type, args, event_index)
        if wire_type in _BOOST_TYPES:
            return _parse_boost(wire_type, args, event_index)
        if wire_type in _FIELD_TYPES:
            return _parse_field(wire_type, args, event_index)
        if wire_type in _VOLATILE_TYPES:
            return _parse_volatile(wire_type, args, event_index)
        if wire_type in _ITEM_ABILITY_TYPES:
            return _parse_item_ability(wire_type, args, event_index)
        if wire_type in _FORM_TERA_TYPES:
            return _parse_form_tera(wire_type, args, event_index)
        if wire_type in EVIDENCE_TYPES:
            return _parse_evidence(wire_type, args, event_index)
        if payload == "|":
            return IgnoredDisplayEvent(event_index=event_index, kind="spacer")
        if wire_type == "-message":
            message = "|".join(args) if args else ""
            lowered = message.lower()
            if (
                lowered.endswith(" lost due to inactivity.")
                or lowered.endswith(" forfeited.")
                or lowered == "all players are inactive."
            ):
                raise TimerOrForfeit(message)
        if wire_type in IGNORED_DISPLAY_TYPES:
            return IgnoredDisplayEvent(event_index=event_index, kind=wire_type)
        raise UnknownProtocolEvent(wire_type)
    except (MalformedProtocolMessage, UnknownProtocolEvent):
        raise
    except (ValueError, IndexError, KeyError) as exc:
        raise MalformedProtocolMessage(f"malformed battle line {payload!r}: {exc}") from exc


def parse_inactive_line(payload: str, event_index: int) -> BattleEvent:
    """Parse a TIMER_MESSAGE-classified `|inactive|` or `|inactiveoff|` line."""
    from battlebelief_runtime.errors.protocol import TimerOrForfeit

    wire_type, args = _split(payload)
    message = "|".join(args) if args else ""
    if wire_type == "inactiveoff":
        return VisibleEvidence(
            event_index=event_index,
            kind="timer_warning_cleared",
            side_id=None,
            slot=None,
            nickname=None,
            effect=message or None,
            annotations=(),
        )
    if wire_type == "inactive":
        lowered = message.lower()
        if "forfeit" in lowered or "lost due to inactivity" in lowered:
            raise TimerOrForfeit(message)
        return VisibleEvidence(
            event_index=event_index,
            kind="timer_warning",
            side_id=None,
            slot=None,
            nickname=None,
            effect=message or None,
            annotations=(),
        )
    raise UnknownProtocolEvent(f"not an inactive line: {wire_type!r}")
