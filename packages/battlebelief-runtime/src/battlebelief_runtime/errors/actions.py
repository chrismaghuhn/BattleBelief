from __future__ import annotations


class ServerInvalidChoice(RuntimeError):
    code = "server_invalid_choice"


class ServerUnavailableChoice(RuntimeError):
    code = "server_unavailable_choice"
