from __future__ import annotations

import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from tools import create_engine_artifact_index_v2 as artifact_index_v2
from tools import smoke_poke_engine_legal_choices as legal_choice_smoke
from tools.build_poke_engine_wheel import (
    BuildPokeEngineError,
    _normalize_materialized_base,
    apply_downstream_patch,
)

from battlebelief_core.canonicalization import manifest_digest

ROOT = Path(__file__).resolve().parents[2]
PATCH_PATH = (
    ROOT / "artifacts/gen9ou/m2/engine/downstream-patches/poke-engine-legal-choices-v1.patch"
)


def _run_git(repository: Path, *arguments: str) -> str:
    return subprocess.check_output(("git", *arguments), cwd=repository, text=True).strip()


def _create_checkout(tmp_path: Path) -> tuple[Path, str, str, Path, list[dict[str, object]]]:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    _run_git(checkout, "init", "--quiet")
    _run_git(checkout, "config", "user.email", "test@example.invalid")
    _run_git(checkout, "config", "user.name", "Test")
    _run_git(checkout, "config", "core.autocrlf", "false")
    source = checkout / "src.txt"
    source.write_bytes(b"before\n")
    _run_git(checkout, "add", "src.txt")
    _run_git(checkout, "commit", "--quiet", "-m", "base")
    base_commit = _run_git(checkout, "rev-parse", "HEAD")
    base_tree = _run_git(checkout, "rev-parse", "HEAD^{tree}")
    base_bytes = source.read_bytes()

    source.write_bytes(b"after\n")
    patch = tmp_path / "legal-choices.patch"
    patch.write_bytes(subprocess.check_output(("git", "diff", "--binary"), cwd=checkout))
    source.write_bytes(base_bytes)
    assert source.read_bytes() == base_bytes
    expected_records = [
        {
            "path": "src.txt",
            "git_mode": "100644",
            "size": 6,
            "sha256": "sha256:" + hashlib.sha256(b"after\n").hexdigest(),
        }
    ]
    return checkout, base_commit, base_tree, patch, expected_records


def test_downstream_patch_exposes_only_native_legal_choice_enumeration() -> None:
    patch_text = PATCH_PATH.read_text(encoding="utf-8")

    assert "fn legal_choices(py_state: PyState)" in patch_text
    assert patch_text.count("state.root_get_all_options()") == 1
    assert "perform_mcts" not in patch_text
    assert "iterative_deepen_expectiminimax" not in patch_text
    assert "generate_instructions_from_move_pair" not in patch_text


def test_downstream_patch_applies_once_and_verifies_post_patch_closure(tmp_path: Path) -> None:
    checkout, base_commit, base_tree, patch, expected_records = _create_checkout(tmp_path)

    apply_downstream_patch(
        checkout,
        patch,
        base_commit=base_commit,
        base_tree=base_tree,
        patch_sha256="sha256:" + hashlib.sha256(patch.read_bytes()).hexdigest(),
        expected_source_files=expected_records,
    )

    assert (checkout / "src.txt").read_bytes() == b"after\n"


def test_downstream_patch_rejects_digest_mismatch_before_application(tmp_path: Path) -> None:
    checkout, base_commit, base_tree, patch, expected_records = _create_checkout(tmp_path)

    with pytest.raises(BuildPokeEngineError, match="downstream patch digest differs"):
        apply_downstream_patch(
            checkout,
            patch,
            base_commit=base_commit,
            base_tree=base_tree,
            patch_sha256="sha256:" + "0" * 64,
            expected_source_files=expected_records,
        )

    assert (checkout / "src.txt").read_text(encoding="utf-8") == "before\n"


def test_downstream_patch_rejects_second_application(tmp_path: Path) -> None:
    checkout, base_commit, base_tree, patch, expected_records = _create_checkout(tmp_path)
    patch_sha256 = "sha256:" + hashlib.sha256(patch.read_bytes()).hexdigest()

    apply_downstream_patch(
        checkout,
        patch,
        base_commit=base_commit,
        base_tree=base_tree,
        patch_sha256=patch_sha256,
        expected_source_files=expected_records,
    )

    with pytest.raises(BuildPokeEngineError, match="base source tree is dirty"):
        apply_downstream_patch(
            checkout,
            patch,
            base_commit=base_commit,
            base_tree=base_tree,
            patch_sha256=patch_sha256,
            expected_source_files=expected_records,
        )


