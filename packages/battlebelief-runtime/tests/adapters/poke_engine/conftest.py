from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import SimpleNamespace

import pytest

from battlebelief_runtime.adapters.poke_engine.artifact import VerifiedEngineArtifact
from battlebelief_runtime.search_status import EngineArtifactIdentity


class _Index(StrEnum):
    P0 = "0"
    P1 = "1"
    P2 = "2"
    P3 = "3"
    P4 = "4"
    P5 = "5"


class _Weather(StrEnum):
    NONE = "none"


class _Terrain(StrEnum):
    NONE = "none"


@dataclass
class _Move:
    id: str = "none"
    pp: int = 16
    disabled: bool = False


class _Pokemon:
    def __init__(self, **values: object) -> None:
        defaults: dict[str, object] = {
            "id": "pikachu",
            "level": 50,
            "types": ("normal", "typeless"),
            "base_types": ("normal", "typeless"),
            "hp": 100,
            "maxhp": 100,
            "ability": "none",
            "base_ability": "none",
            "item": "none",
            "nature": "serious",
            "evs": (0, 0, 0, 0, 0, 0),
            "attack": 100,
            "defense": 100,
            "special_attack": 100,
            "special_defense": 100,
            "speed": 100,
            "status": "none",
            "tera_type": "typeless",
            "terastallized": False,
            "moves": [],
        }
        defaults.update(values)
        for name, value in defaults.items():
            setattr(self, name, value)


class _SideConditions:
    def __init__(self, **values: int) -> None:
        self.values = dict(values)


class _Side:
    def __init__(
        self,
        *,
        pokemon: list[_Pokemon] | None = None,
        active_index: _Index = _Index.P0,
        force_switch: bool = False,
        force_trapped: bool = False,
        side_conditions: _SideConditions | None = None,
        **_: object,
    ) -> None:
        self.pokemon = [] if pokemon is None else pokemon
        self.active_index = active_index
        self.force_switch = force_switch
        self.force_trapped = force_trapped
        self.side_conditions = side_conditions or _SideConditions()


@dataclass
class _Instructions:
    percentage: float
    state: str


