from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import re
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field, replace
from numbers import Real
from typing import Any, cast

from battlebelief_core.domain.events.metadata import (
    GameTypeDeclared,
    GenerationDeclared,
    PlayerDeclared,
    TierDeclared,
)
from battlebelief_runtime.adapters.showdown_client.types import BattleConnection
from battlebelief_runtime.adapters.showdown_protocol.challenge_state_reader import (
    ChallengeStateReader,
    OutgoingChallengeStatus,
)
from battlebelief_runtime.adapters.showdown_protocol.frame_decoder import RoomLine
from battlebelief_runtime.adapters.showdown_protocol.parser import parse_battle_line
from battlebelief_runtime.adapters.team_files.packed_team import PackedTeam
from battlebelief_runtime.composition.battle_session import (
    BattleSession,
    BattleSessionResult,
    DecisionPolicy,
)
from battlebelief_runtime.errors.protocol import (
    Disconnect,
    MalformedProtocolMessage,
    UnknownProtocolEvent,
)
from battlebelief_runtime.errors.setup import ChallengeSetupError, TeamValidationError

_FORMAT_ID = "gen9ou"
_GAME_TYPE = "singles"
_GENERATION = 9
_TIER = "[Gen 9] OU"
_TEAM_VALIDATION_PREFIXES = (
    "Your team was rejected for the following reason:\n\n- ",
    "Your team was rejected for the following reasons:\n\n- ",
)
_EXPLICIT_REJECTION_MESSAGES = frozenset(
    {
        "You can't battle yourself. The best you can do is open PS in Private Browsing "
        "(or another browser) and log into a different username, and battle that username.",
        "You are already challenging someone. Cancel that challenge before challenging someone else.",
        "You challenged less than 10 seconds after your last challenge! It's cancelled in "
        "case it's a misclick.",
        "This user already has 3 pending challenges.\nYou must be autoconfirmed to challenge them.",
        "You are locked and cannot challenge unlocked users. If this user is your friend, "
        "ask them to challenge you instead.",
        "You are banned from battling and cannot challenge users.",
        "You must choose a username before you challenge someone.",
        "The server is restarting. Battles will be available again in a few minutes.",
        "The server is under attack. Battles cannot be started at this time.",
    }
)
_HARMLESS_GLOBAL_TYPES = frozenset(
    {
        "B",
        "b",
        "battle",
        "customgroups",
        "formats",
        "usercount",
    }
)
_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _RoomCandidate:
    room_id: str
    lines: list[RoomLine] = field(default_factory=list)
    battle_initialized: bool = False
    players: dict[str, str] = field(default_factory=dict)
    game_type: str | None = None
    generation: int | None = None
    tier: str | None = None
    metadata_error: MalformedProtocolMessage | None = None


class _SessionConnection:
    def __init__(
        self,
        connection: BattleConnection,
        source: AsyncIterator[RoomLine],
        room_id: str,
        buffered_lines: tuple[RoomLine, ...],
        validate_line: Callable[[RoomLine], None],
    ) -> None:
        self._connection = connection
        self._source = source
        self._room_id = room_id
        self._buffered_lines = buffered_lines
        self._validate_line = validate_line

    async def connect(self) -> None:
        return None

    def lines(self) -> AsyncIterator[RoomLine]:
        return self._line_stream()

    async def _line_stream(self) -> AsyncIterator[RoomLine]:
        for line in self._buffered_lines:
            yield line
        async for line in self._source:
            if line.room_id == self._room_id:
                self._validate_line(line)
                yield line

    async def send_global(self, command: str) -> None:
        await self._connection.send_global(command)

    async def send_room(self, room_id: str, command: str) -> None:
        await self._connection.send_room(room_id, command)

    async def close(self) -> None:
        return None


