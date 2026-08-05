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
_MAX_SAFE_INTEGER = 9_007_199_254_740_991


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

    def __post_init__(self) -> None:
        if type(self.row_id) is not str or not _DIGEST_RE.fullmatch(self.row_id):
            raise ValueError("row_id must be a sha256 digest")
        if type(self.base_matchup_id) is not str or not _DIGEST_RE.fullmatch(self.base_matchup_id):
            raise ValueError("base_matchup_id must be a sha256 digest")
        if not isinstance(self.side_assignment, SideAssignment):
            raise ValueError("side_assignment must be a SideAssignment")
        if type(self.schedule_block) is not str or not self.schedule_block:
            raise ValueError("schedule_block must be a non-empty string")
        if not isinstance(self.seed_family, SeedFamily):
            raise ValueError("seed_family must be a SeedFamily")
        if (
            type(self.repetition_index) is not int
            or not 0 <= self.repetition_index <= _MAX_SAFE_INTEGER
        ):
            raise ValueError("repetition_index must be a JCS-safe non-negative integer")
        if self.row_id != derive_schedule_row_id(
            base_matchup_id=self.base_matchup_id,
            side_assignment=self.side_assignment,
            schedule_block=self.schedule_block,
            seed_family=self.seed_family,
            repetition_index=self.repetition_index,
        ):
            raise ValueError("row_id does not match schedule-row contents")

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
        if type(self.rows) is not tuple or any(
            not isinstance(row, ScheduleRow) for row in self.rows
        ):
            raise ValueError("schedule rows must be a tuple of ScheduleRow values")
        if not self.rows:
            raise ValueError("schedule requires at least one schedule row")
        if len({row.row_id for row in self.rows}) != len(self.rows):
            raise ValueError("schedule row IDs must be unique")
        if self.rows != tuple(
            sorted(self.rows, key=lambda row: (row.base_matchup_id, row.repetition_index))
        ):
            raise ValueError("schedule rows must use canonical order")
        if type(self.digest) is not str or not _DIGEST_RE.fullmatch(self.digest):
            raise ValueError("schedule digest must be a sha256 digest")
        expected = manifest_digest([row.to_dict() for row in self.rows])
        if self.digest != expected:
            raise ValueError("schedule digest does not match rows")
        groups: dict[str, list[ScheduleRow]] = {}
        for row in self.rows:
            groups.setdefault(row.base_matchup_id, []).append(row)
        for base_matchup_id, rows in groups.items():
            repetitions = sorted(row.repetition_index for row in rows)
            if repetitions != list(range(len(rows))):
                raise ValueError(
                    f"repetition indices for {base_matchup_id} must be contiguous from zero"
                )
            p1_count = sum(row.side_assignment is SideAssignment.P1 for row in rows)
            p2_count = sum(row.side_assignment is SideAssignment.P2 for row in rows)
            if abs(p1_count - p2_count) > 1:
                raise ValueError(f"schedule rows for {base_matchup_id} must be balanced")


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


def derive_schedule_row_id(
    *,
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

    if type(repetitions) is not int or not 1 <= repetitions <= _MAX_SAFE_INTEGER:
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
            row_id = derive_schedule_row_id(
                base_matchup_id=base_id,
                side_assignment=side,
                schedule_block=key.schedule_block,
                seed_family=family,
                repetition_index=repetition_index,
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


__all__ = [
    "Schedule",
    "ScheduleRow",
    "SideAssignment",
    "build_schedule",
    "derive_schedule_row_id",
]
