"""Build or verify the pinned local Pokemon Showdown oracle.

The command line is deliberately thin.  All source/build verification lives in
``battlebelief_lab.oracle.showdown.installation`` so a Lab session performs the
same read-only verification immediately before it launches ``simulate-battle``.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from battlebelief_core.canonicalization import canonicalize  # noqa: E402
from battlebelief_lab.oracle.showdown import installation as _installation  # noqa: E402
from battlebelief_lab.oracle.showdown.errors import OracleFailureClass  # noqa: E402
from battlebelief_lab.oracle.showdown.installation import (  # noqa: E402
    BuildOracleError,
    acquire_pinned_source,
    create_build_manifest,
    verify_build_manifest,
)
from battlebelief_lab.oracle.showdown.manifests import (  # noqa: E402
    ShowdownBuildManifest,
    ShowdownSourceManifest,
)


def _strict_json(data: bytes, *, label: str) -> dict[str, object]:
    return _installation._strict_json(data, label=label)


def _load_source_manifest(path: Path) -> ShowdownSourceManifest:
    return ShowdownSourceManifest.from_dict(
        _strict_json(path.read_bytes(), label="source manifest")
    )


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _validate_cli_paths(
    *,
    source_manifest_path: Path,
    checkout_directory: Path,
    cache_directory: Path,
    home_directory: Path,
    output_path: Path,
    allow_existing_output: bool,
) -> None:
    source = source_manifest_path.resolve()
    output = output_path.resolve()
    checkout = checkout_directory.resolve()
    if (
        output == source
        or _is_within(output, checkout)
        or _is_within(cache_directory, checkout)
        or _is_within(home_directory, checkout)
    ):
        raise BuildOracleError(OracleFailureClass.BUILD_FAILED, "CLI path aliases are forbidden")
    if not allow_existing_output and output.exists():
        raise BuildOracleError(OracleFailureClass.BUILD_FAILED, "output already exists")


def _write_new_manifest(output_path: Path, content: bytes) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("xb") as output:
            output.write(content)
    except FileExistsError as error:
        raise BuildOracleError(OracleFailureClass.BUILD_FAILED, "output already exists") from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--npm", type=Path, required=True)
    parser.add_argument("--probe-role", choices=("candidate", "comparison"), required=True)
    parser.add_argument("--npm-cache", type=Path, required=True)
    parser.add_argument("--npm-home", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        _validate_cli_paths(
            source_manifest_path=args.source_manifest,
            checkout_directory=args.checkout,
            cache_directory=args.npm_cache,
            home_directory=args.npm_home,
            output_path=args.output,
            allow_existing_output=args.verify_only,
        )
        source_manifest = _load_source_manifest(args.source_manifest)
        if args.verify_only:
            build_manifest = ShowdownBuildManifest.from_dict(
                _strict_json(args.output.read_bytes(), label="build manifest")
            )
            verify_build_manifest(
                source_manifest=source_manifest,
                build_manifest=build_manifest,
                checkout_directory=args.checkout,
                node_executable=args.node,
                npm_executable=args.npm,
            )
        else:
            acquire_pinned_source(args.checkout, source_manifest)
            build_manifest = create_build_manifest(
                source_manifest=source_manifest,
                checkout_directory=args.checkout,
                node_executable=args.node,
                npm_executable=args.npm,
                probe_role=args.probe_role,
                cache_directory=args.npm_cache,
                home_directory=args.npm_home,
            )
            _write_new_manifest(args.output, canonicalize(build_manifest.to_dict()) + b"\n")
    except BuildOracleError as error:
        print(error.failure_class.value, file=sys.stderr)
        return 1
    except ValueError:
        print(OracleFailureClass.BUILD_FAILED.value, file=sys.stderr)
        return 1
    print("PASS: pinned Showdown source/build provenance verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