def test_downstream_patch_rejects_post_patch_closure_mismatch(tmp_path: Path) -> None:
    checkout, base_commit, base_tree, patch, expected_records = _create_checkout(tmp_path)
    expected_records[0]["sha256"] = "sha256:" + "0" * 64

    with pytest.raises(BuildPokeEngineError, match="post-patch source closure differs"):
        apply_downstream_patch(
            checkout,
            patch,
            base_commit=base_commit,
            base_tree=base_tree,
            patch_sha256="sha256:" + hashlib.sha256(patch.read_bytes()).hexdigest(),
            expected_source_files=expected_records,
        )


def test_materialized_base_normalization_rewrites_crlf_to_git_blob_bytes(tmp_path: Path) -> None:
    checkout, base_commit, _base_tree, _patch, _expected_records = _create_checkout(tmp_path)
    _run_git(checkout, "config", "core.autocrlf", "true")
    (checkout / "src.txt").write_bytes(b"before\r\n")

    _normalize_materialized_base(checkout, base_commit)

    assert (checkout / "src.txt").read_bytes() == b"before\n"


def test_v2_source_manifest_binds_base_patch_and_resulting_closure() -> None:
    source_path = ROOT / "artifacts/gen9ou/m2/engine-v2/engine-source.json"
    schema_path = ROOT / "schemas/manifests/engine-source-v2.schema.json"
    source = json.loads(source_path.read_bytes())
    schema = json.loads(schema_path.read_bytes())

    assert (
        list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(source)) == []
    )
    assert source["base_commit"] == "bcf13823abc162a608e187b26bbf683f759f385e"
    assert source["downstream_patch"]["role"] == "legal-choice-binding"
    assert source["source_file_count"] == len(source["source_files"])


def test_v2_source_schema_rejects_the_immutable_v1_identity() -> None:
    source = json.loads((ROOT / "artifacts/gen9ou/m2/engine-v2/engine-source.json").read_bytes())
    source = deepcopy(source)
    source["schema_version"] = 1
    schema = json.loads((ROOT / "schemas/manifests/engine-source-v2.schema.json").read_bytes())

    assert list(Draft202012Validator(schema).iter_errors(source))


def _v2_source_and_build() -> tuple[dict[str, object], dict[str, object]]:
    source = json.loads((ROOT / "artifacts/gen9ou/m2/engine-v2/engine-source.json").read_bytes())
    build = json.loads(
        (
            ROOT
            / "packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/data-v2/"
            / "engine-build-ubuntu-24.04-x86_64-cp312.json"
        ).read_bytes()
    )
    return source, build


def test_v2_index_requires_the_exact_source_patch_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    source, build = _v2_source_and_build()
    build["downstream_patch_digest"] = "sha256:" + "0" * 64
    monkeypatch.setattr(
        artifact_index_v2, "inspect_wheel", lambda *_args, **_kwargs: build["wheel"]
    )

    with pytest.raises(artifact_index_v2.ArtifactIndexV2Error, match="downstream patch identity"):
        artifact_index_v2._build_cell(
            build,
            source_digest=manifest_digest(source),
            patch_digest=source["downstream_patch"]["sha256"],
            wheel_path=ROOT / "missing.whl",
        )


def test_v2_index_rejects_a_non_string_source_patch_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    source, build = _v2_source_and_build()
    build["downstream_patch_digest"] = None
    monkeypatch.setattr(
        artifact_index_v2, "inspect_wheel", lambda *_args, **_kwargs: build["wheel"]
    )

    with pytest.raises(artifact_index_v2.ArtifactIndexV2Error, match="downstream patch identity"):
        artifact_index_v2._build_cell(
            build,
            source_digest=manifest_digest(source),
            patch_digest=source["downstream_patch"]["sha256"],
            wheel_path=ROOT / "missing.whl",
        )


