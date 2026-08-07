from pathlib import Path

import pytest
from tools.check_architecture import ImportRule, scan_poke_engine_public_surface, scan_tree


def write_module(root: Path, package: str, body: str) -> Path:
    path = root / package / "module.py"
    path.parent.mkdir(parents=True)
    path.write_text(body, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "forbidden_module", ("battlebelief_runtime", "battlebelief_lab", "poke_engine")
)
def test_core_cannot_import_runtime_lab_or_native_engine(
    tmp_path: Path, forbidden_module: str
) -> None:
    write_module(tmp_path, "battlebelief_core", f"import {forbidden_module}\n")
    errors = scan_tree(tmp_path, ImportRule.core())
    assert any(forbidden_module in error for error in errors)


def test_core_cannot_import_process_primitives(tmp_path: Path) -> None:
    write_module(tmp_path, "battlebelief_core", "import subprocess\n")
    errors = scan_tree(tmp_path, ImportRule.core())
    assert any("subprocess" in error for error in errors)


@pytest.mark.parametrize(
    ("body", "forbidden_root"),
    (
        ("from pathlib import Path\n", "pathlib"),
        ("import os\nos.getenv('BATTLEBELIEF_TEST')\n", "os"),
        ("import time\ntime.monotonic()\n", "time"),
        ("import socket\nsocket.create_connection(('example.invalid', 443))\n", "socket"),
        ("import random\nrandom.random()\n", "random"),
        ("import secrets\nsecrets.token_bytes(32)\n", "secrets"),
    ),
)
def test_core_cannot_import_nondeterministic_or_external_io_primitives(
    tmp_path: Path, body: str, forbidden_root: str
) -> None:
    write_module(tmp_path, "battlebelief_core", body)

    errors = scan_tree(tmp_path, ImportRule.core())

    assert any(f"forbidden import {forbidden_root}" in error for error in errors)


@pytest.mark.parametrize(
    "body",
    (
        "open('private-world.json')\n",
        "import builtins\nbuiltins.open('private-world.json')\n",
        "from builtins import open as read_file\nread_file('private-world.json')\n",
    ),
)
def test_core_cannot_call_builtin_filesystem_open(tmp_path: Path, body: str) -> None:
    write_module(tmp_path, "battlebelief_core", body)

    errors = scan_tree(tmp_path, ImportRule.core())

    assert any("forbidden builtin call open" in error for error in errors)


@pytest.mark.parametrize(
    "body",
    (
        "import io\nio.open('private-world.json')\n",
        "from io import open as read_file\nread_file('private-world.json')\n",
    ),
)
def test_core_cannot_call_io_open(tmp_path: Path, body: str) -> None:
    write_module(tmp_path, "battlebelief_core", body)

    errors = scan_tree(tmp_path, ImportRule.core())

    assert any("forbidden call io.open" in error for error in errors)


@pytest.mark.parametrize(
    "body",
    (
        "import datetime\ndatetime.datetime.now()\n",
        "import datetime as dt\ndt.datetime.utcnow()\n",
        "from datetime import datetime as Clock\nClock.now()\n",
        "from datetime import date\ndate.today()\n",
    ),
)
def test_core_cannot_read_wall_clock_datetime_values(tmp_path: Path, body: str) -> None:
    write_module(tmp_path, "battlebelief_core", body)

    errors = scan_tree(tmp_path, ImportRule.core())

    assert any("forbidden call datetime." in error for error in errors)


@pytest.mark.parametrize(
    "body",
    (
        "def search(world):\n    return world._opaque\n",
        "def search(world):\n    return getattr(world, '_opaque')\n",
        "def search(world):\n    return world.__getattribute__('_opaque')\n",
        "def search(world):\n    return object.__getattribute__(world, '_opaque')\n",
    ),
)
def test_core_search_cannot_read_the_prepared_world_payload(tmp_path: Path, body: str) -> None:
    write_module(tmp_path, "battlebelief_core/search", body)

    errors = scan_tree(tmp_path, ImportRule.core())

    assert any("forbidden private attribute _opaque" in error for error in errors)


@pytest.mark.parametrize(
    "body",
    (
        "import dataclasses\ndef search(world):\n    return dataclasses.asdict(world)\n",
        "from dataclasses import astuple as project\ndef search(world):\n    return project(world)\n",
    ),
)
def test_core_cannot_generically_serialize_dataclass_payloads(tmp_path: Path, body: str) -> None:
    write_module(tmp_path, "battlebelief_core/search", body)

    errors = scan_tree(tmp_path, ImportRule.core())

    assert any("forbidden call dataclasses." in error for error in errors)


