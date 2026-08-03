from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

SHOWDOWN_SERVER_HOST = "sim3.psim.us"
SHOWDOWN_SERVER_TLS_PORT = 443
DEFAULT_SERVER_URL = f"wss://{SHOWDOWN_SERVER_HOST}/showdown/websocket"
DEFAULT_CHALLENGE_SETUP_TIMEOUT_SECONDS = 120.0
SHOWDOWN_PASSWORD_ENV = "BATTLEBELIEF_SHOWDOWN_PASSWORD"
_ALLOWED_SERVER_URLS = frozenset(
    {
        DEFAULT_SERVER_URL,
        f"wss://{SHOWDOWN_SERVER_HOST}:{SHOWDOWN_SERVER_TLS_PORT}/showdown/websocket",
    }
)


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
    user_id = _to_id(value)
    if (
        not user_id
        or len(user_id) > 18
        or not any("a" <= character <= "z" for character in user_id)
        or not any(character.isascii() and character.isalpha() for character in value)
        or not value.isprintable()
        or any(character in {",", "|"} for character in value)
    ):
        raise ChallengeConfigError(f"config_error: {field_name} is invalid")


def _to_id(value: str) -> str:
    return "".join(
        character for character in value.lower() if character.isascii() and character.isalnum()
    )


def _validate_server_url(value: str) -> None:
    if value not in _ALLOWED_SERVER_URLS:
        raise ChallengeConfigError("config_error: server URL is invalid")
