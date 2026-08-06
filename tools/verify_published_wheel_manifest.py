"""Verify a published poke-engine wheel against canonical v1 manifests."""

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
    validate_pinned_source_manifest,
)
from tools.verify_poke_engine_artifact import (  # noqa: E402
    ManifestWheelBindingError,
    verify_manifest_wheel_binding,
)


class PublishedWheelManifestVerificationError(RuntimeError):
    """A stable published-wheel-manifest verification failure."""


def _fail(message: str) -> NoReturn:
    raise PublishedWheelManifestVerificationError(message)


def _reject_nonfinite(_value: str) -> NoReturn:
    raise ValueError("non-finite JSON constant")


def _canonical_document(path: Path, schema_name: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        document = json.loads(raw, parse_constant=_reject_nonfinite)
        schema = json.loads(
            (ROOT / "schemas/manifests" / schema_name).read_bytes(),
            parse_constant=_reject_nonfinite,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        _fail("published wheel input is unreadable")
    if not isinstance(document, dict) or raw != canonicalize(document) + b"\n":
        _fail("published wheel input is not canonical")
    if list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document)):
        _fail("published wheel input violates its schema")
    return document


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--build-manifest", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        source = _canonical_document(args.source_manifest, "engine-source.schema.json")
        build = _canonical_document(args.build_manifest, "engine-build.schema.json")
        validate_pinned_source_manifest(source)
        verify_manifest_wheel_binding(source, build, args.wheel)
    except ManifestWheelBindingError as error:
        print(f"published {error}", file=sys.stderr)
        return 1
    except (PublishedWheelManifestVerificationError, BuildPokeEngineError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"published_wheel_manifest_digest={manifest_digest(build)}")
    print(f"published_wheel_sha256={build['wheel']['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
