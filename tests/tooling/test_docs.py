from pathlib import Path

from tools.check_docs import collect_doc_errors


ROOT = Path(__file__).resolve().parents[2]


def test_repository_documentation_contracts() -> None:
    assert collect_doc_errors(ROOT) == []
