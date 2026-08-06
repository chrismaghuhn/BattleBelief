"""Focused tests for the staged poke-engine artifact verifier."""

from pathlib import Path
from types import SimpleNamespace

import pytest
import tools.verify_poke_engine_artifact as staged_verifier
from tools.verify_poke_engine_artifact import ArtifactVerificationError, _canonical_document
from tools.verify_poke_engine_artifact import main as verify_staged_artifact

from battlebelief_core.canonicalization import manifest_digest

_CLOSURE_ERROR = "staged wheelhouse closure differs"


def _sole_wheel(tmp_path: Path) -> Path:
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel = wheelhouse / "poke_engine-0.0.48-cp314-none-win_amd64.whl"
    wheel.write_bytes(b"wheel bytes")
    return wheel


def _symlink_or_skip(link: Path, target: Path, *, target_is_directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable on this host: {error}")


def test_staged_wheelhouse_closure_accepts_only_expected_regular_wheel(
    tmp_path: Path,
) -> None:
    staged_verifier.verify_staged_wheelhouse_closure(_sole_wheel(tmp_path))


def test_staged_wheelhouse_closure_rejects_extra_regular_file(tmp_path: Path) -> None:
    wheel = _sole_wheel(tmp_path)
    (wheel.parent / "unexpected.txt").write_text("unexpected", encoding="utf-8")

    with pytest.raises(ArtifactVerificationError, match=f"^{_CLOSURE_ERROR}$"):
        staged_verifier.verify_staged_wheelhouse_closure(wheel)


def test_staged_wheelhouse_closure_rejects_extra_directory(tmp_path: Path) -> None:
    wheel = _sole_wheel(tmp_path)
    (wheel.parent / "unexpected").mkdir()

    with pytest.raises(ArtifactVerificationError, match=f"^{_CLOSURE_ERROR}$"):
        staged_verifier.verify_staged_wheelhouse_closure(wheel)


def test_staged_wheelhouse_closure_rejects_expected_wheel_symlink(tmp_path: Path) -> None:
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    target = tmp_path / "outside.whl"
    target.write_bytes(b"wheel bytes")
    wheel = wheelhouse / "poke_engine-0.0.48-cp314-none-win_amd64.whl"
    _symlink_or_skip(wheel, target)

    with pytest.raises(ArtifactVerificationError, match=f"^{_CLOSURE_ERROR}$"):
        staged_verifier.verify_staged_wheelhouse_closure(wheel)


def test_staged_wheelhouse_closure_rejects_extra_symlink(tmp_path: Path) -> None:
    wheel = _sole_wheel(tmp_path)
    target = tmp_path / "outside.txt"
    target.write_text("outside", encoding="utf-8")
    _symlink_or_skip(wheel.parent / "unexpected-link", target)

    with pytest.raises(ArtifactVerificationError, match=f"^{_CLOSURE_ERROR}$"):
        staged_verifier.verify_staged_wheelhouse_closure(wheel)


def test_staged_wheelhouse_closure_rejects_linked_wheelhouse(tmp_path: Path) -> None:
    real_wheelhouse = tmp_path / "real-wheelhouse"
    real_wheelhouse.mkdir()
    wheel = real_wheelhouse / "poke_engine-0.0.48-cp314-none-win_amd64.whl"
    wheel.write_bytes(b"wheel bytes")
    linked_wheelhouse = tmp_path / "linked-wheelhouse"
    _symlink_or_skip(linked_wheelhouse, real_wheelhouse, target_is_directory=True)

    with pytest.raises(ArtifactVerificationError, match=f"^{_CLOSURE_ERROR}$"):
        staged_verifier.verify_staged_wheelhouse_closure(linked_wheelhouse / wheel.name)


def test_staged_wheelhouse_closure_rejects_simulated_reparse_wheel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    wheel = _sole_wheel(tmp_path)
    original_lstat = Path.lstat

    def lstat_with_reparse(path: Path) -> object:
        result = original_lstat(path)
        if path == wheel:
            return SimpleNamespace(
                st_mode=result.st_mode,
                st_file_attributes=0x400,
            )
        return result

    monkeypatch.setattr(staged_verifier.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400, raising=False)
    monkeypatch.setattr(Path, "lstat", lstat_with_reparse)
    monkeypatch.setattr(Path, "is_junction", lambda _path: False, raising=False)

    with pytest.raises(ArtifactVerificationError, match=f"^{_CLOSURE_ERROR}$"):
        staged_verifier.verify_staged_wheelhouse_closure(wheel)


def test_staged_wheelhouse_closure_rejects_simulated_reparse_wheelhouse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    wheel = _sole_wheel(tmp_path)
    original_lstat = Path.lstat

    def lstat_with_reparse(path: Path) -> object:
        result = original_lstat(path)
        if path == wheel.parent:
            return SimpleNamespace(
                st_mode=result.st_mode,
                st_file_attributes=0x400,
            )
        return result

    monkeypatch.setattr(staged_verifier.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400, raising=False)
    monkeypatch.setattr(Path, "lstat", lstat_with_reparse)
    monkeypatch.setattr(Path, "is_junction", lambda _path: False, raising=False)

    with pytest.raises(ArtifactVerificationError, match=f"^{_CLOSURE_ERROR}$"):
        staged_verifier.verify_staged_wheelhouse_closure(wheel)


def test_invalid_staged_wheelhouse_stops_before_manifest_checkout_and_wheel_binding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    wheel = _sole_wheel(tmp_path)
    (wheel.parent / "unexpected.txt").write_text("unexpected", encoding="utf-8")
    called: list[str] = []

    def unexpected(name: str) -> object:
        called.append(name)
        raise AssertionError(f"{name} must not run after a closure failure")

    monkeypatch.setattr(
        staged_verifier,
        "_canonical_document",
        lambda *_args: unexpected("canonical_document"),
    )
    monkeypatch.setattr(
        staged_verifier,
        "validate_pinned_source_manifest",
        lambda *_args: unexpected("validate_pinned_source_manifest"),
    )
    monkeypatch.setattr(
        staged_verifier,
        "verify_source_checkout",
        lambda *_args: unexpected("verify_source_checkout"),
    )
    monkeypatch.setattr(
        staged_verifier,
        "verify_manifest_wheel_binding",
        lambda *_args: unexpected("verify_manifest_wheel_binding"),
    )

    result = verify_staged_artifact(
        [
            "--source-manifest",
            str(tmp_path / "source.json"),
            "--build-manifest",
            str(tmp_path / "build.json"),
            "--wheel",
            str(wheel),
            "--checkout",
            str(tmp_path / "checkout"),
        ]
    )

    assert result == 1
    assert called == []
    assert capsys.readouterr().err.strip() == _CLOSURE_ERROR


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
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = Path(__file__).resolve().parents[2]
    wheel = _sole_wheel(tmp_path)

    result = verify_staged_artifact(
        [
            "--source-manifest",
            str(root / "artifacts/gen9ou/m2/engine/engine-source.json"),
            "--build-manifest",
            str(root / "artifacts/gen9ou/m2/engine/engine-build-windows-2025-x86_64-cp314.json"),
            "--wheel",
            str(wheel),
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
    wheel = _sole_wheel(tmp_path)

    result = verify_staged_artifact(
        [
            "--source-manifest",
            str(tmp_path / "source.json"),
            "--build-manifest",
            str(tmp_path / "build.json"),
            "--wheel",
            str(wheel),
            "--checkout",
            str(tmp_path / "checkout"),
        ]
    )

    error = capsys.readouterr().err
    assert result == 1
    assert error.strip() == "staged artifact wheel differs from manifest"
    assert "published" not in error
