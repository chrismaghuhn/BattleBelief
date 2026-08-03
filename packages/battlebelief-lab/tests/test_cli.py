import json

import pytest

from battlebelief_lab.cli import lab_status, main


def test_lab_status_has_no_oracle_or_dataset_capability() -> None:
    assert lab_status() == {
        "package": "battlebelief-lab",
        "version": "0.2.0",
        "phase": "M0",
        "entrypoint": "ready",
        "oracle_capability": "absent",
        "dataset_capability": "absent",
    }


def test_lab_doctor(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["doctor"]) == 0
    assert json.loads(capsys.readouterr().out) == lab_status()


def test_lab_version_uses_lockstep_package_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "0.2.0"
