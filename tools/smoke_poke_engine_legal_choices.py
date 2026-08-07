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
from battlebelief_runtime.adapters.poke_engine.native_probe import (  # noqa: E402
    load_fixture_bundle,
)


def _pokemon(name: str, moves: list[Any], *, hp: int = 100) -> Any:
    from poke_engine import Pokemon  # type: ignore[import-not-found]

    return Pokemon(
        id=name,
        level=100,
        types=("normal", "typeless"),
        base_types=("normal", "typeless"),
        hp=hp,
        maxhp=100,
        attack=100,
        defense=100,
        special_attack=100,
        special_defense=100,
        speed=100,
        terastallized=True,
        moves=moves,
    )


def _state(side_one: list[Any], *, force_switch: bool = False, force_trapped: bool = False) -> Any:
    from poke_engine import Move, Side, State  # type: ignore[import-not-found]

    return State(
        side_one=Side(
            pokemon=side_one,
            force_switch=force_switch,
            force_trapped=force_trapped,
        ),
        side_two=Side(pokemon=[_pokemon("charmander", [Move(id="ember", pp=32)])]),
        weather="none",
        weather_turns_remaining=-1,
        terrain="none",
        terrain_turns_remaining=-1,
        trick_room=False,
        trick_room_turns_remaining=-1,
    )


def _run_checks() -> dict[str, Any]:
    from poke_engine import Move, legal_choices  # type: ignore[import-not-found]

    ordinary = _state(
        [_pokemon("squirtle", [Move(id="watergun", pp=32), Move(id="tackle", pp=32)])]
    )
    if legal_choices(ordinary) != (["watergun", "tackle"], ["ember"]):
        raise ValueError("ordinary native legal choices differ")

    disabled = _state(
        [
            _pokemon(
                "squirtle",
                [Move(id="tackle", pp=32, disabled=True), Move(id="watergun", pp=0)],
            )
        ]
    )
    disabled_choices = legal_choices(disabled)
    if disabled_choices[0] != ["No Move"] or any(
        choice == "watergun" for choice in disabled_choices[0]
    ):
        raise ValueError("disabled or zero-PP move was enumerated")

    switching = _state(
        [
            _pokemon("squirtle", [Move(id="tackle", pp=32)]),
            _pokemon("pikachu", [Move(id="tackle", pp=32)]),
        ]
    )
    if legal_choices(switching)[0] != ["tackle", "switch pikachu"]:
        raise ValueError("legal switch choices differ")

    trapped = _state(
        [_pokemon("squirtle", [Move(id="tackle", pp=32)]), _pokemon("pikachu", [])],
        force_trapped=True,
    )
    if legal_choices(trapped)[0] != ["tackle"]:
        raise ValueError("trapped state exposed a switch")

    forced = _state(
        [_pokemon("squirtle", [Move(id="tackle", pp=32)]), _pokemon("pikachu", [])],
        force_switch=True,
    )
    if legal_choices(forced)[0] != ["switch pikachu"]:
        raise ValueError("forced-switch state exposed a non-switch choice")

    before = ordinary.to_string()
    canonical = legal_choices(ordinary)
    if ordinary.to_string() != before:
        raise ValueError("legal-choice enumeration mutated the caller state")
    if any(
        choice != "No Move" and choice != choice.lower() for side in canonical for choice in side
    ):
        raise ValueError("native choice strings are not canonical")
    return {
        "ordinary": canonical,
        "disabled_zero_pp": disabled_choices,
        "switching": legal_choices(switching),
        "trapped": legal_choices(trapped),
        "forced_switch": legal_choices(forced),
    }


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
