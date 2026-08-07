"""Canonical, sanitized report rendering for differential fixture outcomes."""

from __future__ import annotations

from battlebelief_core.canonicalization import canonicalize
from battlebelief_lab.differential.runner import FixtureResult


def render_fixture_result(result: FixtureResult) -> bytes:
    """Serialize one already-sanitized result as deterministic RFC8785 JSON bytes."""

    if not isinstance(result, FixtureResult):
        raise TypeError("fixture report requires a FixtureResult")
    return canonicalize(result.to_dict())


__all__ = ["render_fixture_result"]
