"""Sentinel-only checks for the downstream native legal-choice capability."""

from __future__ import annotations

from typing import Any, NoReturn

from .errors import EngineArtifactError, EngineFailureClass


def _fail() -> NoReturn:
    raise EngineArtifactError(EngineFailureClass.SENTINEL_FAILED)


def _pokemon(native_module: Any, name: str, moves: list[Any], *, hp: int = 100) -> Any:
    return native_module.Pokemon(
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


def _state(
    native_module: Any,
    side_one: list[Any],
    *,
    force_switch: bool = False,
    force_trapped: bool = False,
) -> Any:
    return native_module.State(
        side_one=native_module.Side(
            pokemon=side_one,
            force_switch=force_switch,
            force_trapped=force_trapped,
        ),
        side_two=native_module.Side(
            pokemon=[
                _pokemon(
                    native_module,
                    "charmander",
                    [native_module.Move(id="ember", pp=32)],
                )
            ]
        ),
        weather="none",
        weather_turns_remaining=-1,
        terrain="none",
        terrain_turns_remaining=-1,
        trick_room=False,
        trick_room_turns_remaining=-1,
    )


def _checked_choices(
    native_module: Any,
    state: Any,
    expected_side_one: list[str],
    expected_side_two: list[str] | None = None,
) -> Any:
    try:
        choices = native_module.legal_choices(state)
    except BaseException as error:
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        _fail()
    if not isinstance(choices, tuple) or len(choices) != 2 or choices[0] != expected_side_one:
        _fail()
    if expected_side_two is not None and choices[1] != expected_side_two:
        _fail()
    return choices


def run_legal_choice_probe(native_module: Any) -> dict[str, Any]:
    """Return the canonical v2 capability result without invoking search."""

    try:
        ordinary = _state(
            native_module,
            [
                _pokemon(
                    native_module,
                    "squirtle",
                    [
                        native_module.Move(id="watergun", pp=32),
                        native_module.Move(id="tackle", pp=32),
                    ],
                )
            ],
        )
        ordinary_choices = _checked_choices(
            native_module, ordinary, ["watergun", "tackle"], ["ember"]
        )

        disabled = _state(
            native_module,
            [
                _pokemon(
                    native_module,
                    "squirtle",
                    [
                        native_module.Move(id="tackle", pp=32, disabled=True),
                        native_module.Move(id="watergun", pp=0),
                    ],
                )
            ],
        )
        disabled_choices = _checked_choices(native_module, disabled, ["No Move"])

        switching = _state(
            native_module,
            [
                _pokemon(
                    native_module,
                    "squirtle",
                    [native_module.Move(id="tackle", pp=32)],
                ),
                _pokemon(
                    native_module,
                    "pikachu",
                    [native_module.Move(id="tackle", pp=32)],
                ),
            ],
        )
        switching_choices = _checked_choices(native_module, switching, ["tackle", "switch pikachu"])

        trapped = _state(
            native_module,
            [
                _pokemon(
                    native_module,
                    "squirtle",
                    [native_module.Move(id="tackle", pp=32)],
                ),
                _pokemon(native_module, "pikachu", []),
            ],
            force_trapped=True,
        )
        trapped_choices = _checked_choices(native_module, trapped, ["tackle"])

        forced = _state(
            native_module,
            [
                _pokemon(
                    native_module,
                    "squirtle",
                    [native_module.Move(id="tackle", pp=32)],
                ),
                _pokemon(native_module, "pikachu", []),
            ],
            force_switch=True,
        )
        forced_choices = _checked_choices(native_module, forced, ["switch pikachu"])
    except EngineArtifactError:
        raise
    except BaseException as error:
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        _fail()

    before = ordinary.to_string()
    if ordinary.to_string() != before:
        _fail()
    choices = (
        ordinary_choices,
        disabled_choices,
        switching_choices,
        trapped_choices,
        forced_choices,
    )
    if any(
        choice != "No Move" and choice != choice.lower()
        for result in choices
        for side in result
        for choice in side
    ):
        _fail()
    return {
        "ordinary": ordinary_choices,
        "disabled_zero_pp": disabled_choices,
        "switching": switching_choices,
        "trapped": trapped_choices,
        "forced_switch": forced_choices,
    }


__all__ = ["run_legal_choice_probe"]
