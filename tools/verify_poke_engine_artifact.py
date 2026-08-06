"""Verify a staged poke-engine wheel against its canonical source and build manifests."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from battlebelief_core.canonicalization import canonicalize, manifest_digest  # noqa: E402
from tools.build_poke_engine_wheel import (  # noqa: E402
    BuildPokeEngineError,
    inspect_wheel,
    validate_pinned_source_manifest,
    verify_source_checkout,
)


class ArtifactVerificationError(RuntimeError):
    """A stable staged-artifact verification failure."""


def _fail(message: str) -> NoReturn:
    raise ArtifactVerificationError(message)


def _canonical_document(path: Path, schema_name: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        document = json.loads(raw)
        schema = json.loads((ROOT / "schemas/manifests" / schema_name).read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _fail("artifact input is unreadable")
    if not isinstance(document, dict) or raw != canonicalize(document) + b"\n":
        _fail("artifact input is not canonical")
    if list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document)):
        _fail("artifact input violates its schema")
    return document


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--build-manifest", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--checkout", type=Path)
    args = parser.parse_args(argv)
    try:
        source = _canonical_document(args.source_manifest, "engine-source.schema.json")
        build = _canonical_document(args.build_manifest, "engine-build.schema.json")
        validate_pinned_source_manifest(source)
        if args.checkout is not None:
            verify_source_checkout(args.checkout, source)
        if build.get("source_manifest_digest") != manifest_digest(source):
            _fail("build source digest differs")
        python = build.get("python")
        wheel = build.get("wheel")
        if not isinstance(python, dict) or not isinstance(wheel, dict):
            _fail("build wheel identity differs")
        inspected = inspect_wheel(
            args.wheel,
            python_tag=str(python.get("python_tag")),
            abi_tag=str(python.get("abi_tag")),
            platform_tag=str(python.get("platform_tag")),
        )
        if inspected != wheel:
            _fail("built wheel differs from manifest")
    except (ArtifactVerificationError, BuildPokeEngineError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"build_manifest_digest={manifest_digest(build)}")
    print(f"wheel_sha256={wheel['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
