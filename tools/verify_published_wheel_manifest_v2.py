"""Verify one published downstream-patched v2 wheel manifest."""

from __future__ import annotations

import argparse
import json
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
)
from tools.verify_poke_engine_artifact import (  # noqa: E402
    ManifestWheelBindingError,
    verify_staged_wheelhouse_closure,
)


class PublishedWheelV2Error(RuntimeError):
    """A stable published v2 wheel verification failure."""


def _fail(message: str) -> NoReturn:
    raise PublishedWheelV2Error(message)


def _canonical_document(path: Path, schema_name: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        document = json.loads(raw)
        schema = json.loads((ROOT / "schemas/manifests" / schema_name).read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _fail("published v2 wheel input is unreadable")
    if not isinstance(document, dict) or raw != canonicalize(document) + b"\n":
        _fail("published v2 wheel input is not canonical")
    if list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document)):
        _fail("published v2 wheel input violates its schema")
    return document


def verify_manifest_wheel_binding_v2(
    source: Mapping[str, Any], build: Mapping[str, Any], wheel_path: Path
) -> None:
    if build.get("source_manifest_digest") != manifest_digest(source):
        raise ManifestWheelBindingError("v2 build source digest differs")
    if build.get("source_tree_digest") != source.get("source_tree_digest"):
        raise ManifestWheelBindingError("v2 source tree digest differs")
    patch = source.get("downstream_patch")
    if not isinstance(patch, Mapping) or build.get("downstream_patch_digest") != patch.get(
        "sha256"
    ):
        raise ManifestWheelBindingError("v2 downstream patch digest differs")
    python = build.get("python")
    wheel = build.get("wheel")
    if not isinstance(python, Mapping) or not isinstance(wheel, Mapping):
        raise ManifestWheelBindingError("v2 build wheel identity differs")
    inspected = inspect_wheel(
        wheel_path,
        python_tag=str(python.get("python_tag")),
        abi_tag=str(python.get("abi_tag")),
        platform_tag=str(python.get("platform_tag")),
        distribution_version="0.0.49",
    )
    if inspected != wheel:
        raise ManifestWheelBindingError("v2 wheel differs from manifest")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--build-manifest", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        verify_staged_wheelhouse_closure(args.wheel)
        source = _canonical_document(args.source_manifest, "engine-source-v2.schema.json")
        build = _canonical_document(args.build_manifest, "engine-build-v2.schema.json")
        verify_manifest_wheel_binding_v2(source, build, args.wheel)
    except ManifestWheelBindingError as error:
        print(f"published v2 {error}", file=sys.stderr)
        return 1
    except (PublishedWheelV2Error, BuildPokeEngineError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"published_wheel_manifest_digest={manifest_digest(build)}")
    print(f"published_wheel_sha256={build['wheel']['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
