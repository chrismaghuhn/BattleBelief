import json

import pytest

from battlebelief_runtime.cli import main
from battlebelief_runtime.public_api import runtime_status


def test_runtime_status_is_m0_entrypoint_only() -> None:
    assert runtime_status() == {
        "package": "battlebelief-runtime",
        "version": "0.1.0",
        "phase": "M0",
        "entrypoint": "ready",
        "battle_capability": "absent",
    }


def test_doctor_prints_canonical_status(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["doctor"]) == 0
    output = capsys.readouterr().out
    assert json.loads(output) == runtime_status()


def test_version_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "0.1.0"
