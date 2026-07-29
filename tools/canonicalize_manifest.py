from __future__ import annotations

import hashlib
from typing import Any, cast

import rfc8785


def canonicalize(value: Any) -> bytes:
    return cast(bytes, rfc8785.dumps(value))


def manifest_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonicalize(value)).hexdigest()
