from __future__ import annotations


class ReducerInvariantError(RuntimeError):
    code = "reducer_invariant_failure"


class StaleRequestIdentity(RuntimeError):
    code = "stale_rqid"


class LocalActionGateRejection(RuntimeError):
    code = "local_action_gate_rejection"


class NoLegalActionError(RuntimeError):
    code = "no_legal_action_available"


class TraceSinkFailure(RuntimeError):
    """A trace sink failed without exposing its implementation details."""

    code = "trace_sink_failure"