def test_v2_candidate_index_contains_no_sentinel_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, _build = _v2_source_and_build()
    committed_index = json.loads(
        (
            ROOT
            / "packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/data-v2/"
            / "engine-artifact-index.json"
        ).read_bytes()
    )
    committed_cells = {cell["cell_id"]: cell for cell in committed_index["cells"]}
    builds = []
    for cell_id in sorted(artifact_index_v2.EXPECTED_CELLS):
        builds.append({"cell_id": cell_id, "wheel": {"filename": f"{cell_id}.whl"}})

    def fake_build_cell(
        build: dict[str, object], *, source_digest: str, patch_digest: str, wheel_path: Path
    ) -> dict[str, object]:
        cell = dict(committed_cells[build["cell_id"]])
        cell.pop("sentinel_fixture_digest", None)
        cell.pop("sentinel_result_digest", None)
        cell.pop("sentinel_configuration_digest", None)
        cell["source_manifest_digest"] = source_digest
        return cell

    monkeypatch.setattr(artifact_index_v2, "_build_cell", fake_build_cell)
    index = artifact_index_v2.create_artifact_index_v2(
        source_manifest=source,
        build_manifests=builds,
        wheel_paths={
            f"{cell_id}.whl": ROOT / "missing.whl" for cell_id in artifact_index_v2.EXPECTED_CELLS
        },
        fixture_digest="sha256:" + "a" * 64,
        availability_status="candidate",
        evidence_by_cell=None,
    )

    assert all(
        not {"sentinel_fixture_digest", "sentinel_result_digest", "sentinel_configuration_digest"}
        & cell.keys()
        for cell in index["cells"]
    )
    schema = json.loads(
        (ROOT / "schemas/manifests/engine-artifact-index-v2.schema.json").read_bytes()
    )
    assert (
        list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(index)) == []
    )


def test_v2_available_workflow_separates_build_and_sentinel_namespaces() -> None:
    workflow = yaml.load(
        (ROOT / ".github/workflows/poke-engine-legal-choice.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    steps = workflow["jobs"]["legal-choice-available-index"]["steps"]
    downloads = [
        step["with"]
        for step in steps
        if step.get("uses", "").startswith("actions/download-artifact@")
    ]

    assert downloads == [
        {
            "pattern": "legal-choice-build-*",
            "path": "${{ runner.temp }}/v2-builds",
            "merge-multiple": "true",
        },
        {
            "pattern": "legal-choice-sentinel-*",
            "path": "${{ runner.temp }}/v2-evidence",
            "merge-multiple": "true",
        },
    ]


def _run_legal_choice_smoke(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_bytes: bytes,
    build: dict[str, object],
) -> int:
    source_path = tmp_path / "engine-source.json"
    build_path = tmp_path / "engine-build.json"
    output_path = tmp_path / "sentinel.json"
    source_path.write_bytes(source_bytes)
    build_path.write_bytes(json.dumps(build, separators=(",", ":")).encode("utf-8") + b"\n")
    monkeypatch.setattr(
        legal_choice_smoke,
        "load_fixture_bundle",
        lambda _root: SimpleNamespace(
            fixture_digest="sha256:" + "a" * 64,
            configuration_digest="sha256:" + "b" * 64,
        ),
    )
    monkeypatch.setattr(legal_choice_smoke, "_run_checks", lambda: {})
    return legal_choice_smoke.main(
        [
            "--cell-id",
            "ubuntu-24.04-x86_64-cp312",
            "--source-manifest",
            str(source_path),
            "--build-manifest",
            str(build_path),
            "--fixture-root",
            str(tmp_path),
            "--output",
            str(output_path),
        ]
    )


def test_legal_choice_smoke_rejects_duplicate_manifest_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = b'{"schema_id":"first","schema_id":"second"}\n'
    build = {"wheel": {"sha256": "sha256:" + "c" * 64}}

    assert _run_legal_choice_smoke(tmp_path, monkeypatch, source, build) == 1


def test_legal_choice_smoke_reports_missing_manifest_keys_without_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = b'{"schema_id":"urn:battlebelief:schema:manifest:engine-source:v2"}\n'
    build = {"schema_id": "urn:battlebelief:schema:manifest:engine-build:v2"}

    assert _run_legal_choice_smoke(tmp_path, monkeypatch, source, build) == 1


def test_v2_verifiers_convert_expected_runtime_failures_to_status_codes(tmp_path: Path) -> None:
    from tools import verify_published_engine_release_v2 as release_verifier
    from tools import verify_published_wheel_manifest_v2 as wheel_verifier

    missing = tmp_path / "missing"
    assert (
        wheel_verifier.main(
            [
                "--source-manifest",
                str(missing / "source.json"),
                "--build-manifest",
                str(missing / "build.json"),
                "--wheel",
                str(missing / "wheelhouse" / "wheel.whl"),
            ]
        )
        == 1
    )
    assert (
        release_verifier.main(
            [
                "--release-metadata",
                str(missing / "release.json"),
                "--bundle-root",
                str(missing / "bundle"),
                "--manifest-root",
                str(missing / "manifest"),
                "--expected-repository",
                "chrismaghuhn/BattleBelief",
            ]
        )
        == 1
    )
