"""Fail-closed logical pool partitioning for M1.5."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from battlebelief_core.canonicalization import manifest_digest


class PoolName(StrEnum):
    DEVELOPMENT = "development"
    SELECTION = "selection"
    POWER_PILOT = "power_pilot"
    RELEASE_HOLDOUT = "release_holdout"


class ProtectedPoolError(RuntimeError):
    """Raised when M1.5 tries to open a protected evaluation pool."""


@dataclass(frozen=True, slots=True)
class PoolPartition:
    assignments: tuple[tuple[str, PoolName], ...]
    access: Mapping[PoolName, str]

    def __post_init__(self) -> None:
        assignments = tuple(self.assignments)
        if any(
            not isinstance(item, tuple)
            or len(item) != 2
            or type(item[0]) is not str
            or not item[0]
            or not isinstance(item[1], PoolName)
            for item in assignments
        ):
            raise ValueError("assignments must contain non-empty cluster IDs and PoolNames")
        assignments = tuple(sorted(assignments, key=lambda item: (item[0], item[1].value)))
        if len({cluster_id for cluster_id, _ in assignments}) != len(assignments):
            raise ValueError("cluster has more than one pool owner")
        object.__setattr__(self, "assignments", assignments)
        expected = {
            PoolName.DEVELOPMENT: "available",
            PoolName.SELECTION: "unopened",
            PoolName.POWER_PILOT: "unopened",
            PoolName.RELEASE_HOLDOUT: "unopened",
        }
        if not isinstance(self.access, Mapping) or dict(self.access) != expected:
            raise ValueError("M1.5 pool access state is not fail-closed")
        object.__setattr__(self, "access", MappingProxyType(dict(expected)))

    @property
    def digest(self) -> str:
        return manifest_digest(
            {
                "assignments": [
                    {"cluster_id": cluster_id, "pool": pool.value}
                    for cluster_id, pool in self.assignments
                ],
                "access": {pool.value: state for pool, state in self.access.items()},
            }
        )

    def open(self, pool: PoolName) -> None:
        if self.access.get(pool) != "available":
            raise ProtectedPoolError(f"pool {pool.value} is unopened in M1.5")


def create_pool_partition(
    assignments: Iterable[tuple[str, PoolName]],
) -> PoolPartition:
    ordered = tuple(assignments)
    if len({cluster_id for cluster_id, _ in ordered}) != len(ordered):
        raise ValueError("cluster has more than one pool owner")
    ordered = tuple(sorted(ordered, key=lambda item: (item[0], item[1].value)))
    for cluster_id, pool in ordered:
        if type(cluster_id) is not str or not cluster_id:
            raise ValueError("cluster IDs must be non-empty strings")
        if not isinstance(pool, PoolName):
            raise ValueError("pool must be a PoolName")
    access = MappingProxyType(
        {
            PoolName.DEVELOPMENT: "available",
            PoolName.SELECTION: "unopened",
            PoolName.POWER_PILOT: "unopened",
            PoolName.RELEASE_HOLDOUT: "unopened",
        }
    )
    return PoolPartition(assignments=ordered, access=access)


__all__ = ["PoolName", "PoolPartition", "ProtectedPoolError", "create_pool_partition"]
