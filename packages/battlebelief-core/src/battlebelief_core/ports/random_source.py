"""Injected deterministic random-stream contract for reproducible search."""

from __future__ import annotations

import hashlib
import re
from typing import Protocol, runtime_checkable

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_DOMAIN_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*)+$")


def validate_random_domain(domain: str) -> str:
    """Validate a stable, lower-ASCII PRNG namespace."""

    if (
        type(domain) is not str
        or len(domain.encode("utf-8")) > 128
        or not _DOMAIN_RE.fullmatch(domain)
    ):
        raise ValueError("random domain must be a canonical dotted identifier")
    return domain


def derive_stream_identity(parent_stream_identity_digest: str, domain: str) -> str:
    """Derive a domain-separated stream identity without consuming a stream."""

    if type(parent_stream_identity_digest) is not str or not _DIGEST_RE.fullmatch(
        parent_stream_identity_digest
    ):
        raise ValueError("parent_stream_identity_digest must be a sha256 digest")
    validated_domain = validate_random_domain(domain)
    parent = parent_stream_identity_digest.encode("ascii")
    domain_bytes = validated_domain.encode("ascii")
    material = (
        b"battlebelief.random-stream.v1\x00"
        + len(parent).to_bytes(4, "big")
        + parent
        + len(domain_bytes).to_bytes(4, "big")
        + domain_bytes
    )
    return "sha256:" + hashlib.sha256(material).hexdigest()


@runtime_checkable
class RandomStream(Protocol):
    """A deterministic stream with non-consuming domain derivation."""

    @property
    def stream_identity_digest(self) -> str: ...

    def derive(self, domain: str) -> RandomStream: ...

    def next_u64(self) -> int: ...

    def randbelow(self, upper_bound: int) -> int: ...


__all__ = ["RandomStream", "derive_stream_identity", "validate_random_domain"]
