"""Exercise the installed v3 native action-order binding without search."""

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
from battlebelief_runtime.adapters.poke_engine.native_probe import load_fixture_bundle  # noqa: E402
from tools.create_engine_artifact_index_v3 import (  # noqa: E402
    ArtifactIndexV3Error,
    _strict_canonical,
)


class ResolvedActionOrderSmokeError(RuntimeError):
    """A controlled v3 native-binding sentinel failure."""


def _fail(message: str) -> NoReturn:
    raise ResolvedActionOrderSmokeError(message)


def _state(native_module: Any, *, side_one_speed: int, side_two_speed: int) -> Any:
    def pokemon(name: str, speed: int) -> Any:
        return native_module.Pokemon(
            id=name,
            level=100,
            types=("normal", "typeless"),
            base_types=("normal", "typeless"),
            hp=100,
            maxhp=100,
            attack=100,
            defense=100,
            special_attack=100,
            special_defense=100,
            speed=speed,
            terastallized=False,
            moves=[native_module.Move(id="tackle", pp=32)],
        )

    return native_module.State(
        side_one=native_module.Side(pokemon=[pokemon("squirtle", side_one_speed)]),
        side_two=native_module.Side(pokemon=[pokemon("charmander", side_two_speed)]),
        weather="none",
        weather_turns_remaining=-1,
        terrain="none",
        terrain_turns_remaining=-1,
        trick_room=False,
        trick_room_turns_remaining=-1,
    )


def _orders(
    native_module: Any, *, side_one_speed: int, side_two_speed: int
) -> list[tuple[str, str]]:
    state = _state(native_module, side_one_speed=side_one_speed, side_two_speed=side_two_speed)
    before = state.to_string()
    branches = native_module.generate_instructions(state, "tackle", "tackle")
    if not isinstance(branches, list) or not branches or state.to_string() != before:
        _fail("native transition semantics differ")
    orders: list[tuple[str, str]] = []
    for branch in branches:
        order = getattr(branch, "resolved_action_order", None)
        if (
            not isinstance(order, tuple)
            or order not in (("p1", "p2"), ("p2", "p1"))
            or not isinstance(branch.percentage, float)
            or not isinstance(branch.instruction_list, list)
        ):
            _fail("native order binding differs")
        orders.append(order)
    return orders


def _run_checks() -> dict[str, Any]:
    import poke_engine  # type: ignore[import-not-found]

    legal_choices = run_legal_choice_probe(poke_engine)
    faster_p1 = _orders(poke_engine, side_one_speed=120, side_two_speed=80)
    faster_p2 = _orders(poke_engine, side_one_speed=80, side_two_speed=120)
    if set(faster_p1) != {("p1", "p2")} or set(faster_p2) != {("p2", "p1")}:
        _fail("native order authority differs")
    return {
        "legal_choices": legal_choices,
        "faster_p1": [list(order) for order in faster_p1],
        "faster_p2": [list(order) for order in faster_p2],
    }


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
        if source.get("schema_id") != "urn:battlebelief:schema:manifest:engine-source:v3":
            _fail("source manifest identity differs")
        if (
            build.get("schema_id") != "urn:battlebelief:schema:manifest:engine-build:v3"
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
            "schema_version": 3,
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
        ArtifactIndexV3Error,
        OSError,
        ResolvedActionOrderSmokeError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        print(f"resolved-action-order smoke failed: {error}", file=sys.stderr)
        return 1
    print(f"resolved_action_order_result_digest={result_digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
