from typing import Final, TypedDict


class RuntimeStatus(TypedDict):
    package: str
    version: str
    phase: str
    entrypoint: str
    battle_capability: str


_STATUS: Final[RuntimeStatus] = {
    "package": "battlebelief-runtime",
    "version": "0.1.0",
    "phase": "M0",
    "entrypoint": "ready",
    "battle_capability": "absent",
}


def runtime_status() -> RuntimeStatus:
    return _STATUS.copy()
