from __future__ import annotations

from dataclasses import replace

import pytest

from battlebelief_core.canonicalization import manifest_digest
from battlebelief_lab.evaluation.matchup_blocks import BaseMatchupKey
from battlebelief_lab.evaluation.schedule import (
    Schedule,
    ScheduleRow,
    SideAssignment,
    build_schedule,
    derive_schedule_row_id,
)
from battlebelief_lab.evaluation.seed_families import SeedNamespace, derive_seed

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


def test_schedule_row_rejects_fabricated_identity_outside_factory() -> None:
    schedule = build_schedule(
        registration_digest=REGISTRATION,
        master_seed=MASTER_SEED,
        matchup_keys=[_key("hero-alpha")],
        repetitions=2,
    )
    row = schedule.rows[0]
    with pytest.raises(ValueError, match="row_id"):
        ScheduleRow(
            row_id="sha256:" + "f" * 64,
            base_matchup_id=row.base_matchup_id,
            side_assignment=row.side_assignment,
            schedule_block=row.schedule_block,
            seed_family=row.seed_family,
            repetition_index=row.repetition_index,
        )


def test_schedule_rejects_empty_and_noncontiguous_repetition_groups() -> None:
    with pytest.raises(ValueError, match="at least one schedule row"):
        Schedule(rows=(), digest=manifest_digest([]))

    schedule = build_schedule(
        registration_digest=REGISTRATION,
        master_seed=MASTER_SEED,
        matchup_keys=[_key("hero-alpha")],
        repetitions=2,
    )
    second = schedule.rows[1]
    noncontiguous_repetition_index = 2
    noncontiguous = replace(
        second,
        repetition_index=noncontiguous_repetition_index,
        row_id=derive_schedule_row_id(
            base_matchup_id=second.base_matchup_id,
            side_assignment=second.side_assignment,
            schedule_block=second.schedule_block,
            seed_family=second.seed_family,
            repetition_index=noncontiguous_repetition_index,
        ),
    )
    with pytest.raises(ValueError, match="contiguous"):
        Schedule(
            rows=(schedule.rows[0], noncontiguous),
            digest=manifest_digest([schedule.rows[0].to_dict(), noncontiguous.to_dict()]),
        )


def test_schedule_rejects_unbalanced_direct_construction() -> None:
    schedule = build_schedule(
        registration_digest=REGISTRATION,
        master_seed=MASTER_SEED,
        matchup_keys=[_key("hero-alpha")],
        repetitions=2,
    )
    original = schedule.rows[1]
    changed = replace(
        original,
        side_assignment=SideAssignment.P1,
        row_id=derive_schedule_row_id(
            base_matchup_id=original.base_matchup_id,
            side_assignment=SideAssignment.P1,
            schedule_block=original.schedule_block,
            seed_family=original.seed_family,
            repetition_index=original.repetition_index,
        ),
    )
    with pytest.raises(ValueError, match="balanced"):
        Schedule(
            rows=(schedule.rows[0], changed),
            digest=manifest_digest([schedule.rows[0].to_dict(), changed.to_dict()]),
        )


def test_schedule_row_and_run_context_seed_family_must_match() -> None:
    from types import SimpleNamespace

    from battlebelief_lab.evaluation.measurement_runner import MeasurementRunner

    schedule = build_schedule(
        registration_digest=REGISTRATION,
        master_seed=MASTER_SEED,
        matchup_keys=[_key("hero-alpha")],
        repetitions=2,
    )
    ledger = SimpleNamespace(
        records=(),
        accepted_record_count=0,
        accepted_record_digests=(),
    )
    session = SimpleNamespace(trace_sink=ledger, failure_result=lambda error: None)
    with pytest.raises(ValueError, match="seed family"):
        MeasurementRunner(
            session=session,
            trace_sink=ledger,
            run_context=SimpleNamespace(
                run_scope=SimpleNamespace(
                    schedule_row_id=schedule.rows[0].row_id,
                    seed_family_digest=schedule.rows[1].seed_family.digest,
                )
            ),
            schedule_row=schedule.rows[0],
        )


def test_seed_and_schedule_vectors_are_frozen() -> None:
    key = _key("hero-alpha")
    assert (
        key.base_matchup_id
        == "sha256:7fecb7a996de736b7c4495013ccf4c49432610fc90e3363287baae04df40c1e1"
    )
    expected_seeds = {
        SeedNamespace.SEARCH: "ca0fb7c5264a4ad3f1f872cbe055e1f75dbdf7e8b9c37e423a4972d6a3d528aa",
        SeedNamespace.WORLD: "8837547df89634e6e3444c804cca0dea70cee74f2b652afaef03bb837f17a1f9",
        SeedNamespace.POLICY: "a6b51a293f73aafb8a9b5ab35dfbdc22c76355700c37a5540cdfe092e08c5f45",
        SeedNamespace.SIMULATOR: "55d83eca319176248cc4995b5c0e436a092f554d3e88f58dc4b4f7bdd3914f8a",
        SeedNamespace.SCHEDULE: "b2051414b4ad3225c6034efa7cd66d197dceda237f6fcc82c3de23909f46ae81",
        SeedNamespace.SIDE_ASSIGNMENT: "8c49b703474e6a3c18f50e4259b9f07a494a7b7aaccef50aa96a5b44e260aec0",
    }
    for namespace, expected in expected_seeds.items():
        assert (
            derive_seed(
                master_seed=MASTER_SEED,
                namespace=namespace,
                base_matchup_id=key.base_matchup_id,
                side_assignment="p1",
                repetition_index=0,
            )
            == expected
        )

    schedule = build_schedule(
        registration_digest=REGISTRATION,
        master_seed=MASTER_SEED,
        matchup_keys=[key],
        repetitions=2,
    )
    assert (
        schedule.digest == "sha256:b387f4746acd9175b394ad65c0c4963603bdf7aabd63bd84273f44015ea92ab7"
    )
    assert [row.row_id for row in schedule.rows] == [
        "sha256:c96aedef2b723c4b3669124a3964aa0d46e41a46034cedba8515d1459266cb59",
        "sha256:9724f816ff29e4801c77cf4264776e76d793cbb55ff7700beeaff2f6e7137ed0",
    ]