class BattleCoordinator:
    _connection: BattleConnection
    _our_user_id: str
    _opponent_display: str
    _opponent_user_id: str
    _team: PackedTeam
    _setup_timeout: float
    _policy: DecisionPolicy | None

    def __init__(
        self,
        connection: BattleConnection,
        our_user_id: str,
        opponent_display: str,
        team: PackedTeam,
        setup_timeout: float,
        policy: DecisionPolicy | None = None,
    ) -> None:
        normalized_our_user_id = _to_id(our_user_id)
        normalized_opponent_user_id = _to_id(opponent_display)
        if not normalized_our_user_id or not normalized_opponent_user_id:
            raise ValueError("user IDs must normalize to non-empty ASCII identifiers")
        if (
            any(character in {",", "|", "\r", "\n"} for character in opponent_display)
            or not opponent_display.isprintable()
        ):
            raise ValueError("opponent display contains unsafe command characters")
        if (
            isinstance(setup_timeout, bool)
            or not isinstance(setup_timeout, Real)
            or not math.isfinite(setup_timeout)
            or setup_timeout <= 0
        ):
            raise ValueError("setup timeout must be a finite positive real value")
        if team.packed == "" or "\r" in team.packed or "\n" in team.packed:
            raise TeamValidationError("packed team must be one nonempty physical line")
        packed_digest = hashlib.sha256(team.packed.encode("utf-8")).hexdigest()
        if packed_digest != team.sealed.digest:
            raise TeamValidationError("packed team digest does not match its sealed team")
        self._connection = connection
        self._our_user_id = normalized_our_user_id
        self._opponent_display = opponent_display
        self._opponent_user_id = normalized_opponent_user_id
        self._team = team
        self._setup_timeout = float(setup_timeout)
        self._policy = policy

    async def run(self) -> BattleSessionResult:
        result: BattleSessionResult | None = None
        primary_error: BaseException | None = None
        try:
            _LOGGER.info(
                "starting direct Gen 9 OU challenge opponent_id=%s team_digest=%s",
                self._opponent_user_id,
                self._team.sealed.digest,
            )
            await self._connection.connect()
            source = self._connection.lines()
            candidate = await self._discover(source)
            session = BattleSession(
                connection=_SessionConnection(
                    self._connection,
                    source,
                    candidate.room_id,
                    tuple(candidate.lines),
                    lambda line: self._validate_handoff_line(candidate, line),
                ),
                room_id=candidate.room_id,
                our_user_id=self._our_user_id,
                policy=self._policy,
            )
            result = await session.run()
            if (
                result.primary_error is None
                and result.state.winner is None
                and not result.state.tied
            ):
                result = replace(
                    result,
                    primary_error=Disconnect(
                        "Showdown battle stream ended before a terminal result"
                    ),
                )
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            try:
                await self._connection.close()
            except BaseException:
                if primary_error is None and (result is None or result.primary_error is None):
                    raise

        assert result is not None
        return result

    async def _discover(self, source: AsyncIterator[RoomLine]) -> _RoomCandidate:
        candidates: dict[str, _RoomCandidate] = {}
        challenge_reader = ChallengeStateReader(
            our_user_id=self._our_user_id,
            target_user_id=self._opponent_user_id,
            format_id=_FORMAT_ID,
        )
        ever_pending = False
        latest_status: OutgoingChallengeStatus | None = None
        bootstrap_complete = False
        excluded_room_ids: set[str] = set()
        timeout = asyncio.timeout(self._setup_timeout)
        try:
            async with timeout:
                async for line in source:
                    if line.room_id is None:
                        if line.payload.startswith("|updatesearch|"):
                            existing_room_ids = _read_existing_room_ids(line.payload)
                            if not bootstrap_complete:
                                excluded_room_ids.update(existing_room_ids)
                                bootstrap_complete = True
                                await self._connection.send_global(f"|/utm {self._team.packed}")
                                await self._connection.send_global(
                                    f"|/challenge {self._opponent_display}, {_FORMAT_ID}"
                                )
                            continue
                        observation = challenge_reader.read(line.payload)
                        if observation is not None:
                            if bootstrap_complete:
                                latest_status = observation.status
                                ever_pending = ever_pending or (
                                    observation.status == OutgoingChallengeStatus.PENDING
                                )
                            continue
                        self._read_global_line(line.payload)
                        continue
                    if not bootstrap_complete:
                        excluded_room_ids.add(line.room_id)
                        continue
                    if line.room_id in excluded_room_ids:
                        continue
                    candidate = candidates.setdefault(
                        line.room_id, _RoomCandidate(room_id=line.room_id)
                    )
                    candidate.lines.append(line)
                    self._read_candidate_metadata(candidate, line)
                    self._raise_for_exact_candidate_failure(candidate)
                    if self._is_matching_candidate(candidate):
                        return candidate
                await asyncio.Event().wait()
        except TimeoutError as exc:
            if not timeout.expired():
                raise
            subcode = (
                "challenge_not_pending"
                if ever_pending and latest_status == OutgoingChallengeStatus.NOT_PENDING
                else "challenge_setup_timeout"
            )
            raise ChallengeSetupError(
                subcode=subcode,
                message="direct challenge setup did not produce a matching battle room",
            ) from exc

        raise AssertionError("unreachable")

    def _read_global_line(self, payload: str) -> None:
        if payload.startswith("|popup|"):
            self._read_popup(payload.removeprefix("|popup|"))
            return
        if payload.startswith("|error|"):
            self._read_popup(payload.removeprefix("|error|"))
            return
        if payload.startswith("|pm|"):
            return
        if _global_wire_type(payload) in _HARMLESS_GLOBAL_TYPES:
            return
        raise UnknownProtocolEvent("unrecognized setup payload")

    def _read_popup(self, wire_message: str) -> None:
        message = wire_message.replace("||", "\n")
        if message.startswith(_TEAM_VALIDATION_PREFIXES):
            raise TeamValidationError("Showdown rejected the selected team")
        if self._is_explicit_challenge_rejection(message):
            raise ChallengeSetupError(
                subcode="challenge_command_rejected_explicit",
                message="Showdown explicitly rejected the challenge command",
            )
        raise UnknownProtocolEvent("unrecognized setup popup")

    def _is_explicit_challenge_rejection(self, message: str) -> bool:
        if message in _EXPLICIT_REJECTION_MESSAGES:
            return True

        user_not_found = re.fullmatch(r"The user '([^']+)' was not found\.", message)
        if user_not_found is not None:
            return user_not_found.group(1) == self._opponent_display

        target_blocking = re.fullmatch(
            r"The user '([^']+)' is not accepting challenges right now\.", message
        )
        if target_blocking is not None:
            return _to_id(target_blocking.group(1)) == self._opponent_user_id

        existing_challenge = re.fullmatch(
            r"There's already a challenge \(([^()]*)\) between you and (.+)!", message
        )
        return (
            existing_challenge is not None
            and existing_challenge.group(1) == _FORMAT_ID
            and _to_id(existing_challenge.group(2)) == self._opponent_user_id
        )

    def _read_candidate_metadata(self, candidate: _RoomCandidate, line: RoomLine) -> None:
        if line.payload == "|init|battle":
            parse_battle_line(line.payload, len(candidate.lines) - 1, room_id=candidate.room_id)
            candidate.battle_initialized = True
            return
        if (
            not candidate.battle_initialized
            and line.payload.startswith(("|player|", "|gametype|", "|gen|", "|tier|"))
            and candidate.metadata_error is None
        ):
            candidate.metadata_error = MalformedProtocolMessage(
                "battle metadata arrived before battle initialization"
            )
        if not candidate.battle_initialized:
            return
        if not line.payload.startswith(("|player|", "|gametype|", "|gen|", "|tier|")):
            return
        try:
            event = parse_battle_line(
                line.payload,
                len(candidate.lines) - 1,
                room_id=candidate.room_id,
            )
        except MalformedProtocolMessage as exc:
            if candidate.metadata_error is None:
                candidate.metadata_error = exc
            return
        if isinstance(event, PlayerDeclared):
            player_id = _to_id(event.display_name)
            if event.side_id not in {"p1", "p2"} or not player_id:
                if candidate.metadata_error is None:
                    candidate.metadata_error = MalformedProtocolMessage(
                        "battle player metadata is malformed"
                    )
                return
            existing_player_id = candidate.players.get(event.side_id)
            if existing_player_id is None:
                candidate.players[event.side_id] = player_id
            elif existing_player_id != player_id and candidate.metadata_error is None:
                candidate.metadata_error = MalformedProtocolMessage(
                    "battle player metadata conflicts for one side"
                )
        elif isinstance(event, GameTypeDeclared):
            if candidate.game_type is None:
                candidate.game_type = event.game_type
            elif candidate.game_type != event.game_type and candidate.metadata_error is None:
                candidate.metadata_error = MalformedProtocolMessage(
                    "battle game type metadata conflicts"
                )
        elif isinstance(event, GenerationDeclared):
            if candidate.generation is None:
                candidate.generation = event.generation
            elif candidate.generation != event.generation and candidate.metadata_error is None:
                candidate.metadata_error = MalformedProtocolMessage(
                    "battle generation metadata conflicts"
                )
        elif isinstance(event, TierDeclared):
            if candidate.tier is None:
                candidate.tier = event.tier
            elif candidate.tier != event.tier and candidate.metadata_error is None:
                candidate.metadata_error = MalformedProtocolMessage(
                    "battle tier metadata conflicts"
                )

    def _validate_handoff_line(self, candidate: _RoomCandidate, line: RoomLine) -> None:
        candidate.lines.append(line)
        self._read_candidate_metadata(candidate, line)
        self._raise_for_exact_candidate_failure(candidate)

    def _raise_for_exact_candidate_failure(self, candidate: _RoomCandidate) -> None:
        if not self._has_exact_player_pair(candidate):
            return
        if candidate.metadata_error is not None:
            raise candidate.metadata_error
        if candidate.game_type is not None and candidate.game_type != _GAME_TYPE:
            raise UnknownProtocolEvent("matching player pair has an unsupported game type")
        if candidate.generation is not None and candidate.generation != _GENERATION:
            raise UnknownProtocolEvent("matching player pair has an unsupported generation")
        if candidate.tier is not None and candidate.tier != _TIER:
            raise UnknownProtocolEvent("matching player pair has an unsupported tier")

    def _is_matching_candidate(self, candidate: _RoomCandidate) -> bool:
        return (
            candidate.battle_initialized
            and self._has_exact_player_pair(candidate)
            and candidate.game_type == _GAME_TYPE
            and candidate.generation == _GENERATION
            and candidate.tier == _TIER
        )

    def _has_exact_player_pair(self, candidate: _RoomCandidate) -> bool:
        return set(candidate.players) == {"p1", "p2"} and set(candidate.players.values()) == {
            self._our_user_id,
            self._opponent_user_id,
        }


