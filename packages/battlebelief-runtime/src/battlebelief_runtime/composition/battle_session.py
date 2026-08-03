from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from battlebelief_core.application.decision.heuristic_policy import HeuristicPolicy
from battlebelief_core.application.observation.reducer import ObservationReducer
from battlebelief_core.application.safety.action_gate import ActionSafetyGate
from battlebelief_core.application.safety.request_reconciler import (
    ReconciliationStatus,
    RequestReconciler,
)
from battlebelief_core.domain.actions.decision_request import DecisionRequest
from battlebelief_core.domain.actions.submission import (
    ActionProvenance,
    BattleSubmission,
    RequestIdentity,
)
from battlebelief_core.domain.events.metadata import (
    GameTypeDeclared,
    GenerationDeclared,
    PlayerDeclared,
    TierDeclared,
)
from battlebelief_core.domain.events.pokemon import PokemonDragged, PokemonSwitched
from battlebelief_core.domain.events.progress import (
    BattleStarted,
    BattleTied,
    BattleWon,
    TurnStarted,
)
from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_core.errors import ReducerInvariantError, StaleRequestIdentity
from battlebelief_runtime.adapters.showdown_client.types import BattleConnection
from battlebelief_runtime.adapters.showdown_protocol.command_encoder import encode_submission
from battlebelief_runtime.adapters.showdown_protocol.frame_decoder import RoomLine
from battlebelief_runtime.adapters.showdown_protocol.parser import (
    parse_battle_line,
    parse_inactive_line,
)
from battlebelief_runtime.adapters.showdown_protocol.request_reader import read_request
from battlebelief_runtime.adapters.showdown_protocol.room_payload_classifier import (
    RoomPayloadKind,
    classify_room_payload,
)
from battlebelief_runtime.errors.actions import ServerInvalidChoice, ServerUnavailableChoice
from battlebelief_runtime.errors.protocol import (
    MalformedProtocolMessage,
    ReducerInvariantFailure,
    RequestStateReconciliationMismatch,
    UnknownProtocolEvent,
)


class DecisionPolicy(Protocol):
    def select(self, request: DecisionRequest) -> BattleSubmission:
        """Select one candidate from the request's safe submission set."""


@dataclass(frozen=True, slots=True)
class BattleSessionResult:
    state: ObservedState
    primary_error: BaseException | None
    room_control_or_chat_count: int
    explicit_request_submissions: int
    default_submissions: int


_RETRY_EVENTS = (
    BattleStarted,
    GameTypeDeclared,
    GenerationDeclared,
    PlayerDeclared,
    TierDeclared,
    PokemonDragged,
    PokemonSwitched,
)


