from __future__ import annotations

import pytest

from battlebelief_lab.evaluation.seed_families import (
    SEED_DERIVATION_ID,
    SeedNamespace,
    derive_seed,
    derive_seed_family,
)

MASTER_SEED = "0123456789abcdef" * 4
BASE_MATCHUP = "sha256:" + "a" * 64


def test_seed_family_is_stable_and_separates_namespaces() -> None:
    first = derive_seed_family(
        master_seed=MASTER_SEED,
        base_matchup_id=BASE_MATCHUP,
        side_assignment="p1",
        repetition_index=0,
    )
    second = derive_seed_family(
        master_seed=MASTER_SEED,
        base_matchup_id=BASE_MATCHUP,
        side_assignment="p1",
        repetition_index=0,
    )

    assert first == second
    assert first.derivation_id == SEED_DERIVATION_ID
    assert len(first.search_seed) == 64
    assert len({first.search_seed, first.world_seed, first.policy_seed}) == 3


def test_seed_derivation_rejects_ambiguous_inputs() -> None:
    with pytest.raises(ValueError, match="master_seed"):
        derive_seed(
            master_seed="not-hex",
            namespace=SeedNamespace.SEARCH,
            base_matchup_id=BASE_MATCHUP,
            side_assignment="p1",
            repetition_index=0,
        )

    with pytest.raises(ValueError, match="repetition_index"):
        derive_seed(
            master_seed=MASTER_SEED,
            namespace=SeedNamespace.SEARCH,
            base_matchup_id=BASE_MATCHUP,
            side_assignment="p1",
            repetition_index=-1,
        )
