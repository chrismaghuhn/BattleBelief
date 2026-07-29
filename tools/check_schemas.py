from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Allow `python tools/check_schemas.py` without -m
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from jsonschema import Draft202012Validator, FormatChecker

from tools.canonicalize_manifest import canonicalize, manifest_digest


def collect_schema_errors(root: Path) -> list[str]:
    errors: list[str] = []
    schema_root = root / "schemas"
    ids: dict[str, Path] = {}

    for path in sorted(schema_root.rglob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as error:
            errors.append(f"{path.relative_to(root)}: invalid schema: {error}")
            continue
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str) or not schema_id.startswith(
            "urn:battlebelief:"
        ):
            errors.append(f"{path.relative_to(root)}: invalid project schema ID")
        elif schema_id in ids:
            errors.append(
                f"{path.relative_to(root)}: duplicate schema ID also in "
                f"{ids[schema_id].relative_to(root)}"
            )
        else:
            ids[schema_id] = path

    for example_path in sorted((schema_root / "examples").glob("*.example.json")):
        name = example_path.name.removesuffix(".example.json")
        schema_path = schema_root / "manifests" / f"{name}.schema.json"
        if not schema_path.exists():
            errors.append(f"{example_path.relative_to(root)}: schema missing")
            continue
        instance = json.loads(example_path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors.extend(
            f"{example_path.relative_to(root)} {issue.json_path}: {issue.message}"
            for issue in validator.iter_errors(instance)
        )

    vectors: list[dict[str, Any]] = json.loads(
        (schema_root / "canonicalization/test-vectors.json").read_text(
            encoding="utf-8"
        )
    )
    for vector in vectors:
        actual_bytes = canonicalize(vector["value"])
        expected_bytes = vector["canonical_utf8"].encode("utf-8")
        if actual_bytes != expected_bytes:
            errors.append(f"{vector['name']}: canonical bytes differ")
        actual_digest = manifest_digest(vector["value"])
        if actual_digest != "sha256:" + vector["sha256"]:
            errors.append(f"{vector['name']}: digest differs")
    return sorted(errors)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = collect_schema_errors(root)
    if errors:
        print(*errors, sep="\n", file=sys.stderr)
        return 1
    print("PASS: schemas, examples, IDs, and canonicalization vectors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
