"""Digest-bound Node preload that denies every non-literal-loopback network path."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from types import MappingProxyType

from battlebelief_lab.oracle.showdown.errors import OracleFailureClass

EXTERNAL_NETWORK_MARKER = "BATTLEBELIEF_ORACLE_EXTERNAL_NETWORK_ATTEMPT"
LOOPBACK_LISTEN_MARKER = "BATTLEBELIEF_ORACLE_LOOPBACK_LISTEN"
_NETWORK_GUARD_DIGEST = "sha256:f78b2d3ce3a6af69a79acc7fa4766bfbebee25d6da11d28228a334c535fdacf8"


class NetworkGuardError(RuntimeError):
    """The packaged fail-closed Node preload is missing or has changed."""


def _guard_resource() -> resources.abc.Traversable:
    return resources.files("battlebelief_lab.oracle.showdown").joinpath(
        "assets", "showdown_no_public_network.cjs"
    )


def network_guard_bytes() -> bytes:
    """Read and integrity-check the packaged CommonJS preload."""

    try:
        payload = _guard_resource().read_bytes()
    except (FileNotFoundError, ModuleNotFoundError) as error:
        raise NetworkGuardError("the packaged Node network guard is unavailable") from error
    if "sha256:" + hashlib.sha256(payload).hexdigest() != _NETWORK_GUARD_DIGEST:
        raise NetworkGuardError("the packaged Node network guard digest differs")
    return payload


def network_guard_digest() -> str:
    """Return the fixed digest bound to the packaged preload bytes."""

    network_guard_bytes()
    return _NETWORK_GUARD_DIGEST


def _node_options_for_guard(path: Path) -> str:
    # NODE_OPTIONS has its own option parser. Quotes preserve a genuine path
    # containing spaces; the forward-slash form avoids Windows backslash escapes.
    rendered = path.resolve().as_posix().replace('"', "")
    return f'--require "{rendered}"'


@contextmanager
def guarded_node_environment(environment: Mapping[str, str]) -> Iterator[Mapping[str, str]]:
    """Yield a child environment with the immutable preload as its sole options value.

    Caller-supplied ``NODE_OPTIONS`` is deliberately replaced, rather than
    extended, so a caller cannot omit or override the oracle network boundary.
    ``resources.as_file`` keeps a wheel-extracted asset live through the child.
    """

    if any(type(key) is not str or type(value) is not str for key, value in environment.items()):
        raise TypeError("Node environment keys and values must be strings")
    network_guard_bytes()
    with resources.as_file(_guard_resource()) as guard_path:
        guarded = dict(environment)
        guarded["NODE_OPTIONS"] = _node_options_for_guard(guard_path)
        yield MappingProxyType(guarded)


def classify_network_marker(stderr: bytes | bytearray) -> OracleFailureClass | None:
    """Prioritize the preload's fixed marker over generic child-exit failures."""

    return (
        OracleFailureClass.EXTERNAL_NETWORK_ATTEMPT
        if EXTERNAL_NETWORK_MARKER.encode("ascii") in bytes(stderr)
        else None
    )


__all__ = [
    "EXTERNAL_NETWORK_MARKER",
    "LOOPBACK_LISTEN_MARKER",
    "classify_network_marker",
    "guarded_node_environment",
    "network_guard_bytes",
    "network_guard_digest",
]
