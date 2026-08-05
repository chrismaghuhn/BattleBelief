"""Strict, bounded codec for the Pokémon Showdown simulator stdio protocol."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Never, cast

from battlebelief_core.canonicalization import canonicalize
from battlebelief_lab.oracle.showdown.errors import OracleFailureClass

type PlayerSide = Literal["p1", "p2"]
_PLAYER_SIDES = frozenset({"p1", "p2"})
_TIMESTAMP_LINE_RE = re.compile(r"^\|t:\|[0-9]+$")

DEFAULT_MAX_FRAME_BYTES = 4 * 1024 * 1024
DEFAULT_MAX_BUFFER_BYTES = 4 * 1024 * 1024
DEFAULT_MAX_COMMAND_BYTES = 1024 * 1024
DEFAULT_MAX_INPUT_BYTES = 16 * 1024 * 1024


class OracleProtocolError(ValueError):
    """Protocol failure with a stable, evidence-safe classification."""

    def __init__(self, failure_class: OracleFailureClass, message: str) -> None:
        self.failure_class = failure_class
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class UpdateMessage:
    """A simulator update after operational timestamp lines are removed."""

    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SideUpdateMessage:
    """A player-only request with immutable canonical JSON bytes."""

    side: PlayerSide
    lines: tuple[str, ...]
    request_json: bytes


@dataclass(frozen=True, slots=True)
class SideErrorMessage:
    """A syntactically valid player choice error retained for session policy."""

    side: PlayerSide
    line: str


@dataclass(frozen=True, slots=True)
class EndMessage:
    """The terminal simulator log object as immutable canonical JSON bytes."""

    log_json: bytes


type ProtocolMessage = UpdateMessage | SideUpdateMessage | SideErrorMessage | EndMessage


def _raise_protocol(failure_class: OracleFailureClass, message: str) -> Never:
    raise OracleProtocolError(failure_class, message)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_nonfinite(_value: str) -> None:
    raise ValueError("non-finite JSON number")


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite JSON number")
    return parsed


def _is_nfc_json(value: Any) -> bool:
    if isinstance(value, str):
        return unicodedata.is_normalized("NFC", value)
    if isinstance(value, list):
        return all(_is_nfc_json(item) for item in value)
    if isinstance(value, dict):
        return all(
            unicodedata.is_normalized("NFC", key) and _is_nfc_json(item)
            for key, item in value.items()
        )
    return True


def _load_json(payload: str) -> Any:
    try:
        value = json.loads(
            payload,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
            parse_float=_parse_finite_float,
        )
        if not _is_nfc_json(value):
            raise ValueError("JSON strings must be NFC normalized")
        canonicalize(value)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise OracleProtocolError(
            OracleFailureClass.MALFORMED_OUTPUT,
            "simulator message contains invalid JSON",
        ) from exc
    return value


def _canonical_json(payload: str, *, allow_null: bool) -> bytes:
    value = _load_json(payload)
    if value is None and allow_null:
        return b"null"
    if not isinstance(value, dict):
        _raise_protocol(
            OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
            "simulator JSON payload has an unexpected top-level shape",
        )
    return canonicalize(value)


def _validate_protocol_lines(lines: tuple[str, ...]) -> None:
    if not lines or any(not line.startswith("|") for line in lines):
        _raise_protocol(
            OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
            "simulator message contains an invalid protocol line",
        )
    if any(line.startswith("|error|") for line in lines):
        _raise_protocol(
            OracleFailureClass.RULESET_REJECTED,
            "simulator emitted a protocol error",
        )


def _semantic_lines(lines: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(line for line in lines if _TIMESTAMP_LINE_RE.fullmatch(line) is None)


class ShowdownProtocolDecoder:
    """Incrementally decode one strict simulator battle stream."""

    def __init__(
        self,
        *,
        max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
        max_buffer_bytes: int = DEFAULT_MAX_BUFFER_BYTES,
    ) -> None:
        if max_frame_bytes <= 0 or max_buffer_bytes <= 0:
            raise ValueError("protocol limits must be positive")
        self._max_frame_bytes = max_frame_bytes
        self._max_buffer_bytes = max_buffer_bytes
        self._buffer = bytearray()
        self._started = False
        self._ended = False
        self._finished = False
        self._failed = False

    def feed(self, chunk: bytes) -> tuple[ProtocolMessage, ...]:
        """Consume an arbitrary stdout chunk and return all complete messages."""

        if self._failed:
            _raise_protocol(
                OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
                "simulator output arrived after a terminal decoder failure",
            )
        if self._finished:
            _raise_protocol(
                OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
                "simulator output arrived after decoder finish",
            )
        try:
            self._buffer.extend(chunk)
            messages: list[ProtocolMessage] = []
            delimiter = b"\n\n"
            while (boundary := self._buffer.find(delimiter)) >= 0:
                frame = bytes(self._buffer[:boundary])
                del self._buffer[: boundary + len(delimiter)]
                if len(frame) > self._max_frame_bytes:
                    _raise_protocol(
                        OracleFailureClass.OUTPUT_TOO_LARGE,
                        "simulator frame exceeds the configured byte limit",
                    )
                messages.append(self._decode_frame(frame))
            if len(self._buffer) > min(self._max_frame_bytes, self._max_buffer_bytes):
                _raise_protocol(
                    OracleFailureClass.OUTPUT_TOO_LARGE,
                    "simulator buffer exceeds the configured byte limit",
                )
            return tuple(messages)
        except OracleProtocolError:
            self._failed = True
            raise

    def finish(self) -> None:
        """Require a clean frame boundary and exactly one terminal end message."""

        if self._finished:
            return
        if self._failed:
            _raise_protocol(
                OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
                "simulator decoder cannot finish after a terminal failure",
            )
        self._finished = True
        if self._buffer:
            try:
                bytes(self._buffer).decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise OracleProtocolError(
                    OracleFailureClass.MALFORMED_OUTPUT,
                    "simulator output is not valid UTF-8",
                ) from exc
            _raise_protocol(
                OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
                "simulator output ended inside a frame",
            )
        if not self._ended:
            _raise_protocol(
                OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
                "simulator output ended before the terminal end message",
            )

    def _decode_frame(self, frame: bytes) -> ProtocolMessage:
        if not frame:
            _raise_protocol(
                OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
                "simulator emitted an empty frame",
            )
        try:
            text = frame.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise OracleProtocolError(
                OracleFailureClass.MALFORMED_OUTPUT,
                "simulator output is not valid UTF-8",
            ) from exc
        if "\r" in text or "\x00" in text or not unicodedata.is_normalized("NFC", text):
            _raise_protocol(
                OracleFailureClass.MALFORMED_OUTPUT,
                "simulator output contains a forbidden character or normalization",
            )
        lines = tuple(text.split("\n"))
        frame_kind = lines[0]
        if self._ended:
            _raise_protocol(
                OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
                "simulator emitted output after the terminal end message",
            )
        if frame_kind == "update":
            update_message = self._decode_update(lines[1:])
            self._started = True
            return update_message
        if frame_kind == "sideupdate":
            side_message = self._decode_sideupdate(lines[1:])
            if isinstance(side_message, SideUpdateMessage) and not self._started:
                _raise_protocol(
                    OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
                    "simulator emitted a request before battle initialization",
                )
            return side_message
        if frame_kind == "end":
            if not self._started:
                _raise_protocol(
                    OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
                    "simulator ended before battle initialization",
                )
            end_message = self._decode_end(lines[1:])
            self._ended = True
            return end_message
        _raise_protocol(
            OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
            "simulator emitted an unknown frame kind",
        )

    @staticmethod
    def _decode_update(lines: tuple[str, ...]) -> UpdateMessage:
        _validate_protocol_lines(lines)
        return UpdateMessage(lines=_semantic_lines(lines))

    @staticmethod
    def _decode_sideupdate(lines: tuple[str, ...]) -> SideUpdateMessage | SideErrorMessage:
        if len(lines) != 2 or lines[0] not in _PLAYER_SIDES:
            _raise_protocol(
                OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
                "sideupdate has an invalid player or message shape",
            )
        side = cast(PlayerSide, lines[0])
        line = lines[1]
        if line.startswith("|error|") and len(line) > len("|error|"):
            return SideErrorMessage(side=side, line=line)
        if not line.startswith("|request|"):
            _raise_protocol(
                OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
                "sideupdate must contain exactly one request line",
            )
        request_payload = line.removeprefix("|request|")
        request_json = _canonical_json(request_payload, allow_null=True)
        canonical_line = "|request|" + request_json.decode("utf-8")
        return SideUpdateMessage(
            side=side,
            lines=(canonical_line,),
            request_json=request_json,
        )

    @staticmethod
    def _decode_end(lines: tuple[str, ...]) -> EndMessage:
        if len(lines) != 1:
            _raise_protocol(
                OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
                "end message has an invalid shape",
            )
        return EndMessage(log_json=_canonical_json(lines[0], allow_null=False))


def encode_commands(
    commands: Sequence[str],
    *,
    max_command_bytes: int = DEFAULT_MAX_COMMAND_BYTES,
    max_total_bytes: int = DEFAULT_MAX_INPUT_BYTES,
) -> bytes:
    """Encode strict simulator commands with one trailing newline each."""

    if max_command_bytes <= 0 or max_total_bytes <= 0:
        raise ValueError("command limits must be positive")
    if not commands:
        _raise_protocol(
            OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
            "simulator command list must not be empty",
        )
    encoded_commands: list[bytes] = []
    total_bytes = 0
    for command in commands:
        if (
            not command
            or not command.startswith(">")
            or "\r" in command
            or "\n" in command
            or "\x00" in command
            or not unicodedata.is_normalized("NFC", command)
        ):
            _raise_protocol(
                OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
                "simulator command has an invalid shape",
            )
        try:
            encoded = command.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise OracleProtocolError(
                OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
                "simulator command is not valid Unicode",
            ) from exc
        if len(encoded) > max_command_bytes:
            _raise_protocol(
                OracleFailureClass.INPUT_TOO_LARGE,
                "simulator command exceeds the configured byte limit",
            )
        total_bytes += len(encoded) + 1
        if total_bytes > max_total_bytes:
            _raise_protocol(
                OracleFailureClass.INPUT_TOO_LARGE,
                "simulator input exceeds the configured byte limit",
            )
        encoded_commands.append(encoded + b"\n")
    return b"".join(encoded_commands)


__all__ = [
    "DEFAULT_MAX_BUFFER_BYTES",
    "DEFAULT_MAX_COMMAND_BYTES",
    "DEFAULT_MAX_FRAME_BYTES",
    "DEFAULT_MAX_INPUT_BYTES",
    "EndMessage",
    "OracleProtocolError",
    "PlayerSide",
    "ProtocolMessage",
    "ShowdownProtocolDecoder",
    "SideErrorMessage",
    "SideUpdateMessage",
    "UpdateMessage",
    "encode_commands",
]
