"""Dependency-injection ports owned by the pure core package."""

from battlebelief_core.ports.trace_sink import ClosableTraceSink, NullTraceSink, TraceSink

__all__ = ["ClosableTraceSink", "NullTraceSink", "TraceSink"]
