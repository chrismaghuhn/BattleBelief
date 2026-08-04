"""Ports for recording validated public Decision Records."""

from __future__ import annotations

from typing import Protocol

from battlebelief_core.domain.records.decision_record import DecisionRecord


class TraceSink(Protocol):
    """Receive one finalized public Decision Record."""

    def emit(self, record: DecisionRecord) -> None:
        """Persist or retain one record without changing it."""


class ClosableTraceSink(TraceSink, Protocol):
    """Trace sink whose lifecycle is owned by a measurement runner."""

    def flush(self) -> None:
        """Flush all accepted records."""

    def close(self) -> None:
        """Close the underlying trace destination."""


class NullTraceSink:
    """Default no-op sink used by the public runtime path."""

    def emit(self, record: DecisionRecord) -> None:
        del record


__all__ = ["ClosableTraceSink", "NullTraceSink", "TraceSink"]
