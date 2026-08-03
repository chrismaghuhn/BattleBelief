from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast

from battlebelief_runtime.errors.protocol import (
    MalformedProtocolMessage,
    UnknownProtocolEvent,
)


class OutgoingChallengeStatus(StrEnum):
    PENDING = "pending"
    NOT_PENDING = "not_pending"


@dataclass(frozen=True, slots=True)
class OutgoingChallengeObservation:
    status: OutgoingChallengeStatus
    target_user_id: str
    format_id: str | None
    source_kind: str


class ChallengeStateReader:
    def __init__(
        self,
        our_user_id: str,
        target_user_id: str,
        format_id: str = "gen9ou",
    ) -> None:
        if format_id != "gen9ou":
            raise ValueError("ChallengeStateReader supports only gen9ou")
        normalized_our_user_id = _to_id(our_user_id)
        normalized_target_user_id = _to_id(target_user_id)
        if not normalized_our_user_id:
            raise ValueError("our_user_id must normalize to a non-empty Showdown ID")
        if not normalized_target_user_id:
            raise ValueError("target_user_id must normalize to a non-empty Showdown ID")
        self._our_user_id = normalized_our_user_id
        self._target_user_id = normalized_target_user_id
        self._format_id = format_id

    def read(self, payload: str) -> OutgoingChallengeObservation | None:
        if payload.startswith("|updatechallenges|"):
            return self._read_update_challenges(payload.removeprefix("|updatechallenges|"))
        if payload.startswith("|pm|"):
            return self._read_private_message(payload)
        return None

    def _read_update_challenges(self, json_payload: str) -> OutgoingChallengeObservation:
        try:
            payload = json.loads(json_payload)
        except json.JSONDecodeError as exc:
            raise MalformedProtocolMessage(f"invalid updatechallenges json: {exc}") from exc
        if not isinstance(payload, dict):
            raise MalformedProtocolMessage("updatechallenges json must be an object")
        data = cast(dict[str, Any], payload)

        if "challengeTo" not in data or data["challengeTo"] is None:
            return self._observation(OutgoingChallengeStatus.NOT_PENDING, None, "updatechallenges")

        challenge_to = data["challengeTo"]
        if not isinstance(challenge_to, dict):
            raise MalformedProtocolMessage("challengeTo must be an object or null")
        challenge = cast(dict[str, Any], challenge_to)
        target = _require_string(challenge.get("to"), "challengeTo.to")
        challenge_format = _require_string(challenge.get("format"), "challengeTo.format")
        if _to_id(target) != self._target_user_id:
            raise UnknownProtocolEvent(f"unexpected outgoing challenge target: {target!r}")
        if challenge_format != self._format_id:
            raise UnknownProtocolEvent(
                f"unexpected outgoing challenge format: {challenge_format!r}"
            )
        return self._observation(
            OutgoingChallengeStatus.PENDING, self._format_id, "updatechallenges"
        )

    def _read_private_message(self, payload: str) -> OutgoingChallengeObservation | None:
        parts = payload.split("|", maxsplit=4)
        if len(parts) != 5:
            raise MalformedProtocolMessage("pm must contain sender, receiver, and message")
        _, wire_type, sender, receiver, message = parts
        if wire_type != "pm":
            return None

        sender_id = _to_id(sender)
        receiver_id = _to_id(receiver)
        participants_match = {sender_id, receiver_id} == {
            self._our_user_id,
            self._target_user_id,
        }
        if not participants_match:
            return None

        if message == "/challenge":
            return self._observation(OutgoingChallengeStatus.NOT_PENDING, None, "pm")

        if not message.startswith("/challenge "):
            if message.startswith("/challenge"):
                raise MalformedProtocolMessage("invalid challenge state pm command")
            return None
        if sender_id == self._target_user_id and receiver_id == self._our_user_id:
            return None

        challenge_fields = message.split("|")
        if len(challenge_fields) != 5:
            raise MalformedProtocolMessage("pending challenge pm must contain exactly five fields")
        command, team_builder_format, _, _, _ = challenge_fields
        expected_command = f"/challenge {self._format_id}"
        if command != expected_command or team_builder_format != self._format_id:
            raise UnknownProtocolEvent("pending challenge pm has an unexpected format")
        return self._observation(OutgoingChallengeStatus.PENDING, self._format_id, "pm")

    def _observation(
        self,
        status: OutgoingChallengeStatus,
        format_id: str | None,
        source_kind: str,
    ) -> OutgoingChallengeObservation:
        return OutgoingChallengeObservation(
            status=status,
            target_user_id=self._target_user_id,
            format_id=format_id,
            source_kind=source_kind,
        )


def _require_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or value == "":
        raise MalformedProtocolMessage(f"{context} must be a non-empty string")
    return value


def _to_id(value: str) -> str:
    return "".join(
        character for character in value.lower() if character.isascii() and character.isalnum()
    )
