import tomllib
from pathlib import Path

from tools.check_versions import collect_version_errors

ROOT = Path(__file__).resolve().parents[2]


def test_workspace_versions_are_exactly_locked() -> None:
    assert collect_version_errors(ROOT) == []


def test_workspace_version_mismatch_is_reported(tmp_path: Path) -> None:
    workspace_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    workspace_version = str(tomllib.loads(workspace_text)["project"]["version"])
    (tmp_path / "pyproject.toml").write_text(
        workspace_text.replace(f'version = "{workspace_version}"', 'version = "9.9.9"', 1),
        encoding="utf-8",
    )
    for package in ("battlebelief-core", "battlebelief-runtime", "battlebelief-lab"):
        destination = tmp_path / "packages" / package / "pyproject.toml"
        destination.parent.mkdir(parents=True)
        destination.write_text(
            (ROOT / "packages" / package / "pyproject.toml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    assert collect_version_errors(tmp_path) == [
        f"workspace and package versions are not lockstep: {sorted([workspace_version, '9.9.9'])}"
    ]
