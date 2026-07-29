import argparse
import json
from collections.abc import Sequence

from .public_api import runtime_status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="battlebelief")
    parser.add_argument("--version", action="store_true")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor", help="report M0 package readiness")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        print(runtime_status()["version"])
        return 0
    if args.command == "doctor":
        print(json.dumps(runtime_status(), sort_keys=True, separators=(",", ":")))
        return 0
    build_parser().print_help()
    return 0
