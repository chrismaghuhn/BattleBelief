import re
from pathlib import Path

from tools.check_docs import collect_doc_errors

ROOT = Path(__file__).resolve().parents[2]
WIKI_LINK = re.compile(r"\[\[([^\]]+)\]\]")


def test_repository_documentation_contracts() -> None:
    assert collect_doc_errors(ROOT) == []


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
