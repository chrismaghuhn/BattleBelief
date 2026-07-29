from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"
PACKAGE_DIRS = (
    ROOT / "packages/battlebelief-core",
    ROOT / "packages/battlebelief-runtime",
    ROOT / "packages/battlebelief-lab",
)


def run(arguments: list[str]) -> None:
    subprocess.run(arguments, cwd=ROOT, check=True)


def environment_python(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts/python.exe"
    return venv_dir / "bin/python"


def entrypoint(venv_dir: Path, name: str) -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    directory = "Scripts" if sys.platform == "win32" else "bin"
    return venv_dir / directory / f"{name}{suffix}"


def install_profile(
    root: Path,
    dist: Path,
    requirement: str,
    commands: list[list[str]],
) -> None:
    venv.EnvBuilder(with_pip=True, clear=True).create(root)
    python = environment_python(root)
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-index",
            "--find-links",
            str(dist),
            requirement,
        ]
    )
    for command in commands:
        run(command)


def main() -> int:
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv executable is required")

    with tempfile.TemporaryDirectory(prefix="battlebelief-smoke-") as temporary:
        temp = Path(temporary)
        dist = temp / "dist"
        dist.mkdir()
        for package_dir in PACKAGE_DIRS:
            run([uv, "build", str(package_dir), "--out-dir", str(dist)])

        core_env = temp / "core"
        install_profile(
            core_env,
            dist,
            f"battlebelief-core=={VERSION}",
            [
                [
                    str(environment_python(core_env)),
                    "-c",
                    "import battlebelief_core; "
                    "assert battlebelief_core.__version__ == '0.1.0'",
                ]
            ],
        )
        print("PASS: core")

        runtime_env = temp / "runtime"
        install_profile(
            runtime_env,
            dist,
            f"battlebelief-runtime=={VERSION}",
            [
                [str(entrypoint(runtime_env, "battlebelief")), "--version"],
                [str(entrypoint(runtime_env, "battlebelief")), "doctor"],
            ],
        )
        print("PASS: runtime")

        lab_env = temp / "lab"
        install_profile(
            lab_env,
            dist,
            f"battlebelief-lab=={VERSION}",
            [
                [str(entrypoint(lab_env, "battlebelief-lab")), "--version"],
                [str(entrypoint(lab_env, "battlebelief-lab")), "doctor"],
            ],
        )
        print("PASS: lab")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
