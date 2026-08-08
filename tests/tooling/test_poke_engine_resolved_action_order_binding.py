"""Contract tests for the immutable v3 resolved-action-order artifact path."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from tools import smoke_poke_engine_resolved_action_order as resolved_order_smoke
from tools.build_poke_engine_wheel import (
    RESOLVED_ACTION_ORDER_ADAPTER_VERSION,
    RESOLVED_ACTION_ORDER_VERSION,
    BuildPokeEngineError,
    apply_downstream_patch_chain,
    create_resolved_action_order_build_manifest,
    create_resolved_action_order_source_manifest,
    validate_resolved_action_order_source_manifest,
)

from battlebelief_core.canonicalization import manifest_digest

ROOT = Path(__file__).resolve().parents[2]
LEGAL_CHOICES_PATCH = (
    ROOT / "artifacts/gen9ou/m2/engine/downstream-patches/poke-engine-legal-choices-v1.patch"
)
RESOLVED_ORDER_PATCH = (
    ROOT
    / "artifacts/gen9ou/m2/engine/downstream-patches/poke-engine-resolved-action-order-v1.patch"
)


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.check_output(("git", *arguments), cwd=repository, text=True).strip()


def _fixture_checkout(tmp_path: Path) -> tuple[Path, str, str, Path, Path]:
    checkout = tmp_path / "checkout"
    checkout.mkdir(parents=True)
    _git(checkout, "init", "--quiet")
    _git(checkout, "config", "user.email", "test@example.invalid")
    _git(checkout, "config", "user.name", "Test")
    _git(checkout, "config", "core.autocrlf", "false")
    source = checkout / "source.txt"
    source.write_bytes(b"base\n")
    _git(checkout, "add", "source.txt")
    _git(checkout, "commit", "--quiet", "-m", "base")
    base_commit = _git(checkout, "rev-parse", "HEAD")
    base_tree = _git(checkout, "rev-parse", "HEAD^{tree}")

    source.write_bytes(b"legal\n")
    legal_patch = tmp_path / "legal.patch"
    legal_patch.write_bytes(
        subprocess.check_output(
            ("git", "diff", "--binary", "--full-index", "--unified=0"), cwd=checkout
        )
    )
    source.write_bytes(b"base\n")
    order_patch = tmp_path / "order.patch"
    order_patch.write_bytes(
        b"diff --git a/source.txt b/source.txt\n"
        b"--- a/source.txt\n"
        b"+++ b/source.txt\n"
        b"@@ -1 +1 @@\n"
        b"-legal\n"
        b"+order\n"
    )
    return checkout, base_commit, base_tree, legal_patch, order_patch


def test_v3_identity_is_additive_and_distinct_from_legal_choice_v2() -> None:
    assert RESOLVED_ACTION_ORDER_VERSION == "0.0.50"
    assert (
        RESOLVED_ACTION_ORDER_ADAPTER_VERSION == "battlebelief-poke-engine-v3-resolved-action-order"
    )


def test_v3_patch_transports_native_order_without_repr_or_python_ordering() -> None:
    patch_text = RESOLVED_ORDER_PATCH.read_text(encoding="utf-8")

    assert "generate_instructions_from_move_pair_with_resolved_action_order" in patch_text
    assert "resolved_action_order" in patch_text
    assert "moves_first(" not in patch_text
    assert "get_effective_speed" not in patch_text
    assert "__repr__" not in patch_text
    assert 'format!("{:?}"' not in patch_text
    assert "keeps_same_state_speed_tie_branches_distinct" in patch_text
    assert '"switch pikachu"' not in patch_text
    assert '"switch bulbasaur"' not in patch_text
    assert 'side_one_moves or [Move(id="tackle", pp=32), Move(id="leer", pp=32)]' in patch_text
    assert "sum(branch.percentage for branch in branches) == pytest.approx(100.0)" in patch_text


def test_v3_patch_bytes_are_preserved_on_windows_checkouts() -> None:
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")

    assert (
        "artifacts/gen9ou/m2/engine/downstream-patches/"
        "poke-engine-resolved-action-order-v1.patch binary"
    ) in attributes


def test_v3_patch_chain_is_ordered_and_rejects_a_reversed_chain(tmp_path: Path) -> None:
    checkout, base_commit, base_tree, legal_patch, order_patch = _fixture_checkout(tmp_path)
    records = apply_downstream_patch_chain(
        checkout,
        patches=(
            (1, legal_patch, "sha256:" + hashlib.sha256(legal_patch.read_bytes()).hexdigest()),
            (2, order_patch, "sha256:" + hashlib.sha256(order_patch.read_bytes()).hexdigest()),
        ),
        base_commit=base_commit,
        base_tree=base_tree,
    )

    assert (checkout / "source.txt").read_bytes() == b"order\n"
    assert records == [
        {
            "path": "source.txt",
            "git_mode": "100644",
            "size": 6,
            "sha256": "sha256:" + hashlib.sha256(b"order\n").hexdigest(),
        }
    ]

    reverse_checkout, reverse_commit, reverse_tree, reverse_legal, reverse_order = (
        _fixture_checkout(tmp_path / "reversed")
    )
    with pytest.raises(BuildPokeEngineError, match="patch chain order differs"):
        apply_downstream_patch_chain(
            reverse_checkout,
            patches=(
                (
                    2,
                    reverse_order,
                    "sha256:" + hashlib.sha256(reverse_order.read_bytes()).hexdigest(),
                ),
                (
                    1,
                    reverse_legal,
                    "sha256:" + hashlib.sha256(reverse_legal.read_bytes()).hexdigest(),
                ),
            ),
            base_commit=reverse_commit,
            base_tree=reverse_tree,
        )


def test_v3_source_manifest_binds_the_exact_two_patch_chain() -> None:
    source_path = ROOT / "artifacts/gen9ou/m2/engine-v3/engine-source.json"
    schema_path = ROOT / "schemas/manifests/engine-source-v3.schema.json"
    source = json.loads(source_path.read_bytes())
    schema = json.loads(schema_path.read_bytes())

    assert (
        list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(source)) == []
    )
    assert [entry["ordinal"] for entry in source["downstream_patches"]] == [1, 2]
    assert [entry["role"] for entry in source["downstream_patches"]] == [
        "legal-choice-binding",
        "resolved-action-order-binding",
    ]
    assert source["source_tree_digest"] == manifest_digest(source["source_files"])


def test_v3_source_manifest_rejects_a_changed_patch_digest() -> None:
    source = json.loads((ROOT / "artifacts/gen9ou/m2/engine-v3/engine-source.json").read_bytes())
    base = json.loads((ROOT / "artifacts/gen9ou/m2/engine/engine-source.json").read_bytes())
    source["downstream_patches"][1]["sha256"] = "sha256:" + "0" * 64

    with pytest.raises(BuildPokeEngineError, match="patch chain provenance differs"):
        validate_resolved_action_order_source_manifest(
            source,
            base,
            (LEGAL_CHOICES_PATCH, RESOLVED_ORDER_PATCH),
        )


def test_v3_source_manifest_creator_is_not_a_v2_alias(tmp_path: Path) -> None:
    checkout, _base_commit, _base_tree, _legal_patch, _order_patch = _fixture_checkout(tmp_path)
    with pytest.raises(BuildPokeEngineError, match="accepted upstream pin"):
        create_resolved_action_order_source_manifest(
            checkout,
            base_manifest={},
            patch_paths=(LEGAL_CHOICES_PATCH, RESOLVED_ORDER_PATCH),
            retrieved_on="2026-08-08",
        )


def test_v3_build_manifest_binds_the_chain_and_rejects_the_v2_distribution() -> None:
    source = json.loads((ROOT / "artifacts/gen9ou/m2/engine-v3/engine-source.json").read_bytes())
    v2_build = json.loads(
        (
            ROOT
            / "packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/data-v2"
            / "engine-build-windows-2025-x86_64-cp314.json"
        ).read_bytes()
    )
    wheel = dict(v2_build["wheel"])
    wheel.update(
        {
            "filename": "poke_engine-0.0.50-cp314-none-win_amd64.whl",
            "tags": ["cp314-none-win_amd64"],
            "root_is_purelib": False,
        }
    )

    build = create_resolved_action_order_build_manifest(
        source_manifest=source,
        rustc_vv=v2_build["rustc_vv"],
        cargo_version=v2_build["cargo_version"],
        maturin_version="1.7.1",
        target_triple="x86_64-pc-windows-msvc",
        operating_system="windows-2025",
        python_version=v2_build["python"]["version"],
        wheel=wheel,
    )

    assert build["distribution"] == {"name": "poke-engine", "version": "0.0.50"}
    assert build["downstream_patch_chain_digest"] == manifest_digest(source["downstream_patches"])
    wheel["filename"] = "poke_engine-0.0.49-cp314-none-win_amd64.whl"
    with pytest.raises(BuildPokeEngineError, match="v3 build cell"):
        create_resolved_action_order_build_manifest(
            source_manifest=source,
            rustc_vv=v2_build["rustc_vv"],
            cargo_version=v2_build["cargo_version"],
            maturin_version="1.7.1",
            target_triple="x86_64-pc-windows-msvc",
            operating_system="windows-2025",
            python_version=v2_build["python"]["version"],
            wheel=wheel,
        )


def test_v3_smoke_rejects_wrong_v2_manifest_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = json.loads((ROOT / "artifacts/gen9ou/m2/engine-v3/engine-source.json").read_bytes())
    source_path = tmp_path / "engine-source.json"
    source_path.write_bytes(json.dumps(source, separators=(",", ":")).encode("utf-8") + b"\n")
    build_path = tmp_path / "engine-build.json"
    build_path.write_bytes(
        b'{"cell_id":"ubuntu-24.04-x86_64-cp312","schema_id":"urn:battlebelief:schema:manifest:engine-build:v2","wheel":{"sha256":"sha256:'
        + b"a" * 64
        + b'"}}\n'
    )
    monkeypatch.setattr(resolved_order_smoke, "load_fixture_bundle", lambda _root: object())
    monkeypatch.setattr(resolved_order_smoke, "_run_checks", lambda: {})

    assert (
        resolved_order_smoke.main(
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
                str(tmp_path / "out.json"),
            ]
        )
        == 1
    )


def test_v3_release_schema_gate_rejects_an_unknown_source_field() -> None:
    from tools.verify_published_engine_release_v3 import _validate_manifest_schema

    with pytest.raises(RuntimeError, match="schema differs"):
        _validate_manifest_schema(
            {"schema_id": "urn:battlebelief:schema:manifest:engine-source:v3", "unexpected": True},
            "engine-source-v3.schema.json",
        )


@pytest.mark.parametrize("field", ["source_tree_digest", "downstream_patch_chain_digest"])
def test_v3_release_rejects_wrong_index_source_closure_digest(field: str) -> None:
    from tools.verify_published_engine_release_v3 import _validate_index_source_closure

    source = json.loads((ROOT / "artifacts/gen9ou/m2/engine-v3/engine-source.json").read_bytes())
    index = {
        "source_manifest_digest": manifest_digest(source),
        "source_tree_digest": source["source_tree_digest"],
        "downstream_patch_chain_digest": manifest_digest(source["downstream_patches"]),
    }
    index[field] = "sha256:" + "0" * 64

    with pytest.raises(RuntimeError, match="source closure differs"):
        _validate_index_source_closure(index, source)


def test_v3_available_workflow_binds_every_cell_sentinel_into_the_index() -> None:
    workflow = yaml.load(
        (ROOT / ".github/workflows/poke-engine-resolved-action-order.yml").read_text(
            encoding="utf-8"
        ),
        Loader=yaml.BaseLoader,
    )

    available = workflow["jobs"]["resolved-order-available-index"]
    assert available["needs"] == [
        "resolved-order-build",
        "resolved-order-candidate-index",
    ]
    steps = available["steps"]
    downloads = [
        step["with"]
        for step in steps
        if step.get("uses", "").startswith("actions/download-artifact@")
    ]
    assert downloads == [
        {
            "pattern": "resolved-order-build-*",
            "path": "${{ runner.temp }}/v3-builds",
            "merge-multiple": "true",
        }
    ]
    command = next(step["run"] for step in steps if step.get("name") == "Create available v3 index")
    assert "--availability-status available" in command
    assert '--evidence-root "${RUNNER_TEMP}/v3-final"' in command
    assert any(
        step.get("with", {}).get("name") == "resolved-order-publication-candidate" for step in steps
    )


def test_v3_workflow_is_triggered_by_every_staged_smoke_input() -> None:
    workflow = yaml.load(
        (ROOT / ".github/workflows/poke-engine-resolved-action-order.yml").read_text(
            encoding="utf-8"
        ),
        Loader=yaml.BaseLoader,
    )

    paths = workflow["on"]["pull_request"]["paths"]
    assert "packages/battlebelief-runtime/tests/fixtures/poke_engine/**" in paths
    assert (
        "packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/"
        "native_probe.py"
    ) in paths
    assert (
        "packages/battlebelief-runtime/src/battlebelief_runtime/adapters/poke_engine/"
        "legal_choice_probe.py"
    ) in paths
