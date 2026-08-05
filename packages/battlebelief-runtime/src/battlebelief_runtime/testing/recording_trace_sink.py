"""Accepted-record ledger for deterministic Lab measurement runs."""

from __future__ import annotations

from battlebelief_core.domain.records.decision_record import DecisionRecord
from battlebelief_core.ports import ClosableTraceSink


class RecordingTraceSink:
    """Wrap a trace sink and retain only records it accepted successfully."""

    def __init__(self, delegate: ClosableTraceSink) -> None:
        self._delegate = delegate
        self._records: list[DecisionRecord] = []

    @property
    def records(self) -> tuple[DecisionRecord, ...]:
        return tuple(self._records)

    @property
    def accepted_record_count(self) -> int:
        return len(self._records)

    @property
    def accepted_record_digests(self) -> tuple[str, ...]:
        return tuple(record.record_digest for record in self._records)

    def emit(self, record: DecisionRecord) -> None:
        self._delegate.emit(record)
        self._records.append(record)

    def flush(self) -> None:
        self._delegate.flush()

    def close(self) -> None:
        self._delegate.close()


__all__ = ["RecordingTraceSink"]