def test_runtime_cannot_import_process_primitives(tmp_path: Path) -> None:
    write_module(tmp_path, "battlebelief_runtime", "from subprocess import Popen\n")
    errors = scan_tree(tmp_path, ImportRule.runtime())
    assert any("subprocess" in error for error in errors)


@pytest.mark.parametrize(
    "body",
    (
        "import poke_engine\n",
        "import poke_engine as native\n",
        "from poke_engine import State\n",
        "import importlib\nimportlib.import_module('poke_engine')\n",
        "from importlib import import_module as load\nload('poke_engine.poke_engine')\n",
        "__import__('poke_engine')\n",
    ),
)
def test_runtime_native_import_is_confined_to_poke_engine_adapter(
    tmp_path: Path, body: str
) -> None:
    write_module(tmp_path, "battlebelief_runtime/composition", body)

    errors = scan_tree(tmp_path, ImportRule.runtime())

    assert any("poke_engine" in error for error in errors)


def test_submodule_importlib_binding_still_detects_dynamic_native_import(
    tmp_path: Path,
) -> None:
    write_module(
        tmp_path,
        "battlebelief_runtime/composition",
        "import importlib.metadata\nimportlib.import_module('poke_engine')\n",
    )

    assert any("poke_engine" in error for error in scan_tree(tmp_path, ImportRule.runtime()))


def test_native_import_is_allowed_inside_poke_engine_adapter(tmp_path: Path) -> None:
    write_module(
        tmp_path,
        "battlebelief_runtime/adapters/poke_engine",
        "import importlib\nimportlib.import_module('poke_engine.poke_engine')\n",
    )

    assert scan_tree(tmp_path, ImportRule.runtime()) == []


def test_public_poke_engine_adapter_rejects_task25_probe_and_native_exports(
    tmp_path: Path,
) -> None:
    package = tmp_path / "battlebelief_runtime/adapters/poke_engine"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        "from .native_probe import FixtureBundle\n"
        "from .legal_choice_probe import run_legal_choice_probe\n"
        "__all__ = ['FixtureBundle', 'run_legal_choice_probe']\n",
        encoding="utf-8",
    )

    errors = scan_poke_engine_public_surface(tmp_path)

    assert any("native_probe" in error for error in errors)
    assert any("legal_choice_probe" in error for error in errors)
    assert any("exports differ" in error for error in errors)


def test_public_poke_engine_adapter_rejects_native_reassignment(tmp_path: Path) -> None:
    package = tmp_path / "battlebelief_runtime/adapters/poke_engine"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        "import poke_engine\n"
        "MappingReport = poke_engine.State\n"
        "from .mapping_report import (\n"
        "    PokeEngineMappingFailure,\n"
        "    RequiredCapabilities,\n"
        ")\n"
        "from .sentinel import run_gen9_sentinel\n"
        "from .transition_model import PokeEngineTransitionModel\n"
        "__all__ = [\n"
        "    'MappingReport',\n"
        "    'PokeEngineMappingFailure',\n"
        "    'PokeEngineTransitionModel',\n"
        "    'RequiredCapabilities',\n"
        "    'run_gen9_sentinel',\n"
        "]\n",
        encoding="utf-8",
    )

    errors = scan_poke_engine_public_surface(tmp_path)

    assert any("forbidden public adapter import" in error for error in errors)
    assert any("unapproved public adapter binding" in error for error in errors)
    assert any("not bound to approved imports" in error for error in errors)


def test_current_poke_engine_public_surface_is_exactly_approved() -> None:
    runtime_root = Path(__file__).resolve().parents[2] / "packages/battlebelief-runtime/src"
    assert scan_poke_engine_public_surface(runtime_root) == []


def test_lab_cannot_import_native_engine_directly(tmp_path: Path) -> None:
    write_module(tmp_path, "battlebelief_lab", "import poke_engine\n")

    assert any("poke_engine" in error for error in scan_tree(tmp_path, ImportRule.lab()))


@pytest.mark.parametrize(
    "body",
    (
        "import asyncio\nasyncio.create_subprocess_exec('node')\n",
        "from asyncio import create_subprocess_exec\ncreate_subprocess_exec('node')\n",
        "import os\nos.system('node')\n",
        "from os import system\nsystem('node')\n",
        "import os\nos.posix_spawn('node', ['node'])\n",
        "from os import posix_spawnp\nposix_spawnp('node', ['node'])\n",
    ),
)
def test_core_and_runtime_cannot_call_indirect_process_spawners(tmp_path: Path, body: str) -> None:
    write_module(tmp_path, "battlebelief_core", body)
    write_module(tmp_path, "battlebelief_runtime", body)

    assert scan_tree(tmp_path, ImportRule.core())
    assert scan_tree(tmp_path, ImportRule.runtime())


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
