from __future__ import annotations

import hashlib

from battlebelief_core.domain.teams.sealed_team import SealedTeam
from battlebelief_runtime.adapters.team_files.packed_team import PackedTeam
from battlebelief_runtime.errors.setup import TeamValidationError

_MIN_MEMBERS = 1
_MAX_MEMBERS = 6
_PACKED_FIELDS = 12


def load_packed_team(text: str) -> PackedTeam:
    """Load exactly one nonempty physical line in the official Showdown
    packed team format. Validates structure only — never asserts full team
    legality (that is a later, Showdown-oracle concern).
    """
    normalized = text[:-1] if text.endswith("\n") else text
    if "\r" in normalized:
        raise TeamValidationError("packed team must not contain carriage returns")
    if "\n" in normalized:
        raise TeamValidationError("packed team must be exactly one physical line")
    if normalized == "":
        raise TeamValidationError("packed team is empty")

    entries = normalized.split("]")
    if not (_MIN_MEMBERS <= len(entries) <= _MAX_MEMBERS):
        raise TeamValidationError(
            f"packed team must have {_MIN_MEMBERS}-{_MAX_MEMBERS} members, got {len(entries)}"
        )
    for entry in entries:
        if entry == "" or len(entry.split("|")) != _PACKED_FIELDS:
            raise TeamValidationError(f"invalid packed team entry: {entry!r}")

    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    sealed = SealedTeam(digest=digest, member_count=len(entries))
    return PackedTeam(sealed=sealed, packed=normalized)
