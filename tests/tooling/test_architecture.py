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


def test_core_cannot_import_process_primitives(tmp_path: Path) -> None:
    write_module(tmp_path, "battlebelief_core", "import subprocess\n")
    errors = scan_tree(tmp_path, ImportRule.core())
    assert any("subprocess" in error for error in errors)


def test_runtime_cannot_import_process_primitives(tmp_path: Path) -> None:
    write_module(tmp_path, "battlebelief_runtime", "from subprocess import Popen\n")
    errors = scan_tree(tmp_path, ImportRule.runtime())
    assert any("subprocess" in error for error in errors)


def test_lab_oracle_may_import_process_primitives(tmp_path: Path) -> None:
    write_module(tmp_path, "battlebelief_lab/oracle/showdown", "import subprocess\n")
    assert scan_tree(tmp_path, ImportRule.lab()) == []


def test_core_and_runtime_cannot_import_lab_oracle(tmp_path: Path) -> None:
    core = tmp_path / "core"
    runtime = tmp_path / "runtime"
    write_module(core, "battlebelief_core", "import battlebelief_lab.oracle.showdown\n")
    write_module(runtime, "battlebelief_runtime", "import battlebelief_lab.oracle.showdown\n")
    assert any(
        "battlebelief_lab.oracle.showdown" in error for error in scan_tree(core, ImportRule.core())
    )
    assert any(
        "battlebelief_lab.oracle.showdown" in error
        for error in scan_tree(runtime, ImportRule.runtime())
    )


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
