"""Ports for recording validated public Decision Records."""

from __future__ import annotations

from typing import Protocol

from battlebelief_core.domain.records.decision_record import DecisionRecord


class TraceSink(Protocol):
    """Receive one finalized public Decision Record."""

    def emit(self, record: DecisionRecord) -> None:
        """Persist or retain one record without changing it."""


class NullTraceSink:
    """Default no-op sink used by the public runtime path."""

    def emit(self, record: DecisionRecord) -> None:
        del record


__all__ = ["NullTraceSink", "TraceSink"]
