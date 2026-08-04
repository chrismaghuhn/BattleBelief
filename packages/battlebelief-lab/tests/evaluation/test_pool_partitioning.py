from __future__ import annotations

import pytest

from battlebelief_lab.evaluation.pool_partitioning import (
    PoolName,
    ProtectedPoolError,
    create_pool_partition,
)


def test_pool_partition_is_disjoint_and_protected_pools_are_closed() -> None:
    partition = create_pool_partition(
        (
            ("cluster-a", PoolName.DEVELOPMENT),
            ("cluster-b", PoolName.DEVELOPMENT),
            ("cluster-c", PoolName.SELECTION),
        )
    )

    assert partition.access[PoolName.DEVELOPMENT] == "available"
    assert partition.access[PoolName.SELECTION] == "unopened"
    assert partition.access[PoolName.POWER_PILOT] == "unopened"
    assert partition.access[PoolName.RELEASE_HOLDOUT] == "unopened"
    with pytest.raises(ProtectedPoolError):
        partition.open(PoolName.SELECTION)


def test_pool_partition_rejects_duplicate_cluster_ownership() -> None:
    with pytest.raises(ValueError, match="cluster"):
        create_pool_partition(
            (
                ("cluster-a", PoolName.DEVELOPMENT),
                ("cluster-a", PoolName.POWER_PILOT),
            )
        )


def test_pool_partition_digest_is_independent_of_input_order() -> None:
    first = create_pool_partition(
        (("cluster-b", PoolName.DEVELOPMENT), ("cluster-a", PoolName.DEVELOPMENT))
    )
    second = create_pool_partition(
        (("cluster-a", PoolName.DEVELOPMENT), ("cluster-b", PoolName.DEVELOPMENT))
    )
    assert first == second
    assert first.digest == second.digest
