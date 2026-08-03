import argparse
import json
from collections.abc import Sequence
from typing import TypedDict

from battlebelief_lab import __version__
from battlebelief_runtime.public_api import runtime_status


class LabStatus(TypedDict):
    package: str
    version: str
    phase: str
    entrypoint: str
    oracle_capability: str
    dataset_capability: str


def lab_status() -> LabStatus:
    runtime = runtime_status()
    if runtime["entrypoint"] != "ready":
        raise RuntimeError("battlebelief-runtime entrypoint is not ready")
    return {
        "package": "battlebelief-lab",
        "version": __version__,
        "phase": "M0",
        "entrypoint": "ready",
        "oracle_capability": "absent",
        "dataset_capability": "absent",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="battlebelief-lab")
    parser.add_argument("--version", action="store_true")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor", help="report M0 lab package readiness")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        print(lab_status()["version"])
        return 0
    if args.command == "doctor":
        print(json.dumps(lab_status(), sort_keys=True, separators=(",", ":")))
        return 0
    build_parser().print_help()
    return 0
