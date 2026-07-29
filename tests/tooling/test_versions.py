from pathlib import Path

from tools.check_versions import collect_version_errors

ROOT = Path(__file__).resolve().parents[2]


def test_workspace_versions_are_exactly_locked() -> None:
    assert collect_version_errors(ROOT) == []
