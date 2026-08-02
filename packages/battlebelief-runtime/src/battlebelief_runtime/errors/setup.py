from __future__ import annotations


class TeamValidationError(RuntimeError):
    code = "team_validation_error"


class ChallengeSetupError(RuntimeError):
    code = "challenge_setup_error"
    allowed_subcodes = frozenset(
        {
            "challenge_command_rejected_explicit",
            "challenge_not_pending",
            "challenge_setup_timeout",
        }
    )

    def __init__(self, *, subcode: str, message: str) -> None:
        if subcode not in self.allowed_subcodes:
            raise ValueError("unsupported challenge setup subcode")
        super().__init__(message)
        self.subcode = subcode
