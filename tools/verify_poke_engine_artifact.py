"""Verify a staged poke-engine wheel against its canonical source and build manifests."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from collections.abc import Mapping, Sequence
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


class ManifestWheelBindingError(RuntimeError):
    """A scope-neutral manifest-to-wheel binding failure."""


def _fail(message: str) -> NoReturn:
    raise ArtifactVerificationError(message)


def _reject_nonfinite(_value: str) -> NoReturn:
    raise ValueError("non-finite JSON constant")


_STAGED_WHEELHOUSE_CLOSURE_ERROR = "staged wheelhouse closure differs"


def _is_link_or_reparse_entry(path: Path, metadata: os.stat_result) -> bool:
    if stat.S_ISLNK(metadata.st_mode):
        return True
    reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if getattr(metadata, "st_file_attributes", 0) & reparse_point:
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction()) if callable(is_junction) else False


def _normalized_absolute_path(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def verify_staged_wheelhouse_closure(wheel_path: Path) -> None:
    """Require the staged wheelhouse to contain exactly the supplied regular wheel."""

    try:
        wheelhouse = wheel_path.parent
        wheelhouse_metadata = wheelhouse.lstat()
        if (
            not stat.S_ISDIR(wheelhouse_metadata.st_mode)
            or _is_link_or_reparse_entry(wheelhouse, wheelhouse_metadata)
        ):
            _fail(_STAGED_WHEELHOUSE_CLOSURE_ERROR)
        entries = list(wheelhouse.iterdir())
        if len(entries) != 1:
            _fail(_STAGED_WHEELHOUSE_CLOSURE_ERROR)
        wheel_entry = entries[0]
        if _normalized_absolute_path(wheel_entry) != _normalized_absolute_path(wheel_path):
            _fail(_STAGED_WHEELHOUSE_CLOSURE_ERROR)
        wheel_metadata = wheel_entry.lstat()
        if (
            not stat.S_ISREG(wheel_metadata.st_mode)
            or _is_link_or_reparse_entry(wheel_entry, wheel_metadata)
        ):
            _fail(_STAGED_WHEELHOUSE_CLOSURE_ERROR)
    except OSError:
        _fail(_STAGED_WHEELHOUSE_CLOSURE_ERROR)


def _canonical_document(path: Path, schema_name: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        document = json.loads(raw, parse_constant=_reject_nonfinite)
        schema = json.loads(
            (ROOT / "schemas/manifests" / schema_name).read_bytes(),
            parse_constant=_reject_nonfinite,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        _fail("artifact input is unreadable")
    if not isinstance(document, dict) or raw != canonicalize(document) + b"\n":
        _fail("artifact input is not canonical")
    if list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document)):
        _fail("artifact input violates its schema")
    return document


def verify_manifest_wheel_binding(
    source: Mapping[str, Any], build: Mapping[str, Any], wheel_path: Path
) -> None:
    """Verify a canonical source/build manifest pair against one wheel's identity."""

    if build.get("source_manifest_digest") != manifest_digest(source):
        raise ManifestWheelBindingError("build source digest differs")
    python = build.get("python")
    wheel = build.get("wheel")
    if not isinstance(python, Mapping) or not isinstance(wheel, Mapping):
        raise ManifestWheelBindingError("build wheel identity differs")
    inspected = inspect_wheel(
        wheel_path,
        python_tag=str(python.get("python_tag")),
        abi_tag=str(python.get("abi_tag")),
        platform_tag=str(python.get("platform_tag")),
    )
    if inspected != wheel:
        raise ManifestWheelBindingError("wheel differs from manifest")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--build-manifest", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        verify_staged_wheelhouse_closure(args.wheel)
        source = _canonical_document(args.source_manifest, "engine-source.schema.json")
        build = _canonical_document(args.build_manifest, "engine-build.schema.json")
        validate_pinned_source_manifest(source)
        verify_source_checkout(args.checkout, source)
        verify_manifest_wheel_binding(source, build, args.wheel)
    except ManifestWheelBindingError as error:
        print(f"staged artifact {error}", file=sys.stderr)
        return 1
    except (
        ArtifactVerificationError,
        BuildPokeEngineError,
        ValueError,
    ) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"build_manifest_digest={manifest_digest(build)}")
    print(f"wheel_sha256={build['wheel']['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
