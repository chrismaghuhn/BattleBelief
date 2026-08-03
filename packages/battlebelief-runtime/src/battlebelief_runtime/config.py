from __future__ import annotations

import ipaddress
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_SERVER_URL = "wss://sim3.psim.us/showdown/websocket"
DEFAULT_CHALLENGE_SETUP_TIMEOUT_SECONDS = 120.0
SHOWDOWN_PASSWORD_ENV = "BATTLEBELIEF_SHOWDOWN_PASSWORD"
_HOST_LABEL_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")


class ChallengeConfigError(ValueError):
    """A local challenge configuration error with a safe public message."""

    def __init__(self, public_message: str) -> None:
        super().__init__(public_message)
        self.public_message = public_message


@dataclass(frozen=True, slots=True)
class ChallengeConfig:
    username: str
    opponent: str
    team_path: Path
    server_url: str
    setup_timeout: float
    password: str = field(repr=False)


def load_challenge_config(
    *,
    username: str,
    opponent: str,
    team_path: Path,
    server_url: str,
    environment: Mapping[str, str],
) -> ChallengeConfig:
    password = environment.get(SHOWDOWN_PASSWORD_ENV)
    if password is None or password == "":
        raise ChallengeConfigError("config_error: Showdown password is required")

    _validate_user_value(username, field_name="username")
    _validate_user_value(opponent, field_name="opponent")
    _validate_server_url(server_url)

    return ChallengeConfig(
        username=username,
        opponent=opponent,
        team_path=team_path,
        server_url=server_url,
        setup_timeout=DEFAULT_CHALLENGE_SETUP_TIMEOUT_SECONDS,
        password=password,
    )


def _validate_user_value(value: str, *, field_name: str) -> None:
    if (
        not _to_id(value)
        or not value.isprintable()
        or any(character in {",", "|"} for character in value)
    ):
        raise ChallengeConfigError(f"config_error: {field_name} is invalid")


def _to_id(value: str) -> str:
    return "".join(
        character.lower() for character in value if character.isascii() and character.isalnum()
    )


def _validate_server_url(value: str) -> None:
    if any(
        character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value
    ):
        raise ChallengeConfigError("config_error: server URL is invalid")

    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ChallengeConfigError("config_error: server URL is invalid") from exc

    if (
        parsed.scheme != "wss"
        or parsed.hostname is None
        or not _is_valid_host(parsed.hostname)
        or parsed.username is not None
        or parsed.password is not None
        or (port is not None and not 1 <= port <= 65535)
        or parsed.fragment
    ):
        raise ChallengeConfigError("config_error: server URL is invalid")


def _is_valid_host(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return True

    try:
        ascii_host = host.encode("idna").decode("ascii")
    except UnicodeError:
        return False
    if ascii_host.endswith("."):
        ascii_host = ascii_host[:-1]
    if not ascii_host or len(ascii_host) > 253:
        return False
    return all(_HOST_LABEL_PATTERN.fullmatch(label) for label in ascii_host.split("."))
