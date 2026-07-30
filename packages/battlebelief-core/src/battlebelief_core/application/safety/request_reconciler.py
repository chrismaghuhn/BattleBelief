from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from battlebelief_core.domain.actions.decision_request import DecisionRequest, RequestKind
from battlebelief_core.domain.state.observed_state import ObservedState

_GEN9 = 9
_SINGLES = "singles"
_GEN9OU_NORMALIZED = "gen9ou"

_TIER_ALIASES = {
    "[gen 9] ou",
    "gen9ou",
    "gen 9 ou",
}


def _tier_matches(tier: str | None) -> bool:
    if tier is None:
        return False
    return tier.lower().replace(" ", "").replace("[", "").replace("]", "") in {
        "gen9ou",
    }


class ReconciliationStatus(StrEnum):
    ACCEPT = "accept"
    PENDING_PUBLIC_STATE = "pending_public_state"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    status: ReconciliationStatus
    reason: str


class RequestReconciler:
    @staticmethod
    def reconcile(
        room_id: str,
        request: DecisionRequest,
        state: ObservedState,
        latest_rqid: int | None,
    ) -> ReconciliationResult:
        # Room must match
        if request.identity.room_id != room_id:
            return ReconciliationResult(
                status=ReconciliationStatus.REJECT,
                reason=f"room mismatch: {request.identity.room_id!r} != {room_id!r}",
            )

        # rqid must not be older than latest accepted
        if latest_rqid is not None and request.identity.rqid < latest_rqid:
            return ReconciliationResult(
                status=ReconciliationStatus.REJECT,
                reason=f"stale rqid {request.identity.rqid} < accepted {latest_rqid}",
            )

        # own side must be known
        if state.our_side is None:
            return ReconciliationResult(
                status=ReconciliationStatus.PENDING_PUBLIC_STATE,
                reason="our_side not yet known",
            )

        # side must match
        if request.side_id != state.our_side:
            return ReconciliationResult(
                status=ReconciliationStatus.REJECT,
                reason=f"side mismatch: request={request.side_id!r}, state={state.our_side!r}",
            )

        # generation must be known and == 9
        if state.generation is None:
            return ReconciliationResult(
                status=ReconciliationStatus.PENDING_PUBLIC_STATE,
                reason="generation not yet known",
            )
        if state.generation != _GEN9:
            return ReconciliationResult(
                status=ReconciliationStatus.REJECT,
                reason=f"generation mismatch: {state.generation} != 9",
            )

        # game_type must be known and == singles
        if state.game_type is None:
            return ReconciliationResult(
                status=ReconciliationStatus.PENDING_PUBLIC_STATE,
                reason="game_type not yet known",
            )
        if state.game_type.lower() != _SINGLES:
            return ReconciliationResult(
                status=ReconciliationStatus.REJECT,
                reason=f"game_type not singles: {state.game_type!r}",
            )

        # tier must be known and gen9ou
        if state.tier is None:
            return ReconciliationResult(
                status=ReconciliationStatus.PENDING_PUBLIC_STATE,
                reason="tier not yet known",
            )
        if not _tier_matches(state.tier):
            return ReconciliationResult(
                status=ReconciliationStatus.REJECT,
                reason=f"tier not gen9ou: {state.tier!r}",
            )

        # for move/forced-switch/revival requests, active identity must be known
        _needs_active = {RequestKind.MOVE, RequestKind.FORCED_SWITCH, RequestKind.REVIVAL}
        if request.kind in _needs_active:
            our_side_view = state.side(state.our_side)
            active_pv = next((p for p in our_side_view.pokemon if p.active), None)
            if active_pv is None and request.kind == RequestKind.MOVE:
                return ReconciliationResult(
                    status=ReconciliationStatus.PENDING_PUBLIC_STATE,
                    reason="active pokemon not yet known from public state",
                )

        return ReconciliationResult(status=ReconciliationStatus.ACCEPT, reason="ok")