class BattleSession:
    """Run one room-scoped, request-driven battle session."""

    def __init__(
        self,
        *,
        connection: BattleConnection,
        room_id: str,
        our_user_id: str,
        policy: DecisionPolicy | None = None,
        initial_state: ObservedState | None = None,
    ) -> None:
        self._connection = connection
        self._room_id = room_id
        self._state = initial_state or ObservedState.initial(our_user_id)
        self._policy = policy or HeuristicPolicy()
        self._pending_request: DecisionRequest | None = None
        self._latest_request: RequestIdentity | None = None
        self._submitted_request: RequestIdentity | None = None
        self._primary_error: BaseException | None = None
        self._done = False
        self._room_control_or_chat_count = 0
        self._explicit_request_submissions = 0
        self._default_submissions = 0

    async def run(self) -> BattleSessionResult:
        try:
            async for line in self._connection.lines():
                if self._done:
                    break
                if line.room_id != self._room_id:
                    continue
                await self._process_line(line)
                if self._done:
                    break
        except Exception as exc:
            self._abort(exc)

        return BattleSessionResult(
            state=self._state,
            primary_error=self._primary_error,
            room_control_or_chat_count=self._room_control_or_chat_count,
            explicit_request_submissions=self._explicit_request_submissions,
            default_submissions=self._default_submissions,
        )

    async def _process_line(self, line: RoomLine) -> None:
        classified = classify_room_payload(line.payload)
        if classified.kind == RoomPayloadKind.BATTLE_EVENT:
            await self._process_battle_event(classified.payload)
            return
        if classified.kind == RoomPayloadKind.DECISION_REQUEST:
            await self._process_request(classified.payload)
            return
        if classified.kind == RoomPayloadKind.BATTLE_ERROR:
            self._process_battle_error(classified.payload)
            return
        if classified.kind == RoomPayloadKind.TIMER_MESSAGE:
            self._process_timer(classified.payload)
            return
        if classified.kind == RoomPayloadKind.ROOM_CONTROL_OR_CHAT:
            self._room_control_or_chat_count += 1
            return
        raise UnknownProtocolEvent(f"unknown room payload: {classified.payload!r}")

    async def _process_battle_event(self, payload: str) -> None:
        event_index = self._state.event_index + 1
        try:
            event = parse_battle_line(payload, event_index, room_id=self._room_id)
            self._state = ObservationReducer.reduce(self._state, event)
        except ReducerInvariantError as exc:
            raise ReducerInvariantFailure(str(exc)) from exc

        if isinstance(event, (BattleWon, BattleTied)):
            self._pending_request = None
            self._done = True
            return

        if isinstance(event, TurnStarted) and self._pending_request is not None:
            await self._retry_pending(
                f"pending request unresolved before turn {event.turn}", strict=True
            )
        elif isinstance(event, _RETRY_EVENTS) and self._pending_request is not None:
            strict = isinstance(event, BattleStarted)
            await self._retry_pending("pending request did not reconcile", strict=strict)

    def _process_timer(self, payload: str) -> None:
        event_index = self._state.event_index + 1
        try:
            event = parse_inactive_line(payload, event_index)
            self._state = ObservationReducer.reduce(self._state, event)
        except ReducerInvariantError as exc:
            raise ReducerInvariantFailure(str(exc)) from exc

    def _process_battle_error(self, payload: str) -> None:
        if payload.startswith("|error|[Invalid choice]"):
            raise ServerInvalidChoice(payload)
        if payload.startswith("|error|[Unavailable choice]"):
            raise ServerUnavailableChoice(payload)
        raise MalformedProtocolMessage(f"unclassified battle error: {payload!r}")

    async def _process_request(self, payload: str) -> None:
        request = read_request(self._room_id, payload[len("|request|") :])
        if self._check_freshness(request.identity):
            return
        self._latest_request = request.identity
        self._pending_request = request
        await self._retry_pending("request received", strict=False)

    def _check_freshness(self, identity: RequestIdentity) -> bool:
        latest = self._latest_request
        if latest is None:
            return False
        if identity.rqid < latest.rqid:
            raise StaleRequestIdentity(
                f"request rqid={identity.rqid} is older than latest rqid={latest.rqid}"
            )
        if identity.rqid == latest.rqid:
            if identity.request_digest == latest.request_digest:
                return True
            raise RequestStateReconciliationMismatch(
                f"request rqid={identity.rqid} changed without a server error"
            )
        return False

    async def _retry_pending(self, reason: str, *, strict: bool) -> None:
        request = self._pending_request
        if request is None:
            return

        reconciliation = RequestReconciler.reconcile(
            room_id=self._room_id,
            request=request,
            state=self._state,
            latest_rqid=self._submitted_request.rqid if self._submitted_request else None,
        )
        if reconciliation.status == ReconciliationStatus.REJECT:
            raise RequestStateReconciliationMismatch(f"{reason}: {reconciliation.reason}")
        if reconciliation.status == ReconciliationStatus.PENDING_PUBLIC_STATE:
            active_identity_pending = reconciliation.reason == (
                "active pokemon not yet known from public state"
            )
            if strict or (self._state.battle_started and not active_identity_pending):
                raise RequestStateReconciliationMismatch(f"{reason}: {reconciliation.reason}")
            return

        await self._submit(request)

    async def _submit(self, request: DecisionRequest) -> None:
        if request.identity == self._submitted_request:
            self._pending_request = None
            return

        if request.kind.value == "wait":
            self._submitted_request = request.identity
            self._pending_request = None
            return

        candidate = self._policy.select(request)
        authorized = ActionSafetyGate.authorize(
            candidate,
            request.identity,
            request.safe_submissions,
        )
        command = f"/choose {encode_submission(authorized)}|{request.identity.rqid}"
        # The session is intentionally synchronous with respect to the fake
        # and real connection: identity is marked submitted only after send.
        await self._connection.send_room(self._room_id, command)
        if authorized.provenance == ActionProvenance.EXPLICIT_REQUEST:
            self._explicit_request_submissions += 1
        elif authorized.provenance == ActionProvenance.SERVER_DEFAULT:
            self._default_submissions += 1
        self._submitted_request = request.identity
        self._pending_request = None

    def _abort(self, error: BaseException) -> None:
        if self._primary_error is None:
            self._primary_error = error
        self._pending_request = None
        self._done = True
