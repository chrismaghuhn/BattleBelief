from typing import Final, TypedDict

from battlebelief_runtime import __version__


class RuntimeStatus(TypedDict):
    package: str
    version: str
    phase: str
    entrypoint: str
    battle_capability: str


_STATUS: Final[RuntimeStatus] = {
    "package": "battlebelief-runtime",
    "version": __version__,
    "phase": "M1",
    "entrypoint": "ready",
    "battle_capability": "heuristic_direct_challenge",
}


def runtime_status() -> RuntimeStatus:
    return _STATUS.copy()
