"""Tests for the hermetic, read-only Lab oracle smoke command."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from tools import smoke_lab_oracle

from battlebelief_lab.oracle.showdown.errors import OracleFailureClass
from battlebelief_lab.oracle.showdown.process import OracleProcessError


def test_fixture_paths_bind_exact_project_fixture_names_and_reject_extras(tmp_path: Path) -> None:
    (tmp_path / "minimal_gen9ou_input.json").write_text("{}", encoding="utf-8")
    (tmp_path / "tera_transition_input.json").write_text("{}", encoding="utf-8")

    assert smoke_lab_oracle.fixture_paths(tmp_path) == (
        tmp_path / "minimal_gen9ou_input.json",
        tmp_path / "tera_transition_input.json",
    )

    (tmp_path / "unbound.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="fixture set differs"):
        smoke_lab_oracle.fixture_paths(tmp_path)


def test_smoke_summary_retains_only_stable_digests_and_never_operational_values() -> None:
    summary = smoke_lab_oracle.canonical_smoke_summary(
        probe_role="candidate",
        source_manifest_digest="sha256:" + "a" * 64,
        build_manifest_digest="sha256:" + "b" * 64,
        fixture_results=(
            ("minimal-gen9ou", "sha256:" + "c" * 64),
            ("tera-transition", "sha256:" + "d" * 64),
        ),
        lifecycle_profile_digest="sha256:" + "e" * 64,
    )

    assert summary == {
        "build_manifest_digest": "sha256:" + "b" * 64,
        "fixture_result_digests": {
            "minimal-gen9ou": "sha256:" + "c" * 64,
            "tera-transition": "sha256:" + "d" * 64,
        },
        "lifecycle_profile_digest": "sha256:" + "e" * 64,
        "probe_role": "candidate",
        "source_manifest_digest": "sha256:" + "a" * 64,
    }
    assert not {"pid", "port", "hostname", "path", "time"} & set(summary)


def test_cli_retains_the_server_failure_class(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(smoke_lab_oracle, "_load_manifests", lambda *_args: (object(), object()))
    monkeypatch.setattr(
        smoke_lab_oracle,
        "fixture_paths",
        lambda _directory: (Path("minimal.json"), Path("tera.json")),
    )
    monkeypatch.setattr(smoke_lab_oracle, "_fixture_document", lambda _path: {})

    async def failed_lifecycle(**_kwargs: object) -> dict[str, object]:
        raise OracleProcessError(OracleFailureClass.EXTERNAL_NETWORK_ATTEMPT, "redacted")

    monkeypatch.setattr(smoke_lab_oracle, "_run_smoke", failed_lifecycle)

    assert (
        smoke_lab_oracle.main(
            [
                "--source-manifest",
                "source.json",
                "--build-manifest",
                "build.json",
                "--checkout",
                "checkout",
                "--node",
                "node",
                "--npm",
                "npm",
                "--fixtures-dir",
                "fixtures",
            ]
        )
        == 1
    )
    assert capsys.readouterr().err == "external_network_attempt\n"


def test_oracle_environment_has_a_minimal_allowlist_and_excludes_host_state() -> None:
    environment = smoke_lab_oracle.oracle_environment(
        Path("C:/exact-node/node.exe"),
        {
            "PATH": "C:/node;C:/system",
            "SYSTEMROOT": "C:/Windows",
            "SystemRoot": "C:/Windows",
            "COMSPEC": "C:/Windows/System32/cmd.exe",
            "WINDIR": "C:/Windows",
            "PATHEXT": ".EXE;.CMD",
            "TEMP": "C:/Temp",
            "TMP": "C:/Temp",
            "HTTPS_PROXY": "http://proxy.example.test",
            "HTTP_PROXY": "http://proxy.example.test",
            "HOME": "C:/Users/Alice",
            "USERPROFILE": "C:/Users/Alice",
            "USERNAME": "Alice",
            "COMPUTERNAME": "private-host",
            "SECRET_TOKEN": "not-for-child",
            "NODE_OPTIONS": "--inspect",
        },
    )

    assert environment["PATH"] == "C:\\exact-node"
    assert "HTTPS_PROXY" not in environment
    assert "HTTP_PROXY" not in environment
    assert not {"HOME", "USERPROFILE", "USERNAME", "COMPUTERNAME", "SECRET_TOKEN"} & set(
        environment
    )
    assert "NODE_OPTIONS" not in environment


@pytest.mark.parametrize("probe_role", ("candidate", "comparison"))
def test_smoke_reverifies_the_cleaned_build_before_starting_any_fixture(
    monkeypatch: pytest.MonkeyPatch, probe_role: str
) -> None:
    calls: list[str] = []
    source = SimpleNamespace(digest="sha256:" + "a" * 64)
    build = SimpleNamespace(probe_role=probe_role, digest="sha256:" + "b" * 64)

    def verify(**_kwargs: object) -> None:
        calls.append("verify")

    class Lifecycle:
        def canonical_profile_bytes(self) -> bytes:
            return b"{}"

    class ServerSmoke:
        async def run(self, *_args: object) -> Lifecycle:
            calls.append("server")
            return Lifecycle()

    async def candidate_fixture(*_args: object) -> tuple[str, str]:
        calls.append("fixture")
        return "fixture", "sha256:" + "c" * 64

    async def comparison_fixture(**_kwargs: object) -> tuple[str, str]:
        calls.append("fixture")
        return "fixture", "sha256:" + "c" * 64

    monkeypatch.setattr(smoke_lab_oracle, "verify_build_manifest", verify)
    monkeypatch.setattr(smoke_lab_oracle, "LoopbackServerSmoke", ServerSmoke)
    monkeypatch.setattr(
        smoke_lab_oracle,
        "oracle_environment",
        lambda _node: {"PATH": "node", "SYSTEMROOT": "C:/Windows"},
    )
    monkeypatch.setattr(smoke_lab_oracle, "ShowdownOracleConfig", lambda **_kwargs: object())
    monkeypatch.setattr(smoke_lab_oracle, "_run_candidate_fixture_twice", candidate_fixture)
    monkeypatch.setattr(smoke_lab_oracle, "_run_comparison_fixture", comparison_fixture)

    result = asyncio.run(
        smoke_lab_oracle._run_smoke(
            source=source,
            build=build,
            checkout=Path("checkout"),
            node=Path("node"),
            npm=Path("npm"),
            fixture_documents=({},),
        )
    )

    assert calls == ["verify", "server", "verify", "fixture"]
    assert result["fixture_result_digests"] == {"fixture": "sha256:" + "c" * 64}
