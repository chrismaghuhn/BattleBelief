from __future__ import annotations

import hashlib
from typing import assert_type

import pytest

from battlebelief_core.ports.random_source import (
    RandomStream,
    derive_stream_identity,
    validate_random_domain,
)


class FakeRandomStream:
    def __init__(self, stream_identity_digest: str, state: int = 0) -> None:
        self.stream_identity_digest = stream_identity_digest
        self.state = state

    def derive(self, domain: str) -> FakeRandomStream:
        return FakeRandomStream(derive_stream_identity(self.stream_identity_digest, domain))

    def next_u64(self) -> int:
        self.state += 1
        return self.state

    def randbelow(self, upper_bound: int) -> int:
        if type(upper_bound) is not int or upper_bound <= 0:
            raise ValueError("upper_bound must be positive")
        return self.next_u64() % upper_bound


def _digest(letter: str) -> str:
    return f"sha256:{letter * 64}"


def test_random_stream_contract_separates_domain_derivation_without_parent_consumption() -> None:
    stream = FakeRandomStream(_digest("a"))
    assert_type(stream, RandomStream)
    child = stream.derive("search.rollout")

    assert stream.state == 0
    assert child.stream_identity_digest != stream.stream_identity_digest
    assert stream.derive("search.rollout").stream_identity_digest == child.stream_identity_digest
    assert stream.derive("search.roll.out").stream_identity_digest != child.stream_identity_digest
    nested = child.derive("policy.selection")
    assert (
        nested.stream_identity_digest
        != stream.derive("search.rollout.policy").stream_identity_digest
    )
    assert stream.state == 0


def test_domain_validation_and_length_prefix_prevent_ambiguous_collisions() -> None:
    parent = _digest("b")
    assert validate_random_domain("search.rollout") == "search.rollout"
    with pytest.raises(ValueError):
        validate_random_domain("Search.rollout")

    expected = hashlib.sha256(
        b"battlebelief.random-stream.v1\x00"
        + len(parent.encode("ascii")).to_bytes(4, "big")
        + parent.encode("ascii")
        + len(b"search.rollout").to_bytes(4, "big")
        + b"search.rollout"
    ).hexdigest()
    assert derive_stream_identity(parent, "search.rollout") == f"sha256:{expected}"
