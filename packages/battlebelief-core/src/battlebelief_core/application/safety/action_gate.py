from __future__ import annotations

from battlebelief_core.domain.actions.submission import (
    BattleSubmission,
    RequestIdentity,
    SafeSubmissionSet,
)
from battlebelief_core.errors import LocalActionGateRejection, StaleRequestIdentity


class ActionSafetyGate:
    @staticmethod
    def authorize(
        candidate: BattleSubmission,
        candidate_request: RequestIdentity,
        latest: SafeSubmissionSet,
    ) -> BattleSubmission:
        if candidate_request != latest.request_identity:
            raise StaleRequestIdentity(
                f"candidate rqid={candidate_request.rqid} != latest rqid={latest.request_identity.rqid}"
            )
        if not latest.contains(candidate):
            raise LocalActionGateRejection(f"submission not in SafeSubmissionSet: {candidate}")
        return candidate
