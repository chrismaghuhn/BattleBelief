import json
import re
import shutil
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from tools.check_docs import collect_contract_snapshot_errors, collect_doc_errors

ROOT = Path(__file__).resolve().parents[2]
WIKI_LINK = re.compile(r"\[\[([^\]]+)\]\]")


def test_repository_documentation_contracts() -> None:
    assert collect_doc_errors(ROOT) == []


def test_contract_snapshot_is_checked_without_becoming_a_current_document(
    tmp_path: Path,
) -> None:
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    shutil.copytree(ROOT / "config", tmp_path / "config")
    shutil.copytree(ROOT / "schemas", tmp_path / "schemas")
    shutil.copytree(ROOT / "tests", tmp_path / "tests")
    shutil.copytree(ROOT / "wiki", tmp_path / "wiki")
    snapshot_root = tmp_path / "docs/contracts/snapshots"
    snapshot_root.mkdir(parents=True)
    snapshot = snapshot_root / "example-doc.v1.md"
    snapshot.write_text(
        "---\n"
        "document_id: example-doc\n"
        "title: Example snapshot\n"
        "document_type: contract\n"
        "status: accepted\n"
        "normative: true\n"
        "version: 1\n"
        "applies_to:\n"
        "  - test\n"
        "effective_from: 2026-08-03\n"
        "supersedes: []\n"
        "superseded_by: null\n"
        "owners:\n"
        "  - maintainer\n"
        "last_reviewed: 2026-08-03\n"
        "---\n",
        encoding="utf-8",
    )
    schema = json.loads((ROOT / "schemas/documents/frontmatter.schema.json").read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    assert collect_contract_snapshot_errors(tmp_path, schema, validator) == []
    assert collect_doc_errors(tmp_path) == []

    snapshot.write_text(snapshot.read_text(encoding="utf-8").replace("version: 1", "version: 2"))
    assert collect_contract_snapshot_errors(tmp_path, schema, validator) == []
    assert collect_doc_errors(tmp_path) == []


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
