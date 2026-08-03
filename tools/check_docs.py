from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

# Allow `python tools/check_docs.py` to import the shared diagnostic helper.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from battlebelief_lab.registration_validation import schema_issue_summary  # noqa: E402

FRONTMATTER = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
FENCED_CODE = re.compile(r"(?ms)^(`{3,})[^\n]*\n.*?^\1[ \t]*$")
LOCAL_PATH = re.compile(r"(?i)(?<![a-z])[a-z]:[\\/]|file://|%3a(?:%2f|/)")
OLD_NAMES = re.compile(r"(?i)urn:pokemonbot|pokemonbot[-_](?:core|runtime|lab)")


def jsonable(value: Any) -> Any:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    return value


def has_unclosed_fence(text: str) -> bool:
    opening_length: int | None = None
    for line in text.splitlines():
        match = re.match(r"^(`{3,})", line)
        if match is None:
            continue
        fence_length = len(match.group(1))
        if opening_length is None:
            opening_length = fence_length
        elif fence_length >= opening_length:
            opening_length = None
    return opening_length is not None


def collect_doc_errors(root: Path) -> list[str]:
    errors: list[str] = []
    docs_root = root / "docs"
    schema = json.loads(
        (root / "schemas/documents/frontmatter.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    paths = sorted(
        path
        for path in docs_root.rglob("*.md")
        if "archive" not in path.relative_to(docs_root).parts
    )

    documents: dict[str, tuple[Path, dict[str, Any]]] = {}
    texts: dict[Path, str] = {}
    for path in paths:
        text = path.read_text(encoding="utf-8")
        texts[path] = text
        match = FRONTMATTER.match(text)
        if match is None:
            errors.append(f"{path.relative_to(root)}: missing frontmatter")
            continue
        frontmatter = jsonable(yaml.safe_load(match.group(1)))
        errors.extend(
            f"{path.relative_to(root)}: {schema_issue_summary(issue)}"
            for issue in validator.iter_errors(frontmatter)
        )
        document_id = frontmatter.get("document_id")
        if document_id in documents:
            errors.append(f"duplicate document_id: {document_id}")
        else:
            documents[document_id] = (path, frontmatter)

        if has_unclosed_fence(text):
            errors.append(f"{path.relative_to(root)}: unbalanced code fences")
        prose = FENCED_CODE.sub("", text)
        if LOCAL_PATH.search(prose):
            errors.append(f"{path.relative_to(root)}: local path")
        for link in MARKDOWN_LINK.findall(prose):
            target = link.strip().strip("<>").split("#", 1)[0]
            if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                continue
            if not (path.parent / target).resolve().exists():
                errors.append(f"{path.relative_to(root)}: broken link {link}")

    known_ids = set(documents)
    index = (docs_root / "README.md").read_text(encoding="utf-8")
    for document_id, (path, frontmatter) in documents.items():
        for predecessor in frontmatter["supersedes"]:
            if predecessor not in known_ids:
                errors.append(f"{document_id}: unresolved supersedes {predecessor}")
        successor = frontmatter["superseded_by"]
        if successor is not None and successor not in known_ids:
            errors.append(f"{document_id}: unresolved superseded_by {successor}")
        marker = f"[`{document_id}`]"
        if frontmatter["status"] == "accepted" and frontmatter["normative"] and marker not in index:
            errors.append(f"{document_id}: accepted normative document not indexed")
        if frontmatter["status"] in {"superseded", "archived"} and marker in index:
            errors.append(f"{document_id}: noncurrent document listed as current")
        if (
            frontmatter["status"] == "accepted"
            and frontmatter["normative"]
            and OLD_NAMES.search(texts[path])
        ):
            errors.append(f"{document_id}: old namespace in current normative document")

    authority = json.loads((root / "config/docs-authority.json").read_text(encoding="utf-8"))
    for definition in authority["definitions"]:
        literal = "".join(definition["parts"])
        hits = [
            path.relative_to(root).as_posix() for path, text in texts.items() if literal in text
        ]
        if hits != [definition["owner"]]:
            errors.append(f"{definition['id']}: expected {definition['owner']}, got {hits}")

    metadata_path = docs_root / "archive/2026-07-29-design-freeze.metadata.yaml"
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    snapshot = metadata_path.parent / metadata["snapshot_path"]
    digest = "sha256:" + hashlib.sha256(snapshot.read_bytes()).hexdigest()
    if digest != metadata["source_hash"]:
        errors.append(f"archive hash mismatch: {digest}")

    matrix_path = metadata_path.parent / metadata["migration_matrix"]
    with matrix_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    coverage: list[int] = []
    for row in rows:
        start, end = map(int, row["source_lines"].split("-"))
        coverage.extend(range(start, end + 1))
        target = root / row["target_document"]
        if not target.exists():
            errors.append(f"{row['old_section']}: missing migration target")
        elif f"# {row['target_heading']}" not in target.read_text(encoding="utf-8").splitlines():
            errors.append(f"{row['old_section']}: missing target H1")
        if row["normative_owner"] not in known_ids:
            errors.append(f"{row['old_section']}: missing migration owner")

    expected_coverage = list(range(1, len(snapshot.read_text(encoding="utf-8").splitlines()) + 1))
    if coverage != expected_coverage:
        errors.append("migration matrix has gaps, overlaps, or wrong order")
    return sorted(errors)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = collect_doc_errors(root)
    if errors:
        print(*errors, sep="\n", file=sys.stderr)
        return 1
    print("PASS: documentation, authority, links, migration, and archive integrity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
