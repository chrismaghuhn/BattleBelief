from __future__ import annotations

import pytest

from battlebelief_runtime.errors.actions import ServerInvalidChoice, ServerUnavailableChoice
from battlebelief_runtime.errors.protocol import (
    Disconnect,
    MalformedProtocolMessage,
    RequestStateReconciliationMismatch,
    TimerOrForfeit,
    TransportTimeout,
    UnknownProtocolEvent,
)
from battlebelief_runtime.errors.setup import ChallengeSetupError, TeamValidationError


class TestProtocolErrors:
    def test_unknown_protocol_event_code(self) -> None:
        assert UnknownProtocolEvent.code == "unknown_protocol_event"
        assert issubclass(UnknownProtocolEvent, RuntimeError)

    def test_malformed_protocol_message_code(self) -> None:
        assert MalformedProtocolMessage.code == "malformed_protocol_message"

    def test_request_state_reconciliation_mismatch_code(self) -> None:
        assert RequestStateReconciliationMismatch.code == "request_state_reconciliation_mismatch"

    def test_transport_timeout_code(self) -> None:
        assert TransportTimeout.code == "transport_timeout"

    def test_disconnect_code(self) -> None:
        assert Disconnect.code == "disconnect"

    def test_timer_or_forfeit_code(self) -> None:
        assert TimerOrForfeit.code == "timer_or_forfeit"

    def test_each_error_is_raisable_with_a_message(self) -> None:
        with pytest.raises(UnknownProtocolEvent, match="boom"):
            raise UnknownProtocolEvent("boom")


class TestActionErrors:
    def test_server_invalid_choice_code(self) -> None:
        assert ServerInvalidChoice.code == "server_invalid_choice"
        assert issubclass(ServerInvalidChoice, RuntimeError)

    def test_server_unavailable_choice_code(self) -> None:
        assert ServerUnavailableChoice.code == "server_unavailable_choice"


class TestSetupErrors:
    def test_team_validation_error_code(self) -> None:
        assert TeamValidationError.code == "team_validation_error"
        assert issubclass(TeamValidationError, RuntimeError)

    def test_challenge_setup_error_code(self) -> None:
        assert ChallengeSetupError.code == "challenge_setup_error"

    def test_challenge_setup_error_accepts_allowed_subcode(self) -> None:
        err = ChallengeSetupError(subcode="challenge_command_rejected_explicit", message="rejected")
        assert err.subcode == "challenge_command_rejected_explicit"
        assert str(err) == "rejected"

    def test_challenge_setup_error_accepts_all_three_subcodes(self) -> None:
        for subcode in (
            "challenge_command_rejected_explicit",
            "challenge_not_pending",
            "challenge_setup_timeout",
        ):
            err = ChallengeSetupError(subcode=subcode, message="x")
            assert err.subcode == subcode

    def test_challenge_setup_error_rejects_unknown_subcode(self) -> None:
        with pytest.raises(ValueError):
            ChallengeSetupError(subcode="not-a-real-subcode", message="x")

    def test_challenge_setup_error_exposes_allowed_subcodes(self) -> None:
        assert ChallengeSetupError.allowed_subcodes == frozenset(
            {
                "challenge_command_rejected_explicit",
                "challenge_not_pending",
                "challenge_setup_timeout",
            }
        )


class TestErrorCodesAreImmutable:
    def test_code_cannot_be_overridden_per_instance_by_default(self) -> None:
        # Class-level code attribute is the single source of truth per class.
        err = UnknownProtocolEvent("x")
        assert err.code == "unknown_protocol_event"
