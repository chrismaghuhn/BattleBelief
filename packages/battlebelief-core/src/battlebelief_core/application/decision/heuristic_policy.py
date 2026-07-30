from __future__ import annotations

from battlebelief_core.domain.actions.decision_request import DecisionRequest
from battlebelief_core.domain.actions.submission import ActionKind, BattleSubmission
from battlebelief_core.errors import NoLegalActionError

# Priority order (lowest index = highest priority):
# 1. first normal Move (no tera)
# 2. first Revival slot
# 3. first Switch (forced or voluntary)
# 4. first Team order
# 5. first Tera Move
# 6. default


def _priority(sub: BattleSubmission) -> int:
    if sub.kind == ActionKind.MOVE and not sub.terastallize:
        return 0
    if sub.kind == ActionKind.REVIVE:
        return 1
    if sub.kind == ActionKind.SWITCH:
        return 2
    if sub.kind == ActionKind.TEAM:
        return 3
    if sub.kind == ActionKind.MOVE and sub.terastallize:
        return 4
    # DEFAULT
    return 5


class HeuristicPolicy:
    @staticmethod
    def select(request: DecisionRequest) -> BattleSubmission:
        subs = request.safe_submissions.submissions
        if not subs:
            raise NoLegalActionError("SafeSubmissionSet is empty — no legal action available")
        return min(subs, key=_priority)
