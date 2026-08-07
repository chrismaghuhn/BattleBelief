from __future__ import annotations

import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from tools.build_poke_engine_wheel import (
    BuildPokeEngineError,
    apply_downstream_patch,
)

PATCH_PATH = Path(
    "artifacts/gen9ou/m2/engine/downstream-patches/poke-engine-legal-choices-v1.patch"
)
ROOT = Path(__file__).resolve().parents[2]


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


def test_v2_source_manifest_binds_base_patch_and_resulting_closure() -> None:
    source_path = ROOT / "artifacts/gen9ou/m2/engine-v2/engine-source.json"
    schema_path = ROOT / "schemas/manifests/engine-source-v2.schema.json"
    source = json.loads(source_path.read_bytes())
    schema = json.loads(schema_path.read_bytes())

    assert list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(source)) == []
    assert source["base_commit"] == "bcf13823abc162a608e187b26bbf683f759f385e"
    assert source["downstream_patch"]["role"] == "legal-choice-binding"
    assert source["source_file_count"] == len(source["source_files"])


def test_v2_source_schema_rejects_the_immutable_v1_identity() -> None:
    source = json.loads((ROOT / "artifacts/gen9ou/m2/engine-v2/engine-source.json").read_bytes())
    source = deepcopy(source)
    source["schema_version"] = 1
    schema = json.loads(
        (ROOT / "schemas/manifests/engine-source-v2.schema.json").read_bytes()
    )

    assert list(Draft202012Validator(schema).iter_errors(source))