class _State:
    def __init__(
        self,
        *,
        side_one: _Side | None = None,
        side_two: _Side | None = None,
        weather: _Weather = _Weather.NONE,
        weather_turns_remaining: int = 0,
        terrain: _Terrain = _Terrain.NONE,
        terrain_turns_remaining: int = 0,
        trick_room: bool = False,
        trick_room_turns_remaining: int = 0,
        team_preview: bool = False,
    ) -> None:
        self.side_one = side_one or _Side()
        self.side_two = side_two or _Side()
        self.weather = weather
        self.weather_turns_remaining = weather_turns_remaining
        self.terrain = terrain
        self.terrain_turns_remaining = terrain_turns_remaining
        self.trick_room = trick_room
        self.trick_room_turns_remaining = trick_room_turns_remaining
        self.team_preview = team_preview

    def to_string(self) -> str:
        def side(value: _Side) -> dict[str, object]:
            return {
                "active_index": int(value.active_index.value),
                "force_switch": value.force_switch,
                "force_trapped": value.force_trapped,
                "side_conditions": value.side_conditions.values,
                "pokemon": [
                    {
                        name: (
                            [
                                {"id": move.id, "pp": move.pp, "disabled": move.disabled}
                                for move in pokemon.moves
                            ]
                            if name == "moves"
                            else list(getattr(pokemon, name))
                            if name in {"types", "base_types", "evs"}
                            else getattr(pokemon, name)
                        )
                        for name in (
                            "id",
                            "level",
                            "types",
                            "base_types",
                            "hp",
                            "maxhp",
                            "ability",
                            "base_ability",
                            "item",
                            "nature",
                            "evs",
                            "attack",
                            "defense",
                            "special_attack",
                            "special_defense",
                            "speed",
                            "status",
                            "tera_type",
                            "terastallized",
                            "moves",
                        )
                    }
                    for pokemon in value.pokemon
                ],
            }

        return json.dumps(
            {
                "side_one": side(self.side_one),
                "side_two": side(self.side_two),
                "weather": str(self.weather),
                "weather_turns_remaining": self.weather_turns_remaining,
                "terrain": str(self.terrain),
                "terrain_turns_remaining": self.terrain_turns_remaining,
                "trick_room": self.trick_room,
                "trick_room_turns_remaining": self.trick_room_turns_remaining,
                "team_preview": self.team_preview,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_string(cls, value: str) -> _State:
        document = json.loads(value)

        def side(raw: dict[str, object]) -> _Side:
            pokemon = []
            for raw_pokemon in raw["pokemon"]:
                data = dict(raw_pokemon)
                data["types"] = tuple(data["types"])
                data["base_types"] = tuple(data["base_types"])
                data["evs"] = tuple(data["evs"])
                data["moves"] = [_Move(**move) for move in data["moves"]]
                pokemon.append(_Pokemon(**data))
            return _Side(
                pokemon=pokemon,
                active_index=getattr(_Index, f"P{raw['active_index']}"),
                force_switch=raw["force_switch"],
                force_trapped=raw["force_trapped"],
                side_conditions=_SideConditions(**raw["side_conditions"]),
            )

        return cls(
            side_one=side(document["side_one"]),
            side_two=side(document["side_two"]),
            weather=_Weather(document["weather"]),
            weather_turns_remaining=document["weather_turns_remaining"],
            terrain=_Terrain(document["terrain"]),
            terrain_turns_remaining=document["terrain_turns_remaining"],
            trick_room=document["trick_room"],
            trick_room_turns_remaining=document["trick_room_turns_remaining"],
            team_preview=document["team_preview"],
        )

    def apply_instructions(self, instructions: _Instructions) -> _State:
        return type(self).from_string(instructions.state)


def _choices(side: _Side) -> list[str]:
    active = side.pokemon[int(side.active_index.value)]
    switches = [
        f"switch {pokemon.id}"
        for index, pokemon in enumerate(side.pokemon)
        if index != int(side.active_index.value) and pokemon.hp > 0 and not side.force_trapped
    ]
    if side.force_switch:
        return switches or ["No Move"]
    moves: list[str] = []
    for move in active.moves:
        if move.pp > 0 and not move.disabled:
            moves.append(move.id)
            if not active.terastallized:
                moves.append(move.id + "-tera")
    return moves + switches or ["No Move"]


def _legal_choices(state: _State) -> tuple[list[str], list[str]]:
    return (_choices(state.side_one), _choices(state.side_two))


def _apply_choice(state: _State, side_index: int, choice: str, damage: int) -> None:
    sides = (state.side_one, state.side_two)
    side = sides[side_index]
    opponent = sides[1 - side_index]
    if choice.startswith("switch "):
        target = choice.removeprefix("switch ")
        side.active_index = getattr(
            _Index,
            f"P{next(index for index, pokemon in enumerate(side.pokemon) if pokemon.id == target)}",
        )
        side.force_switch = False
        return
    if choice == "No Move":
        return
    if choice.endswith("-tera"):
        side.pokemon[int(side.active_index.value)].terastallized = True
        choice = choice.removesuffix("-tera")
    if choice != "protect":
        target = opponent.pokemon[int(opponent.active_index.value)]
        target.hp = max(0, target.hp - damage)


def _generate_instructions(state: _State, p1_choice: str, p2_choice: str) -> list[_Instructions]:
    choices = _legal_choices(state)
    if p1_choice not in choices[0] or p2_choice not in choices[1]:
        raise RuntimeError("illegal fake native choice")
    result = []
    for percentage, damage in ((50.000004, 10), (49.999996, 12)):
        successor = _State.from_string(state.to_string())
        _apply_choice(successor, 0, p1_choice, damage)
        _apply_choice(successor, 1, p2_choice, damage)
        result.append(_Instructions(percentage=percentage, state=successor.to_string()))
    return result


def _native_module() -> SimpleNamespace:
    return SimpleNamespace(
        Move=_Move,
        Pokemon=_Pokemon,
        PokemonIndex=_Index,
        Side=_Side,
        SideConditions=_SideConditions,
        State=_State,
        Terrain=_Terrain,
        Weather=_Weather,
        legal_choices=_legal_choices,
        generate_instructions=_generate_instructions,
    )


def _identity() -> EngineArtifactIdentity:
    return EngineArtifactIdentity(
        artifact_index_digest="sha256:d098fb14aa802d2899c0479b7fa0e18ff7f42ffd1a915dafcd0bcb6e58bc60c6",
        source_manifest_digest="sha256:a7c079dd19bbd3c391cc11acd6fd6a46b803e26a59367d71796b900a7795ed6d",
        build_manifest_digest="sha256:4679464a2f8beaed0a2e20c650e6d0678559c82a01b8b4c553e22f60fe6d7861",
        wheel_sha256="sha256:5a212d8c93f4919f742a53392fbf9a93be7c00d30521842f212c0b5a195cb3a4",
        wheel_filename="poke_engine-0.0.49-cp314-none-win_amd64.whl",
        cell_id="windows-2025-x86_64-cp314",
        distribution_name="poke-engine",
        distribution_version="0.0.49",
        python_tag="cp314",
        abi_tag="none",
        platform_tag="win_amd64",
        operating_system="windows-2025",
        architecture="x86_64",
        features=("poke-engine/gen9", "poke-engine/terastallization"),
        adapter_version="battlebelief-poke-engine-v2-legal-choices",
        release_tag="engine-poke-engine-v0.0.49-bcf13823-v2-legal-choices-r1",
        release_asset_url=(
            "https://github.com/chrismaghuhn/BattleBelief/releases/download/"
            "engine-poke-engine-v0.0.49-bcf13823-v2-legal-choices-r1/"
            "poke_engine-0.0.49-cp314-none-win_amd64.whl"
        ),
        sentinel_fixture_digest="sha256:" + "1" * 64,
        sentinel_result_digest="sha256:" + "2" * 64,
        sentinel_configuration_digest="sha256:" + "3" * 64,
    )


@pytest.fixture(autouse=True)
def _verified_fake_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    from battlebelief_runtime.adapters.poke_engine import transition_model

    verified = VerifiedEngineArtifact(
        identity=_identity(),
        package_root=Path("verified-package"),
        extension_path=Path("verified-extension"),
    )
    monkeypatch.setattr(transition_model, "verify_installed_artifact", lambda **_: verified)
    monkeypatch.setattr(transition_model, "_import_verified_native", lambda _: _native_module())
