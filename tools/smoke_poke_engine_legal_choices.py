"""Exercise the installed downstream legal-choice binding without search."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from battlebelief_core.canonicalization import canonicalize, manifest_digest  # noqa: E402
from battlebelief_runtime.adapters.poke_engine.legal_choice_probe import (  # noqa: E402
    run_legal_choice_probe,
)
from battlebelief_runtime.adapters.poke_engine.native_probe import (  # noqa: E402
    load_fixture_bundle,
)
from tools.create_engine_artifact_index_v2 import (  # noqa: E402
    ArtifactIndexV2Error,
    _strict_canonical,
)


class LegalChoiceSmokeError(RuntimeError):
    """A controlled legal-choice sentinel input failure."""


def _fail(message: str) -> NoReturn:
    raise LegalChoiceSmokeError(message)


def _run_checks() -> dict[str, Any]:
    import poke_engine  # type: ignore[import-not-found]

    return run_legal_choice_probe(poke_engine)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cell-id", required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--build-manifest", type=Path, required=True)
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        source = _strict_canonical(args.source_manifest)
        build = _strict_canonical(args.build_manifest)
        if source.get("schema_id") != "urn:battlebelief:schema:manifest:engine-source:v2":
            _fail("source manifest identity differs")
        if (
            build.get("schema_id") != "urn:battlebelief:schema:manifest:engine-build:v2"
            or build.get("cell_id") != args.cell_id
        ):
            _fail("build manifest identity differs")
        wheel = build.get("wheel")
        wheel_sha256 = wheel.get("sha256") if isinstance(wheel, dict) else None
        if not isinstance(wheel_sha256, str):
            _fail("build wheel identity differs")
        bundle = load_fixture_bundle(args.fixture_root)
        result = _run_checks()
        result_digest = manifest_digest(result)
        evidence = {
            "schema_version": 2,
            "cell_id": args.cell_id,
            "classification": "healthy",
            "source_manifest_digest": manifest_digest(source),
            "build_manifest_digest": manifest_digest(build),
            "wheel_sha256": wheel_sha256,
            "fixture_digest": bundle.fixture_digest,
            "configuration_digest": bundle.configuration_digest,
            "result_digest": result_digest,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonicalize(evidence) + b"\n")
    except (
        ArtifactIndexV2Error,
        LegalChoiceSmokeError,
        OSError,
        RuntimeError,
        ValueError,
        TypeError,
    ) as error:
        print(f"legal-choice smoke failed: {error}", file=sys.stderr)
        return 1
    print(f"legal_choice_result_digest={result_digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
