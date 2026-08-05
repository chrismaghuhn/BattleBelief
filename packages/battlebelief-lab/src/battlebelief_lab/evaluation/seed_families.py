"""Stable, namespace-separated seed derivation for M1.5 plans."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum

from battlebelief_core.canonicalization import canonicalize, manifest_digest

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_MAX_SAFE_INTEGER = 9_007_199_254_740_991
SEED_DERIVATION_ID = "sha256-canonical-fields-v1"


class SeedNamespace(StrEnum):
    SEARCH = "search"
    WORLD = "world"
    POLICY = "policy"
    SIMULATOR = "simulator"
    SCHEDULE = "schedule"
    SIDE_ASSIGNMENT = "side_assignment"


def _validate_inputs(
    master_seed: str,
    base_matchup_id: str,
    side_assignment: str,
    repetition_index: int,
) -> None:
    if type(master_seed) is not str or not _HEX64_RE.fullmatch(master_seed):
        raise ValueError("master_seed must be a 64-character lowercase hex string")
    if type(base_matchup_id) is not str or not _DIGEST_RE.fullmatch(base_matchup_id):
        raise ValueError("base_matchup_id must be a sha256 digest")
    if side_assignment not in {"p1", "p2"}:
        raise ValueError("side_assignment must be p1 or p2")
    if type(repetition_index) is not int or not 0 <= repetition_index <= _MAX_SAFE_INTEGER:
        raise ValueError("repetition_index must be a non-negative integer")


def derive_seed(
    *,
    master_seed: str,
    namespace: SeedNamespace,
    base_matchup_id: str,
    side_assignment: str,
    repetition_index: int,
) -> str:
    """Derive one reproducible 256-bit seed without Python's process hash."""

    _validate_inputs(master_seed, base_matchup_id, side_assignment, repetition_index)
    if not isinstance(namespace, SeedNamespace):
        raise ValueError("namespace must be a SeedNamespace")
    payload = {
        "derivation_id": SEED_DERIVATION_ID,
        "master_seed": master_seed,
        "namespace": namespace.value,
        "base_matchup_id": base_matchup_id,
        "side_assignment": side_assignment,
        "repetition_index": repetition_index,
    }
    return hashlib.sha256(canonicalize(payload)).hexdigest()


@dataclass(frozen=True, slots=True)
class SeedFamily:
    """All independent random namespaces for one scheduled battle."""

    derivation_id: str
    search_seed: str
    world_seed: str
    policy_seed: str
    simulator_seed: str
    schedule_seed: str
    side_assignment_seed: str

    def __post_init__(self) -> None:
        if self.derivation_id != SEED_DERIVATION_ID:
            raise ValueError("unsupported seed derivation ID")
        for name in (
            "search_seed",
            "world_seed",
            "policy_seed",
            "simulator_seed",
            "schedule_seed",
            "side_assignment_seed",
        ):
            value = getattr(self, name)
            if type(value) is not str or not _HEX64_RE.fullmatch(value):
                raise ValueError(f"{name} must be a 64-character lowercase hex string")

    def to_dict(self) -> dict[str, str]:
        return {
            "derivation_id": self.derivation_id,
            "search_seed": self.search_seed,
            "world_seed": self.world_seed,
            "policy_seed": self.policy_seed,
            "simulator_seed": self.simulator_seed,
            "schedule_seed": self.schedule_seed,
            "side_assignment_seed": self.side_assignment_seed,
        }

    @property
    def digest(self) -> str:
        return manifest_digest(self.to_dict())


def derive_seed_family(
    *,
    master_seed: str,
    base_matchup_id: str,
    side_assignment: str,
    repetition_index: int,
) -> SeedFamily:
    """Derive the complete independent seed family for one schedule row."""

    return SeedFamily(
        derivation_id=SEED_DERIVATION_ID,
        search_seed=derive_seed(
            master_seed=master_seed,
            namespace=SeedNamespace.SEARCH,
            base_matchup_id=base_matchup_id,
            side_assignment=side_assignment,
            repetition_index=repetition_index,
        ),
        world_seed=derive_seed(
            master_seed=master_seed,
            namespace=SeedNamespace.WORLD,
            base_matchup_id=base_matchup_id,
            side_assignment=side_assignment,
            repetition_index=repetition_index,
        ),
        policy_seed=derive_seed(
            master_seed=master_seed,
            namespace=SeedNamespace.POLICY,
            base_matchup_id=base_matchup_id,
            side_assignment=side_assignment,
            repetition_index=repetition_index,
        ),
        simulator_seed=derive_seed(
            master_seed=master_seed,
            namespace=SeedNamespace.SIMULATOR,
            base_matchup_id=base_matchup_id,
            side_assignment=side_assignment,
            repetition_index=repetition_index,
        ),
        schedule_seed=derive_seed(
            master_seed=master_seed,
            namespace=SeedNamespace.SCHEDULE,
            base_matchup_id=base_matchup_id,
            side_assignment=side_assignment,
            repetition_index=repetition_index,
        ),
        side_assignment_seed=derive_seed(
            master_seed=master_seed,
            namespace=SeedNamespace.SIDE_ASSIGNMENT,
            base_matchup_id=base_matchup_id,
            side_assignment=side_assignment,
            repetition_index=repetition_index,
        ),
    )
