from pathlib import Path

from tools.check_architecture import ImportRule, scan_tree


def write_module(root: Path, package: str, body: str) -> Path:
    path = root / package / "module.py"
    path.parent.mkdir(parents=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_core_cannot_import_runtime(tmp_path: Path) -> None:
    write_module(tmp_path, "battlebelief_core", "import battlebelief_runtime\n")
    errors = scan_tree(tmp_path, ImportRule.core())
    assert any("battlebelief_runtime" in error for error in errors)


def test_lab_can_import_only_public_runtime_api(tmp_path: Path) -> None:
    write_module(tmp_path, "battlebelief_lab", "import battlebelief_runtime.cli\n")
    errors = scan_tree(tmp_path, ImportRule.lab())
    assert any("battlebelief_runtime.cli" in error for error in errors)


def test_lab_public_runtime_import_is_allowed(tmp_path: Path) -> None:
    write_module(
        tmp_path,
        "battlebelief_lab",
        "from battlebelief_runtime.public_api import runtime_status\n",
    )
    assert scan_tree(tmp_path, ImportRule.lab()) == []
