"""Exercise the installed downstream legal-choice binding without search."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

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
    source = json.loads(args.source_manifest.read_bytes())
    build = json.loads(args.build_manifest.read_bytes())
    bundle = load_fixture_bundle(args.fixture_root)
    result = _run_checks()
    result_digest = manifest_digest(result)
    evidence = {
        "schema_version": 2,
        "cell_id": args.cell_id,
        "classification": "healthy",
        "source_manifest_digest": manifest_digest(source),
        "build_manifest_digest": manifest_digest(build),
        "wheel_sha256": build["wheel"]["sha256"],
        "fixture_digest": bundle.fixture_digest,
        "configuration_digest": bundle.configuration_digest,
        "result_digest": result_digest,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonicalize(evidence) + b"\n")
    print(f"legal_choice_result_digest={result_digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
