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
RELEASE_TAG = "engine-poke-engine-v0.0.49-bcf13823-v2-legal-choices-r1"
RELEASE_ROOT = f"https://github.com/chrismaghuhn/BattleBelief/releases/download/{RELEASE_TAG}/"
INDEX_DIGEST = "sha256:d098fb14aa802d2899c0479b7fa0e18ff7f42ffd1a915dafcd0bcb6e58bc60c6"
WHEELS = (
    (
        "3.12",
        "linux",
        "x86_64",
        "poke_engine-0.0.49-cp312-cp312-linux_x86_64.whl",
        "498c056f0f2e8acb3690f6d6f509c7c4256799fefc952c5212b4757cf33bb6f9",
    ),
    (
        "3.13",
        "linux",
        "x86_64",
        "poke_engine-0.0.49-cp313-cp313-linux_x86_64.whl",
        "597266fd2cfea5928327d3e2fb23d51b7880f2e7d2527400b56070376710f38e",
    ),
    (
        "3.14",
        "linux",
        "x86_64",
        "poke_engine-0.0.49-cp314-cp314-linux_x86_64.whl",
        "4b4879dae04652fed4139c9bb46903b9011bb09f13a2d3855da8561c92c5da96",
    ),
    (
        "3.12",
        "win32",
        "AMD64",
        "poke_engine-0.0.49-cp312-none-win_amd64.whl",
        "d9b35f68d896f2183245a1f043ff57236d15ccbec875ad5218bae5aae0a21895",
    ),
    (
        "3.13",
        "win32",
        "AMD64",
        "poke_engine-0.0.49-cp313-none-win_amd64.whl",
        "8d0fb2a6d4cf5c2e91901d7024d8efea59c0837cf68dfb488910911971b230c9",
    ),
    (
        "3.14",
        "win32",
        "AMD64",
        "poke_engine-0.0.49-cp314-none-win_amd64.whl",
        "5a212d8c93f4919f742a53392fbf9a93be7c00d30521842f212c0b5a195cb3a4",
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
    repository_data = ROOT / "artifacts/gen9ou/m2/engine-v2"
    runtime_data = RUNTIME_ROOT / "src/battlebelief_runtime/adapters/poke_engine/data-v2"
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
