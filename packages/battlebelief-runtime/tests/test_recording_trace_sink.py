from __future__ import annotations

from types import SimpleNamespace

import pytest

from battlebelief_runtime.testing import RecordingTraceSink


class _Delegate:
    def __init__(self, *, fail: bool = False) -> None:
        self.records: list[object] = []
        self.fail = fail
        self.emit_count = 0

    def emit(self, record: object) -> None:
        self.emit_count += 1
        if self.fail:
            raise OSError("private sink detail")
        self.records.append(record)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        return None


def test_recording_trace_sink_ledger_is_committed_after_delegate_acceptance() -> None:
    delegate = _Delegate()
    sink = RecordingTraceSink(delegate)  # type: ignore[arg-type]
    first = SimpleNamespace(record_digest="sha256:" + "a" * 64)
    sink.emit(first)  # type: ignore[arg-type]

    assert sink.accepted_record_count == 1
    assert sink.accepted_record_digests == (first.record_digest,)
    assert sink.records == (first,)


def test_recording_trace_sink_does_not_ledger_rejected_records() -> None:
    sink = RecordingTraceSink(_Delegate(fail=True))  # type: ignore[arg-type]
    with pytest.raises(OSError, match="private sink detail"):
        sink.emit(SimpleNamespace(record_digest="sha256:" + "b" * 64))  # type: ignore[arg-type]
    assert sink.accepted_record_count == 0
    assert sink.records == ()


def test_recording_trace_sink_keeps_accepted_prefix_when_second_emit_fails() -> None:
    delegate = _Delegate()
    sink = RecordingTraceSink(delegate)  # type: ignore[arg-type]
    first = SimpleNamespace(record_digest="sha256:" + "a" * 64)
    second = SimpleNamespace(record_digest="sha256:" + "b" * 64)
    sink.emit(first)  # type: ignore[arg-type]
    delegate.fail = True

    with pytest.raises(OSError, match="private sink detail"):
        sink.emit(second)  # type: ignore[arg-type]

    assert sink.accepted_record_count == 1
    assert sink.accepted_record_digests == (first.record_digest,)
    assert sink.records == (first,)