def _to_id(value: str) -> str:
    return "".join(
        character for character in value.lower() if character.isascii() and character.isalnum()
    )


def _global_wire_type(payload: str) -> str | None:
    if not payload.startswith("|"):
        return None
    parts = payload.split("|", 2)
    if len(parts) < 2:
        return None
    return parts[1]


def _read_existing_room_ids(payload: str) -> set[str]:
    try:
        decoded = json.loads(payload.removeprefix("|updatesearch|"))
    except json.JSONDecodeError as exc:
        raise MalformedProtocolMessage(f"invalid updatesearch json: {exc}") from exc
    if not isinstance(decoded, dict):
        raise MalformedProtocolMessage("updatesearch json must be an object")
    data = cast(dict[str, Any], decoded)
    if "games" not in data:
        raise MalformedProtocolMessage("updatesearch.games is required")
    games = data.get("games")
    if games is None:
        return set()
    if not isinstance(games, dict):
        raise MalformedProtocolMessage("updatesearch.games must be an object or null")

    room_ids: set[str] = set()
    for room_id, title in cast(dict[str, Any], games).items():
        if room_id == "" or not isinstance(title, str):
            raise MalformedProtocolMessage(
                "updatesearch.games must map nonempty room IDs to string titles"
            )
        room_ids.add(room_id)
    return room_ids
