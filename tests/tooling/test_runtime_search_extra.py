from __future__ import annotations

import json
import tomllib
from pathlib import Path

from battlebelief_core.canonicalization import manifest_digest
from battlebelief_runtime.adapters.poke_engine.artifact import (
    EXPECTED_ARTIFACT_INDEX_DIGEST,
)

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = ROOT / "packages/battlebelief-runtime"
RELEASE_TAG = "engine-poke-engine-v0.0.48-bcf13823-v1"
RELEASE_ROOT = f"https://github.com/chrismaghuhn/BattleBelief/releases/download/{RELEASE_TAG}/"
INDEX_DIGEST = "sha256:5b4f59849ff01c6024b7b5f78f95f5457f3f69030bf46822d9f323c911908d98"
WHEELS = (
    (
        "3.12",
        "linux",
        "x86_64",
        "poke_engine-0.0.48-cp312-cp312-linux_x86_64.whl",
        "2f566d435691873278203e6e13ea0247a4c3d675735d2f9e7117812b32988c84",
    ),
    (
        "3.13",
        "linux",
        "x86_64",
        "poke_engine-0.0.48-cp313-cp313-linux_x86_64.whl",
        "0426bae7bada0d8ed576bde65381eb726c9bbecd28d59f491b0c4409420f5131",
    ),
    (
        "3.14",
        "linux",
        "x86_64",
        "poke_engine-0.0.48-cp314-cp314-linux_x86_64.whl",
        "895b44026f5eed78223a37e568e0d426ee7e6e98178abf333298364bca46a8e0",
    ),
    (
        "3.12",
        "win32",
        "AMD64",
        "poke_engine-0.0.48-cp312-none-win_amd64.whl",
        "0678b467f6109dcbff9612bfdff765a0faab825068e5c456d1250f0aac05c05a",
    ),
    (
        "3.13",
        "win32",
        "AMD64",
        "poke_engine-0.0.48-cp313-none-win_amd64.whl",
        "8828c4730a70940a09d49d6e5d776f18dddf6b16e726dffdbe86e7499dd5c653",
    ),
    (
        "3.14",
        "win32",
        "AMD64",
        "poke_engine-0.0.48-cp314-none-win_amd64.whl",
        "11502307bc5ecd37e351c47317f401a1cdbe50f013c8defbe88262238a74352e",
    ),
)


def _expected_requirements() -> set[str]:
    return {
        (
            f"poke-engine @ {RELEASE_ROOT}{filename}#sha256={digest} ; "
            "implementation_name == 'cpython' and "
            f"python_version == '{python_version}' and "
            f"sys_platform == '{sys_platform}' and "
            f"platform_machine == '{machine}'"
        )
        for python_version, sys_platform, machine, filename, digest in WHEELS
    }


def test_runtime_search_extra_binds_only_the_six_immutable_release_wheels() -> None:
    document = tomllib.loads((RUNTIME_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = document["project"]

    assert all(not dependency.startswith("poke-engine") for dependency in project["dependencies"])
    assert set(project["optional-dependencies"]["search"]) == _expected_requirements()
    assert document["tool"]["hatch"]["metadata"]["allow-direct-references"] is True


def test_uv_lock_binds_all_search_urls_and_hashes_without_source_fallback() -> None:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    engine_packages = [package for package in lock["package"] if package["name"] == "poke-engine"]
    expected = {
        (f"{RELEASE_ROOT}{filename}", f"sha256:{digest}")
        for _version, _platform, _machine, filename, digest in WHEELS
    }

    assert len(engine_packages) == 6
    assert {
        (package["source"]["url"], package["wheels"][0]["hash"]) for package in engine_packages
    } == expected
    assert all(len(package["wheels"]) == 1 for package in engine_packages)
    assert all("sdist" not in package for package in engine_packages)


def test_runtime_packages_the_exact_available_artifact_sidecars() -> None:
    repository_data = ROOT / "artifacts/gen9ou/m2/engine"
    runtime_data = RUNTIME_ROOT / "src/battlebelief_runtime/adapters/poke_engine/data"
    expected_names = {
        "engine-source.json",
        "engine-artifact-index.json",
        *{
            f"engine-build-{operating_system}-x86_64-cp{minor}.json"
            for operating_system in ("ubuntu-24.04", "windows-2025")
            for minor in ("312", "313", "314")
        },
    }

    assert {path.name for path in runtime_data.iterdir()} == expected_names
    for name in expected_names:
        assert (runtime_data / name).read_bytes() == (repository_data / name).read_bytes()

    index = json.loads((runtime_data / "engine-artifact-index.json").read_bytes())
    assert manifest_digest(index) == INDEX_DIGEST
    assert EXPECTED_ARTIFACT_INDEX_DIGEST == INDEX_DIGEST
    assert {cell["cell_id"] for cell in index["cells"]} == {
        f"{operating_system}-x86_64-cp{minor}"
        for operating_system in ("ubuntu-24.04", "windows-2025")
        for minor in ("312", "313", "314")
    }
    assert {cell["availability_status"] for cell in index["cells"]} == {"available"}
