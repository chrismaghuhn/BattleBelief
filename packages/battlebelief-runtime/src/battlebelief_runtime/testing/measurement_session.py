"""Narrow, dependency-injected seam for Lab measurement runs."""

from __future__ import annotations

from battlebelief_core.domain.records.decision_record import MeasurementRunContext
from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_core.errors import TraceSinkFailure
from battlebelief_core.ports import ClosableTraceSink
from battlebelief_runtime.adapters.showdown_client.types import BattleConnection
from battlebelief_runtime.composition.battle_session import (
    BattleSession,
    BattleSessionResult,
    DecisionPolicy,
)


class MeasurementSession:
    """Compose one synthetic BattleSession without exposing composition to Lab."""

    def __init__(
        self,
        *,
        connection: BattleConnection,
        room_id: str,
        our_user_id: str,
        decision_record_context: MeasurementRunContext,
        trace_sink: ClosableTraceSink,
        policy: DecisionPolicy | None = None,
        initial_state: ObservedState | None = None,
    ) -> None:
        self._trace_sink = trace_sink
        self._session = BattleSession(
            connection=connection,
            room_id=room_id,
            our_user_id=our_user_id,
            policy=policy,
            initial_state=initial_state,
            trace_sink=trace_sink,
            decision_record_context=decision_record_context,
        )

    async def run(self) -> BattleSessionResult:
        return await self._session.run()

    @property
    def trace_sink(self) -> ClosableTraceSink:
        return self._trace_sink

    def failure_result(self, error: BaseException) -> BattleSessionResult:
        return self._session.result_snapshot(primary_error=error)

    def flush_trace(self) -> None:
        flush = getattr(self._trace_sink, "flush", None)
        if flush is not None:
            try:
                flush()
            except Exception as exc:
                raise TraceSinkFailure() from exc

    def close_trace(self) -> None:
        close = getattr(self._trace_sink, "close", None)
        if close is not None:
            try:
                close()
            except Exception as exc:
                raise TraceSinkFailure() from exc


__all__ = ["MeasurementSession"]
