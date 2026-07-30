from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from battlebelief_core.domain.actions.decision_request import DecisionRequest, RequestKind
from battlebelief_core.domain.actions.submission import ActionKind
from battlebelief_core.domain.state.observed_state import ObservedState

_GEN9 = 9
_SINGLES = "singles"
_GEN9OU_NORMALIZED = "gen9ou"

_TIER_ALIASES = {
    "[gen 9] ou",
    "gen9ou",
    "gen 9 ou",
}

_ALLOWED_KINDS: dict[RequestKind, frozenset[ActionKind]] = {
    RequestKind.MOVE: frozenset({ActionKind.MOVE, ActionKind.SWITCH, ActionKind.DEFAULT}),
    RequestKind.FORCED_SWITCH: frozenset({ActionKind.SWITCH, ActionKind.DEFAULT}),
    RequestKind.REVIVAL: frozenset({ActionKind.REVIVE, ActionKind.DEFAULT}),
    RequestKind.TEAM_PREVIEW: frozenset({ActionKind.TEAM, ActionKind.DEFAULT}),
    RequestKind.WAIT: frozenset(),
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

        if request.identity != request.safe_submissions.request_identity:
            return ReconciliationResult(
                status=ReconciliationStatus.REJECT,
                reason="request identity does not match SafeSubmissionSet identity",
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

        if not 1 <= request.team_member_count <= 6:
            return ReconciliationResult(
                status=ReconciliationStatus.REJECT,
                reason=f"request team size out of range: {request.team_member_count}",
            )

        own_side = state.side(state.our_side)
        if own_side.team_size is not None and request.team_member_count != own_side.team_size:
            return ReconciliationResult(
                status=ReconciliationStatus.REJECT,
                reason=(
                    f"team size mismatch: request={request.team_member_count}, "
                    f"state={own_side.team_size}"
                ),
            )

        submissions = request.safe_submissions.submissions
        if request.kind == RequestKind.WAIT:
            if submissions:
                return ReconciliationResult(
                    status=ReconciliationStatus.REJECT,
                    reason="wait request must not contain submissions",
                )
        elif not any(sub.kind == ActionKind.DEFAULT for sub in submissions):
            return ReconciliationResult(
                status=ReconciliationStatus.REJECT,
                reason="decision request must contain default",
            )

        # Every submission kind must be legal for this request kind — the legal-action-safety
        # contract requires checking team/slot/switch/tera relation before every dispatch.
        allowed_kinds = _ALLOWED_KINDS[request.kind]
        for sub in submissions:
            if sub.kind not in allowed_kinds:
                return ReconciliationResult(
                    status=ReconciliationStatus.REJECT,
                    reason=(
                        f"submission kind {sub.kind!r} is not allowed for request kind "
                        f"{request.kind!r}"
                    ),
                )

        if request.kind == RequestKind.TEAM_PREVIEW:
            expected_order = frozenset(range(1, request.team_member_count + 1))
            for sub in submissions:
                if sub.kind == ActionKind.TEAM and frozenset(sub.team_order) != expected_order:
                    return ReconciliationResult(
                        status=ReconciliationStatus.REJECT,
                        reason=(
                            f"team_order {sub.team_order} is not a permutation of "
                            f"1..{request.team_member_count}"
                        ),
                    )

        # For move/forced-switch/revival requests, active identity must be known.
        _needs_active = {RequestKind.MOVE, RequestKind.FORCED_SWITCH, RequestKind.REVIVAL}
        if request.kind in _needs_active:
            active_pv = next((p for p in own_side.pokemon if p.active), None)
            if active_pv is None:
                return ReconciliationResult(
                    status=ReconciliationStatus.PENDING_PUBLIC_STATE,
                    reason="active pokemon not yet known from public state",
                )
            if request.active_identity is None:
                return ReconciliationResult(
                    status=ReconciliationStatus.REJECT,
                    reason="decision request has no active identity",
                )
            if request.active_identity != active_pv.nickname:
                return ReconciliationResult(
                    status=ReconciliationStatus.REJECT,
                    reason=(
                        f"active identity mismatch: request={request.active_identity!r}, "
                        f"state={active_pv.nickname!r}"
                    ),
                )

        return ReconciliationResult(status=ReconciliationStatus.ACCEPT, reason="ok")
