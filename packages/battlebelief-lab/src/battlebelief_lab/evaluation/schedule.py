"""Deterministic, side-balanced schedule construction."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from battlebelief_core.canonicalization import canonicalize, manifest_digest
from battlebelief_lab.evaluation.matchup_blocks import BaseMatchupKey
from battlebelief_lab.evaluation.seed_families import SeedFamily, derive_seed_family

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class SideAssignment(StrEnum):
    P1 = "p1"
    P2 = "p2"


@dataclass(frozen=True, slots=True)
class ScheduleRow:
    row_id: str
    base_matchup_id: str
    side_assignment: SideAssignment
    schedule_block: str
    seed_family: SeedFamily
    repetition_index: int

    def to_dict(self) -> dict[str, object]:
        return {
            "row_id": self.row_id,
            "base_matchup_id": self.base_matchup_id,
            "side_assignment": self.side_assignment.value,
            "schedule_block": self.schedule_block,
            "seed_family": self.seed_family.to_dict(),
            "repetition_index": self.repetition_index,
        }


@dataclass(frozen=True, slots=True)
class Schedule:
    rows: tuple[ScheduleRow, ...]
    digest: str

    def __post_init__(self) -> None:
        expected = manifest_digest([row.to_dict() for row in self.rows])
        if self.digest != expected:
            raise ValueError("schedule digest does not match rows")


def _initial_side(registration_digest: str, base_matchup_id: str) -> int:
    return (
        hashlib.sha256(
            canonicalize(
                {
                    "registration_digest": registration_digest,
                    "base_matchup_id": base_matchup_id,
                }
            )
        ).digest()[0]
        & 1
    )


def _row_id(
    base_matchup_id: str,
    side_assignment: SideAssignment,
    schedule_block: str,
    seed_family: SeedFamily,
    repetition_index: int,
) -> str:
    return manifest_digest(
        {
            "base_matchup_id": base_matchup_id,
            "side_assignment": side_assignment.value,
            "schedule_block": schedule_block,
            "seed_family": seed_family.to_dict(),
            "repetition_index": repetition_index,
        }
    )


def build_schedule(
    *,
    registration_digest: str,
    master_seed: str,
    matchup_keys: Iterable[BaseMatchupKey],
    repetitions: int,
    require_exact_balance: bool = True,
) -> Schedule:
    """Materialize sorted matchup rows with deterministic alternating sides."""

    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("repetitions must be a positive integer")
    if require_exact_balance and repetitions % 2:
        raise ValueError("exact side balance requires an even repetition count")
    if type(registration_digest) is not str or not _DIGEST_RE.fullmatch(registration_digest):
        raise ValueError("registration_digest must be a sha256 digest")
    ordered = sorted(set(matchup_keys), key=lambda key: key.base_matchup_id)
    if not ordered:
        raise ValueError("at least one matchup key is required")

    rows: list[ScheduleRow] = []
    for key in ordered:
        base_id = key.base_matchup_id
        initial = _initial_side(registration_digest, base_id)
        for repetition_index in range(repetitions):
            side = SideAssignment.P1 if (initial + repetition_index) % 2 == 0 else SideAssignment.P2
            family = derive_seed_family(
                master_seed=master_seed,
                base_matchup_id=base_id,
                side_assignment=side.value,
                repetition_index=repetition_index,
            )
            row_id = _row_id(
                base_id,
                side,
                key.schedule_block,
                family,
                repetition_index,
            )
            rows.append(
                ScheduleRow(
                    row_id=row_id,
                    base_matchup_id=base_id,
                    side_assignment=side,
                    schedule_block=key.schedule_block,
                    seed_family=family,
                    repetition_index=repetition_index,
                )
            )
    rows_tuple = tuple(rows)
    return Schedule(rows=rows_tuple, digest=manifest_digest([row.to_dict() for row in rows_tuple]))


__all__ = ["Schedule", "ScheduleRow", "SideAssignment", "build_schedule"]
