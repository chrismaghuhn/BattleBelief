from __future__ import annotations

import pytest

from battlebelief_lab.evaluation.matchup_blocks import BaseMatchupKey
from battlebelief_lab.evaluation.schedule import (
    SideAssignment,
    build_schedule,
)

REGISTRATION = "sha256:" + "b" * 64
MASTER_SEED = "0123456789abcdef" * 4


def _key(team: str) -> BaseMatchupKey:
    return BaseMatchupKey(
        hero_team=team,
        opponent_team="opponent-alpha",
        opponent_archetype="balance",
        opponent_policy_checkpoint="heuristic-v0",
        schedule_block="block-0",
    )


def test_schedule_is_deterministic_and_balanced_for_even_repetitions() -> None:
    schedule = build_schedule(
        registration_digest=REGISTRATION,
        master_seed=MASTER_SEED,
        matchup_keys=[_key("hero-alpha")],
        repetitions=4,
    )
    repeated = build_schedule(
        registration_digest=REGISTRATION,
        master_seed=MASTER_SEED,
        matchup_keys=[_key("hero-alpha")],
        repetitions=4,
    )

    assert schedule == repeated
    assert schedule.digest == repeated.digest
    assert [row.side_assignment for row in schedule.rows].count(SideAssignment.P1) == 2
    assert [row.side_assignment for row in schedule.rows].count(SideAssignment.P2) == 2
    assert len({row.row_id for row in schedule.rows}) == 4


def test_exact_balance_rejects_odd_repetition_count() -> None:
    with pytest.raises(ValueError, match="even"):
        build_schedule(
            registration_digest=REGISTRATION,
            master_seed=MASTER_SEED,
            matchup_keys=[_key("hero-alpha")],
            repetitions=3,
            require_exact_balance=True,
        )


def test_reordering_matchup_inputs_does_not_change_schedule_identity() -> None:
    first = build_schedule(
        registration_digest=REGISTRATION,
        master_seed=MASTER_SEED,
        matchup_keys=[_key("hero-beta"), _key("hero-alpha")],
        repetitions=2,
    )
    second = build_schedule(
        registration_digest=REGISTRATION,
        master_seed=MASTER_SEED,
        matchup_keys=[_key("hero-alpha"), _key("hero-beta")],
        repetitions=2,
    )
    assert first == second
