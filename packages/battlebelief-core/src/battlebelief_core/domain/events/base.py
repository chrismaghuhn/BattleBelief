from __future__ import annotations


class BattleEvent:
    """Marker base for all canonical Core battle events."""

    __slots__ = ()
    # Contract: every concrete subclass is @dataclass(frozen=True, slots=True)
    # and provides event_index. Declared here so the reducer can read it
    # before any isinstance narrowing.
    event_index: int
