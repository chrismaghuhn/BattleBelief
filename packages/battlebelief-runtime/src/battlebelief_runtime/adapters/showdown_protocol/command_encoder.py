from __future__ import annotations

from battlebelief_core.domain.actions.submission import ActionKind, BattleSubmission


def encode_submission(submission: BattleSubmission) -> str:
    """Encode a validated BattleSubmission into its exact Showdown choice
    string. Never invents targets, mega/z-move/dynamax suffixes — only what
    the plan's binding output table specifies. Room prefixing and the
    `|<rqid>` suffix are the session layer's responsibility, not this
    function's.
    """
    if submission.kind == ActionKind.DEFAULT:
        return "default"
    if submission.kind == ActionKind.MOVE:
        base = f"move {submission.slot}"
        return f"{base} terastallize" if submission.terastallize else base
    if submission.kind in (ActionKind.SWITCH, ActionKind.REVIVE):
        # ActionKind.REVIVE is wire-encoded identically to a switch — Core
        # keeps the semantic distinction, the wire protocol does not.
        return f"switch {submission.slot}"
    if submission.kind == ActionKind.TEAM:
        return "team " + "".join(str(slot) for slot in submission.team_order)
    raise ValueError(f"unencodable submission kind: {submission.kind}")
