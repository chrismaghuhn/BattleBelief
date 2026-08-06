"""Preflight verification for an installed local Showdown oracle."""

from __future__ import annotations

import hashlib

from battlebelief_lab.oracle.showdown.installation import (
    RULESET_EXTRACTOR_DIGEST,
    ruleset_extractor_bytes,
)


def test_packaged_ruleset_extractor_has_the_manifest_bound_digest() -> None:
    assert RULESET_EXTRACTOR_DIGEST == (
        "sha256:82ae637f73a81aa9bafeab27fc0bc057d1fc281660985898a9c0006159e56f58"
    )
    assert "sha256:" + hashlib.sha256(ruleset_extractor_bytes()).hexdigest() == (
        RULESET_EXTRACTOR_DIGEST
    )
