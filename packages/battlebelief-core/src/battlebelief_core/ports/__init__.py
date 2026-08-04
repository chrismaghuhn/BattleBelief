"""Dependency-injection ports owned by the pure core package."""

from battlebelief_core.ports.trace_sink import NullTraceSink, TraceSink

__all__ = ["NullTraceSink", "TraceSink"]
