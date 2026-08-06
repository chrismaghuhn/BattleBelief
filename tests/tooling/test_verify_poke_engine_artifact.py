"""Focused tests for the staged poke-engine artifact verifier."""

from pathlib import Path

import pytest
import tools.verify_poke_engine_artifact as staged_verifier
from tools.verify_poke_engine_artifact import ArtifactVerificationError, _canonical_document
from tools.verify_poke_engine_artifact import main as verify_staged_artifact

from battlebelief_core.canonicalization import manifest_digest


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_canonical_document_rejects_nonfinite_json_as_unreadable(
    tmp_path: Path, constant: str
) -> None:
    document = tmp_path / "manifest.json"
    document.write_text('{"value":' + constant + "}\n", encoding="utf-8")

    with pytest.raises(ArtifactVerificationError, match="artifact input is unreadable"):
        _canonical_document(document, "engine-source.schema.json")


def test_staged_verifier_requires_checkout_argument() -> None:
    with pytest.raises(SystemExit) as error:
        verify_staged_artifact(
            [
                "--source-manifest",
                "source.json",
                "--build-manifest",
                "build.json",
                "--wheel",
                "wheel.whl",
            ]
        )

    assert error.value.code == 2


def test_staged_verifier_rejects_wrong_checkout_before_wheel_acceptance(
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = Path(__file__).resolve().parents[2]

    result = verify_staged_artifact(
        [
            "--source-manifest",
            str(root / "artifacts/gen9ou/m2/engine/engine-source.json"),
            "--build-manifest",
            str(root / "artifacts/gen9ou/m2/engine/engine-build-windows-2025-x86_64-cp314.json"),
            "--wheel",
            str(root / "missing-wheel.whl"),
            "--checkout",
            str(root),
        ]
    )

    assert result == 1
    assert "source commit differs" in capsys.readouterr().err


def test_staged_verifier_reports_staged_scope_for_wheel_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source: dict[str, object] = {"source": "fixture"}
    expected_wheel = {"sha256": "sha256:" + "a" * 64}
    build: dict[str, object] = {
        "source_manifest_digest": manifest_digest(source),
        "python": {
            "python_tag": "cp314",
            "abi_tag": "none",
            "platform_tag": "win_amd64",
        },
        "wheel": expected_wheel,
    }
    checkout_verified = False

    def canonical_document(path: Path, _schema_name: str) -> dict[str, object]:
        return source if path.name == "source.json" else build

    def verify_checkout(_checkout: Path, _source: object) -> None:
        nonlocal checkout_verified
        checkout_verified = True

    def inspect_wheel(_wheel: Path, **_tags: str) -> dict[str, object]:
        assert checkout_verified
        return {**expected_wheel, "size": 1}

    monkeypatch.setattr(staged_verifier, "_canonical_document", canonical_document)
    monkeypatch.setattr(staged_verifier, "validate_pinned_source_manifest", lambda _source: None)
    monkeypatch.setattr(staged_verifier, "verify_source_checkout", verify_checkout)
    monkeypatch.setitem(
        staged_verifier.verify_manifest_wheel_binding.__globals__, "inspect_wheel", inspect_wheel
    )

    result = verify_staged_artifact(
        [
            "--source-manifest",
            str(tmp_path / "source.json"),
            "--build-manifest",
            str(tmp_path / "build.json"),
            "--wheel",
            str(tmp_path / "wheel.whl"),
            "--checkout",
            str(tmp_path / "checkout"),
        ]
    )

    error = capsys.readouterr().err
    assert result == 1
    assert error.strip() == "staged artifact wheel differs from manifest"
    assert "published" not in error
