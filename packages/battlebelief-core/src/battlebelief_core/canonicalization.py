"""RFC 8785 canonicalization shared by installable packages and tools."""

from __future__ import annotations

import hashlib
from typing import Any

import rfc8785


def canonicalize(value: Any) -> bytes:
    """Return the RFC 8785 canonical UTF-8 representation of ``value``."""

    return rfc8785.dumps(value)


def manifest_digest(value: Any) -> str:
    """Return the repository's versioned ``sha256:`` digest representation."""

    return "sha256:" + hashlib.sha256(canonicalize(value)).hexdigest()
