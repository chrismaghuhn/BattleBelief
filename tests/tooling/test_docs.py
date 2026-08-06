import hashlib
import json
import re
import shutil
from pathlib import Path

from tools.check_docs import collect_doc_errors, collect_document_snapshot_errors

ROOT = Path(__file__).resolve().parents[2]
WIKI_LINK = re.compile(r"\[\[([^\]]+)\]\]")


def test_repository_documentation_contracts() -> None:
    assert collect_doc_errors(ROOT) == []


def test_contract_snapshot_is_checked_without_becoming_a_current_document(
    tmp_path: Path,
) -> None:
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    shutil.copytree(ROOT / "config", tmp_path / "config")
    catalog = ROOT / "artifacts/gen9ou/m2/engine-capability-catalog-v1.json"
    copied_catalog = tmp_path / catalog.relative_to(ROOT)
    copied_catalog.parent.mkdir(parents=True)
    shutil.copy2(catalog, copied_catalog)
    shutil.copytree(ROOT / "schemas", tmp_path / "schemas")
    shutil.copytree(ROOT / "tests", tmp_path / "tests")
    shutil.copytree(ROOT / "wiki", tmp_path / "wiki")
    snapshot_root = tmp_path / "docs/archive/document-snapshots"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "docs/evaluation/metrics.md"
    snapshot = snapshot_root / "evaluation-metrics.v4.md"
    snapshot.write_bytes(b"historical bytes without current frontmatter\n[broken](missing.md)\n")
    digest = "sha256:" + hashlib.sha256(snapshot.read_bytes()).hexdigest()
    metadata_path = snapshot_root / "evaluation-metrics.v4.metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "document_id": "evaluation-metrics",
                "document_version": 4,
                "document_type": "contract",
                "status": "accepted",
                "normative": True,
                "source_path": "docs/evaluation/metrics.md",
                "source_digest": digest,
                "snapshot_path": "docs/archive/document-snapshots/evaluation-metrics.v4.md",
                "snapshot_digest": digest,
            }
        ),
        encoding="utf-8",
    )
    source.write_text(
        source.read_text(encoding="utf-8").replace("version: 4", "version: 5", 1),
        encoding="utf-8",
    )

    assert collect_document_snapshot_errors(tmp_path) == []
    assert collect_doc_errors(tmp_path) == []

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["snapshot_digest"] = "sha256:" + "0" * 64
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    assert any(
        "snapshot digest mismatch" in error for error in collect_document_snapshot_errors(tmp_path)
    )


def test_current_and_snapshot_same_version_may_have_distinct_digests(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    shutil.copytree(ROOT / "schemas", tmp_path / "schemas")
    snapshot_root = tmp_path / "docs/archive/document-snapshots"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "docs/evaluation/metrics.md"
    snapshot = snapshot_root / "evaluation-metrics.v4.md"
    snapshot.write_bytes(source.read_bytes() + b"\nchanged historical bytes\n")
    digest = "sha256:" + hashlib.sha256(snapshot.read_bytes()).hexdigest()
    (snapshot_root / "evaluation-metrics.v4.metadata.json").write_text(
        json.dumps(
            {
                "document_id": "evaluation-metrics",
                "document_version": 4,
                "document_type": "contract",
                "status": "accepted",
                "normative": True,
                "source_path": "docs/evaluation/metrics.md",
                "source_digest": digest,
                "snapshot_path": "docs/archive/document-snapshots/evaluation-metrics.v4.md",
                "snapshot_digest": digest,
            }
        ),
        encoding="utf-8",
    )

    assert collect_document_snapshot_errors(tmp_path) == []


def test_duplicate_snapshot_identity_includes_digest(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    shutil.copytree(ROOT / "schemas", tmp_path / "schemas")
    snapshot_root = tmp_path / "docs/archive/document-snapshots"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    snapshot_bytes = b"same immutable bytes\n"
    digest = "sha256:" + hashlib.sha256(snapshot_bytes).hexdigest()
    for name in ("example-doc.v1", "example-doc-copy.v1"):
        snapshot = snapshot_root / f"{name}.md"
        snapshot.write_bytes(snapshot_bytes)
        (snapshot_root / f"{name}.metadata.json").write_text(
            json.dumps(
                {
                    "document_id": "example-doc",
                    "document_version": 1,
                    "document_type": "contract",
                    "status": "accepted",
                    "normative": True,
                    "source_path": "docs/README.md",
                    "source_digest": digest,
                    "snapshot_path": f"docs/archive/document-snapshots/{name}.md",
                    "snapshot_digest": digest,
                }
            ),
            encoding="utf-8",
        )

    errors = collect_document_snapshot_errors(tmp_path)

    assert any("duplicate document snapshot" in error for error in errors)


def test_github_wiki_links_resolve_to_prepared_pages() -> None:
    wiki_root = ROOT / "wiki"
    page_names = {
        path.stem
        for path in wiki_root.glob("*.md")
        if path.name != "README.md" and not path.name.startswith("_")
    }
    broken_links: list[str] = []

    for path in sorted(wiki_root.glob("*.md")):
        for link in WIKI_LINK.findall(path.read_text(encoding="utf-8")):
            target = link.rsplit("|", maxsplit=1)[-1].replace(" ", "-")
            if target not in page_names:
                broken_links.append(f"{path.name} -> {target}")

    assert broken_links == []
