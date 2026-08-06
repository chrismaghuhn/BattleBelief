"""Run the real staged or published Gen-9 poke-engine health sentinel."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from battlebelief_core.canonicalization import canonicalize, manifest_digest  # noqa: E402
from battlebelief_runtime.adapters.poke_engine.artifact import (  # noqa: E402
    verify_installed_artifact,
)
from battlebelief_runtime.adapters.poke_engine.errors import EngineArtifactError  # noqa: E402
from battlebelief_runtime.adapters.poke_engine.native_probe import (  # noqa: E402
    load_fixture_bundle,
    run_native_probe,
)


def _write_new(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as output:
            output.write(content)
    except FileExistsError:
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--staged-wheel", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        index_path = args.data_root / "engine-artifact-index.json"
        index_document = json.loads(index_path.read_bytes())
        index_digest = manifest_digest(index_document)
        verified = verify_installed_artifact(
            data_root=args.data_root,
            expected_index_digest=index_digest,
            staged_wheel=args.staged_wheel,
        )
        availability = run_native_probe(
            verified,
            fixture_root=args.fixture_root,
        )
        bundle = load_fixture_bundle(args.fixture_root)
        evidence = {
            "schema_version": 1,
            "cell_id": verified.identity.cell_id,
            "classification": "healthy",
            "source_manifest_digest": verified.identity.source_manifest_digest,
            "build_manifest_digest": verified.identity.build_manifest_digest,
            "wheel_sha256": verified.identity.wheel_sha256,
            "fixture_digest": bundle.fixture_digest,
            "configuration_digest": bundle.configuration_digest,
            "result_digest": verified.identity.sentinel_result_digest,
        }
        output = canonicalize(evidence) + b"\n"
        if args.output is None:
            sys.stdout.buffer.write(output)
        else:
            _write_new(args.output, output)
        if availability.status != "available":
            return 1
    except (EngineArtifactError, OSError, ValueError):
        print("sentinel_failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
