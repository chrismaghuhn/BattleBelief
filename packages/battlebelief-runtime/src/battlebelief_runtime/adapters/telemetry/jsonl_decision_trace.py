"""Deterministic UTF-8 JSONL Decision-Record sink."""

from __future__ import annotations

from typing import BinaryIO

from battlebelief_core.domain.records.decision_record import DecisionRecord


class JsonlDecisionTrace:
    """Write exactly one canonical record line per successful emit."""

    def __init__(self, stream: BinaryIO) -> None:
        self._stream = stream
        self._records: list[DecisionRecord] = []

    @property
    def records(self) -> tuple[DecisionRecord, ...]:
        return tuple(self._records)

    def emit(self, record: DecisionRecord) -> None:
        line = record.canonical_envelope_bytes() + b"\n"
        self._stream.write(line)
        self._stream.flush()
        self._records.append(record)

    def flush(self) -> None:
        self._stream.flush()

    def close(self) -> None:
        self._stream.close()


__all__ = ["JsonlDecisionTrace"]
