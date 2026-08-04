"""Deterministic in-memory trace sink for approved measurement tests."""

from __future__ import annotations

from battlebelief_core.domain.records.decision_record import DecisionRecord


class InMemoryTraceSink:
    def __init__(self) -> None:
        self._records: list[DecisionRecord] = []

    @property
    def records(self) -> tuple[DecisionRecord, ...]:
        return tuple(self._records)

    def emit(self, record: DecisionRecord) -> None:
        self._records.append(record)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        return None


__all__ = ["InMemoryTraceSink"]
