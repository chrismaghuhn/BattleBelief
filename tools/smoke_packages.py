from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.0"
PACKAGE_DIRS = (
    ROOT / "packages/battlebelief-core",
    ROOT / "packages/battlebelief-runtime",
    ROOT / "packages/battlebelief-lab",
)
EXTERNAL_WHEELS = (
    "attrs==26.1.0",
    "arrow==1.4.0",
    "fqdn==1.5.1",
    "idna==3.18",
    "isoduration==20.11.0",
    "jsonpointer==3.1.1",
    "jsonschema==4.26.0",
    "jsonschema-specifications==2025.9.1",
    "lark==1.3.1",
    "python-dateutil==2.9.0.post0",
    "referencing==0.37.0",
    "rfc3339-validator==0.1.4",
    "rfc3986-validator==0.1.1",
    "rfc3987-syntax==1.1.0",
    "rfc8785==0.1.4",
    "rpds-py==2026.6.3",
    "six==1.17.0",
    "tzdata==2026.3",
    "uri-template==1.3.0",
    "websockets==16.1.1",
    "webcolors==25.10.0",
)
RUNTIME_STATUS = {
    "package": "battlebelief-runtime",
    "version": VERSION,
    "phase": "M1",
    "entrypoint": "ready",
    "battle_capability": "heuristic_direct_challenge",
}
LAB_STATUS = {
    "package": "battlebelief-lab",
    "version": VERSION,
    "phase": "M0",
    "entrypoint": "ready",
    "oracle_capability": "absent",
    "dataset_capability": "absent",
}


def run(arguments: list[str]) -> None:
    subprocess.run(arguments, cwd=ROOT, check=True)


def assert_output(arguments: list[str], expected: str) -> None:
    completed = subprocess.run(
        arguments,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    actual = completed.stdout.strip()
    if actual != expected:
        raise RuntimeError(f"unexpected command output: {actual!r}")


def assert_json_output(arguments: list[str], expected: dict[str, str]) -> None:
    completed = subprocess.run(
        arguments,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        actual = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("doctor output is not valid JSON") from exc
    if actual != expected:
        raise RuntimeError(f"unexpected doctor status: {actual!r}")


def environment_python(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts/python.exe"
    return venv_dir / "bin/python"


def entrypoint(venv_dir: Path, name: str) -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    directory = "Scripts" if sys.platform == "win32" else "bin"
    return venv_dir / directory / f"{name}{suffix}"


def host_python() -> Path:
    if sys.platform == "win32":
        candidate = Path(sys.base_prefix) / "python.exe"
    else:
        candidate = Path(sys.base_prefix) / "bin/python"
    return candidate if candidate.exists() else Path(sys.executable)


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
        run(
            [
                str(host_python()),
                "-m",
                "pip",
                "download",
                "--disable-pip-version-check",
                "--no-deps",
                "--only-binary=:all:",
                "--dest",
                str(dist),
                *EXTERNAL_WHEELS,
            ]
        )

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
                    f"assert battlebelief_core.__version__ == {VERSION!r}; "
                    "import battlebelief_core.canonicalization",
                ]
            ],
        )
        print("PASS: core")

        runtime_env = temp / "runtime"
        install_profile(
            runtime_env,
            dist,
            f"battlebelief-runtime=={VERSION}",
            [],
        )
        runtime_entrypoint = str(entrypoint(runtime_env, "battlebelief"))
        assert_output([runtime_entrypoint, "--version"], VERSION)
        assert_json_output([runtime_entrypoint, "doctor"], RUNTIME_STATUS)
        print("PASS: runtime")

        lab_env = temp / "lab"
        install_profile(
            lab_env,
            dist,
            f"battlebelief-lab=={VERSION}",
            [],
        )
        lab_entrypoint = str(entrypoint(lab_env, "battlebelief-lab"))
        assert_output([lab_entrypoint, "--version"], VERSION)
        assert_json_output([lab_entrypoint, "doctor"], LAB_STATUS)
        run(
            [
                str(environment_python(lab_env)),
                "-c",
                "import hashlib; "
                "from battlebelief_lab.oracle.showdown.installation import "
                "RULESET_EXTRACTOR_DIGEST, ruleset_extractor_bytes; "
                "assert 'sha256:' + hashlib.sha256(ruleset_extractor_bytes()).hexdigest() "
                "== RULESET_EXTRACTOR_DIGEST",
            ]
        )
        run(
            [
                str(environment_python(lab_env)),
                "-c",
                "from battlebelief_lab.oracle.showdown import "
                "OracleFailureClass, OracleRequestIdentity, OracleResult, "
                "ShowdownBuildManifest, ShowdownOracleConfig, ShowdownOracleSession, "
                "ShowdownSourceManifest; "
                "from battlebelief_lab.oracle.showdown.network import "
                "network_guard_bytes, network_guard_digest; "
                "assert network_guard_digest() == "
                "'sha256:f78b2d3ce3a6af69a79acc7fa4766bfbebee25d6da11d28228a334c535fdacf8'; "
                "assert network_guard_bytes(); "
                "assert all(value is not None for value in "
                "(OracleFailureClass, OracleRequestIdentity, OracleResult, "
                "ShowdownBuildManifest, ShowdownOracleConfig, ShowdownOracleSession, "
                "ShowdownSourceManifest))",
            ]
        )
        run(
            [
                str(environment_python(lab_env)),
                "-c",
                "from pathlib import Path; "
                "from battlebelief_lab.registration_validation import "
                "validate_repository_artifacts; "
                f"assert validate_repository_artifacts(Path({str(ROOT)!r})) == []",
            ]
        )
        print("PASS: lab")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
