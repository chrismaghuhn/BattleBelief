"""Release-only tests for published poke-engine wheel manifest verification."""

import base64
import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from tools.build_poke_engine_wheel import inspect_wheel
from tools.verify_published_wheel_manifest import main as verify_published_wheel

from battlebelief_core.canonicalization import canonicalize

ROOT = Path(__file__).resolve().parents[2]


def _record_hash(content: bytes) -> str:
    encoded = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).decode().rstrip("=")
    return f"sha256={encoded}"


def _write_fixture_wheel(path: Path) -> None:
    dist_info = "poke_engine-0.0.48.dist-info"
    metadata = b"Metadata-Version: 2.1\nName: poke-engine\nVersion: 0.0.48\n"
    wheel_metadata = b"Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: cp314-none-win_amd64\n"
    record = (
        f"{dist_info}/METADATA,{_record_hash(metadata)},{len(metadata)}\n"
        f"{dist_info}/WHEEL,{_record_hash(wheel_metadata)},{len(wheel_metadata)}\n"
        f"{dist_info}/RECORD,,\n"
    )
    with zipfile.ZipFile(path, "w") as wheel:
        wheel.writestr(f"{dist_info}/METADATA", metadata)
        wheel.writestr(f"{dist_info}/WHEEL", wheel_metadata)
        wheel.writestr(f"{dist_info}/RECORD", record)


def _write_build_manifest_for_wheel(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = ROOT / "artifacts/gen9ou/m2/engine/engine-source.json"
    build = json.loads(
        (ROOT / "artifacts/gen9ou/m2/engine/engine-build-windows-2025-x86_64-cp314.json").read_text(
            encoding="utf-8"
        )
    )
    wheel = tmp_path / "poke_engine-0.0.48-cp314-none-win_amd64.whl"
    _write_fixture_wheel(wheel)
    build["wheel"] = inspect_wheel(
        wheel,
        python_tag="cp314",
        abi_tag="none",
        platform_tag="win_amd64",
    )
    build_path = tmp_path / "build.json"
    build_path.write_bytes(canonicalize(build) + b"\n")
    return source, build_path, wheel


def test_published_wheel_verifier_succeeds_without_checkout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source, build, wheel = _write_build_manifest_for_wheel(tmp_path)

    result = verify_published_wheel(
        ["--source-manifest", str(source), "--build-manifest", str(build), "--wheel", str(wheel)]
    )

    assert result == 0
    assert "published_wheel_manifest_digest=" in capsys.readouterr().out


def test_published_wheel_verifier_rejects_tampered_wheel(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source, build, wheel = _write_build_manifest_for_wheel(tmp_path)
    wheel.write_bytes(wheel.read_bytes() + b"tampered")

    result = verify_published_wheel(
        ["--source-manifest", str(source), "--build-manifest", str(build), "--wheel", str(wheel)]
    )

    assert result == 1
    assert capsys.readouterr().err.strip() == "published wheel differs from manifest"


def test_published_wheel_verifier_rejects_canonically_rewritten_build_manifest(
    tmp_path: Path,
) -> None:
    source, build_path, wheel = _write_build_manifest_for_wheel(tmp_path)
    build = json.loads(build_path.read_text(encoding="utf-8"))
    build["wheel"]["sha256"] = "sha256:" + "0" * 64
    build_path.write_bytes(canonicalize(build) + b"\n")

    result = verify_published_wheel(
        [
            "--source-manifest",
            str(source),
            "--build-manifest",
            str(build_path),
            "--wheel",
            str(wheel),
        ]
    )

    assert result == 1
