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

from battlebelief_lab.registration_validation import (  # noqa: E402
    load_json_strict,
    schema_issue_summary,
)

FRONTMATTER = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
FENCED_CODE = re.compile(r"(?ms)^(`{3,})[^\n]*\n.*?^\1[ \t]*$")
LOCAL_PATH = re.compile(r"(?i)(?<![a-z])[a-z]:[\\/]|file://|%3a(?:%2f|/)")
OLD_NAMES = re.compile(r"(?i)urn:pokemonbot|pokemonbot[-_](?:core|runtime|lab)")
DOCUMENT_SNAPSHOT_METADATA_SCHEMA = "schemas/documents/document-snapshot-metadata.schema.json"


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

    errors.extend(collect_document_snapshot_errors(root))

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


def collect_document_snapshot_errors(root: Path) -> list[str]:
    """Validate typed immutable snapshot metadata without revalidating bytes."""

    docs_root = root / "docs"
    legacy_roots = (
        docs_root / "contracts/snapshots",
        docs_root / "archive/contract-snapshots",
    )
    snapshot_root = docs_root / "archive/document-snapshots"
    errors: list[str] = []
    for legacy_root in legacy_roots:
        if legacy_root.exists() and any(legacy_root.rglob("*")):
            errors.append(
                f"{legacy_root.relative_to(root)}: legacy snapshot path is unsupported; "
                "use docs/archive/document-snapshots with sidecar metadata"
            )
    if not snapshot_root.exists():
        return sorted(errors)

    metadata_schema_path = root / DOCUMENT_SNAPSHOT_METADATA_SCHEMA
    try:
        metadata_schema = load_json_strict(metadata_schema_path)
        Draft202012Validator.check_schema(metadata_schema)
    except Exception as exc:
        return [
            f"{metadata_schema_path.relative_to(root)}: cannot load snapshot metadata schema: "
            f"{type(exc).__name__}"
        ]
    metadata_validator = Draft202012Validator(metadata_schema, format_checker=FormatChecker())

    referenced_snapshots: set[Path] = set()
    identities: set[tuple[str, int, str]] = set()
    for metadata_path in sorted(snapshot_root.rglob("*.metadata.json")):
        relative = metadata_path.relative_to(root)
        try:
            metadata = load_json_strict(metadata_path)
        except Exception as exc:
            errors.append(f"{relative}: invalid snapshot metadata: {type(exc).__name__}")
            continue
        schema_errors = list(metadata_validator.iter_errors(metadata))
        if schema_errors:
            errors.extend(f"{relative}: {schema_issue_summary(issue)}" for issue in schema_errors)
            continue
        if not isinstance(metadata, dict):
            errors.append(f"{relative}: snapshot metadata must be an object")
            continue
        snapshot_path_text = metadata["snapshot_path"]
        snapshot_path = root / Path(*snapshot_path_text.replace("\\", "/").split("/"))
        resolved_snapshot = snapshot_path.resolve()
        try:
            resolved_snapshot.relative_to(snapshot_root.resolve())
        except ValueError:
            errors.append(f"{relative}: snapshot path escapes archive root")
            continue
        if resolved_snapshot != snapshot_path:
            errors.append(f"{relative}: snapshot path is not repository-relative")
            continue
        if (
            metadata_path.with_name(metadata_path.name.removesuffix(".metadata.json") + ".md")
            != snapshot_path
        ):
            errors.append(f"{relative}: snapshot path does not match metadata filename")
            continue
        if not snapshot_path.is_file():
            errors.append(f"{relative}: snapshot file is missing")
            continue
        actual_digest = "sha256:" + hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
        if metadata["snapshot_digest"] != actual_digest:
            errors.append(f"{relative}: snapshot digest mismatch")
            continue
        if metadata["source_digest"] != metadata["snapshot_digest"]:
            errors.append(f"{relative}: source and snapshot digests differ")
        identity = (
            metadata["document_id"],
            metadata["document_version"],
            metadata["snapshot_digest"],
        )
        if identity in identities:
            errors.append(
                f"duplicate document snapshot: {metadata['document_id']} "
                f"v{metadata['document_version']} {metadata['snapshot_digest']}"
            )
        identities.add(identity)
        referenced_snapshots.add(snapshot_path)

    for snapshot_path in sorted(snapshot_root.rglob("*.md")):
        if snapshot_path not in referenced_snapshots:
            errors.append(f"{snapshot_path.relative_to(root)}: snapshot metadata is missing")
    return sorted(errors)


def collect_contract_snapshot_errors(root: Path) -> list[str]:
    """Backward-compatible name for the generalized document snapshot checker."""

    return collect_document_snapshot_errors(root)


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
