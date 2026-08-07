"""Private, sentinel-only use of the verified native extension."""

from __future__ import annotations

import importlib
import importlib.machinery
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, NoReturn

from battlebelief_core.canonicalization import manifest_digest
from battlebelief_runtime.search_status import EngineAvailability

from .artifact import VerifiedEngineArtifact
from .errors import EngineArtifactError, EngineFailureClass
from .legal_choice_probe import run_legal_choice_probe

_DEFAULT_FIXTURE_ROOT = Path(__file__).with_name("fixtures")


@dataclass(frozen=True, slots=True)
class FixtureBundle:
    transition: dict[str, Any]
    tera_transition: dict[str, Any]
    search: dict[str, Any]
    fixture_digest: str
    configuration_digest: str


def _fail(failure_class: EngineFailureClass) -> NoReturn:
    raise EngineArtifactError(failure_class)


def _strict_fixture(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                _fail(EngineFailureClass.SENTINEL_FAILED)
            result[key] = value
        return result

    def reject_nonfinite_constant(_: str) -> NoReturn:
        _fail(EngineFailureClass.SENTINEL_FAILED)

    try:
        value = json.loads(
            path.read_bytes(),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_nonfinite_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _fail(EngineFailureClass.SENTINEL_FAILED)
    if not isinstance(value, dict):
        _fail(EngineFailureClass.SENTINEL_FAILED)
    return value


def load_fixture_bundle(fixture_root: Path = _DEFAULT_FIXTURE_ROOT) -> FixtureBundle:
    transition = _strict_fixture(fixture_root / "gen9_transition.json")
    tera_transition = _strict_fixture(fixture_root / "gen9_tera_transition.json")
    search = _strict_fixture(fixture_root / "minimal_search.json")
    if (
        transition.get("schema_version") != 1
        or transition.get("fixture_id") != "gen9-transition-v1"
        or tera_transition
        != {
            "expected_side_one_terastallized": True,
            "fixture_id": "gen9-tera-transition-v1",
            "schema_version": 1,
            "side_one_choice": "tackle-tera",
            "side_two_choice": "tackle",
        }
        or search
        != {
            "duration_ms": 5,
            "fixture_id": "gen9-minimal-search-v1",
            "iterations": 1000,
            "schema_version": 1,
            "threads": 1,
        }
    ):
        _fail(EngineFailureClass.SENTINEL_FAILED)
    fixture_document = {
        "gen9_transition": transition,
        "gen9_tera_transition": tera_transition,
        "minimal_search": search,
    }
    try:
        fixture_digest = manifest_digest(fixture_document)
        configuration_digest = manifest_digest(search)
    except (TypeError, ValueError):
        _fail(EngineFailureClass.SENTINEL_FAILED)
    return FixtureBundle(
        transition=transition,
        tera_transition=tera_transition,
        search=search,
        fixture_digest=fixture_digest,
        configuration_digest=configuration_digest,
    )


def _native_state(native_module: Any, document: dict[str, Any]) -> Any:
    state = document.get("state")
    if not isinstance(state, dict):
        _fail(EngineFailureClass.SENTINEL_FAILED)

    def side(name: str) -> Any:
        side_document = state.get(name)
        if not isinstance(side_document, dict):
            _fail(EngineFailureClass.SENTINEL_FAILED)
        pokemon_document = side_document.get("pokemon")
        if not isinstance(pokemon_document, dict):
            _fail(EngineFailureClass.SENTINEL_FAILED)
        moves_document = pokemon_document.get("moves")
        if not isinstance(moves_document, list) or len(moves_document) != 2:
            _fail(EngineFailureClass.SENTINEL_FAILED)
        moves = []
        for move in moves_document:
            if not isinstance(move, dict):
                _fail(EngineFailureClass.SENTINEL_FAILED)
            moves.append(
                native_module.Move(
                    id=move.get("id"),
                    pp=move.get("pp"),
                    disabled=move.get("disabled"),
                )
            )
        types = pokemon_document.get("types")
        base_types = pokemon_document.get("base_types")
        if (
            not isinstance(types, list)
            or len(types) != 2
            or not isinstance(base_types, list)
            or len(base_types) != 2
        ):
            _fail(EngineFailureClass.SENTINEL_FAILED)
        pokemon = native_module.Pokemon(
            id=pokemon_document.get("id"),
            types=tuple(types),
            base_types=tuple(base_types),
            hp=pokemon_document.get("hp"),
            maxhp=pokemon_document.get("maxhp"),
            ability=pokemon_document.get("ability"),
            tera_type=pokemon_document.get("tera_type"),
            moves=moves,
        )
        return native_module.Side(pokemon=[pokemon])

    return native_module.State(side_one=side("side_one"), side_two=side("side_two"))


def _serialized_state(state: Any) -> str:
    value = state.to_string()
    if not isinstance(value, str) or not value:
        _fail(EngineFailureClass.NATIVE_UNHEALTHY)
    return value


def execute_native_probe(native_module: Any, bundle: FixtureBundle) -> dict[str, Any]:
    """Exercise stable Gen-9 health facts without exporting native objects."""

    transition = bundle.transition
    state = _native_state(native_module, transition)
    original = _serialized_state(state)
    instructions = native_module.generate_instructions(
        state,
        transition["side_one_choice"],
        transition["side_two_choice"],
    )
    if not isinstance(instructions, list) or not instructions:
        _fail(EngineFailureClass.NATIVE_UNHEALTHY)
    applied = state.apply_instructions(instructions[0])
    applied_serialized = _serialized_state(applied)
    if applied_serialized == original:
        _fail(EngineFailureClass.NATIVE_UNHEALTHY)
    reversed_state = applied.reverse_instructions(instructions[0])
    if _serialized_state(reversed_state) != original:
        _fail(EngineFailureClass.NATIVE_UNHEALTHY)

    tera = bundle.tera_transition
    tera_state = _native_state(native_module, transition)
    tera_original = _serialized_state(tera_state)
    tera_instructions = native_module.generate_instructions(
        tera_state,
        tera["side_one_choice"],
        tera["side_two_choice"],
    )
    if not isinstance(tera_instructions, list) or not tera_instructions:
        _fail(EngineFailureClass.NATIVE_UNHEALTHY)
    tera_applied = tera_state.apply_instructions(tera_instructions[0])
    if _serialized_state(tera_applied) == tera_original or (
        tera_applied.side_one.pokemon[0].terastallized
        is not tera["expected_side_one_terastallized"]
    ):
        _fail(EngineFailureClass.NATIVE_UNHEALTHY)
    if _serialized_state(tera_applied.reverse_instructions(tera_instructions[0])) != (
        tera_original
    ):
        _fail(EngineFailureClass.NATIVE_UNHEALTHY)

    search = bundle.search
    search_state = _native_state(native_module, transition)
    search_result = native_module.monte_carlo_tree_search(
        search_state,
        duration_ms=search["duration_ms"],
        iterations=search["iterations"],
        threads=search["threads"],
    )
    side_one = search_result.side_one
    side_two = search_result.side_two
    total_visits = search_result.total_visits
    if (
        not isinstance(side_one, list)
        or not side_one
        or not isinstance(side_two, list)
        or not side_two
        or not isinstance(total_visits, int)
        or total_visits != search["iterations"]
    ):
        _fail(EngineFailureClass.NATIVE_UNHEALTHY)
    return healthy_probe_result(bundle)


def healthy_probe_result(bundle: FixtureBundle) -> dict[str, Any]:
    """Return the only stable result document accepted from a healthy probe."""

    return {
        "schema_version": 1,
        "adapter_version": "battlebelief-poke-engine-v1",
        "classification": "healthy",
        "fixture_digest": bundle.fixture_digest,
        "configuration_digest": bundle.configuration_digest,
        "health": {
            "gen9_state_created": True,
            "native_choices_enumerated": True,
            "normal_transition_applied": True,
            "reverse_round_trip": True,
            "tera_transition_applied": True,
            "tera_state_changed": True,
            "minimal_search_completed": True,
            "native_search_nonempty": True,
            "bounded_search_configuration": True,
        },
    }


def _import_verified_native(verified: VerifiedEngineArtifact) -> ModuleType:
    previous_bytecode_setting = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        native = importlib.import_module("poke_engine")
        extension = importlib.import_module("poke_engine.poke_engine")
    except BaseException as error:
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        _fail(EngineFailureClass.IMPORT_FAILED)
    finally:
        sys.dont_write_bytecode = previous_bytecode_setting
    package_origin = getattr(native, "__file__", None)
    extension_origin = getattr(extension, "__file__", None)
    extension_spec = getattr(extension, "__spec__", None)
    if not isinstance(package_origin, str) or not isinstance(extension_origin, str):
        _fail(EngineFailureClass.IMPORT_FAILED)
    try:
        package_path = Path(package_origin).resolve(strict=True)
        extension_path = Path(extension_origin).resolve(strict=True)
        expected_package_path = (verified.package_root / "__init__.py").resolve(strict=True)
        expected_extension_path = verified.extension_path.resolve(strict=True)
    except (OSError, RuntimeError, TypeError):
        _fail(EngineFailureClass.IMPORT_FAILED)
    if package_path != expected_package_path or extension_path != expected_extension_path:
        _fail(EngineFailureClass.IMPORT_FAILED)
    if extension_spec is None or not isinstance(
        extension_spec.loader, importlib.machinery.ExtensionFileLoader
    ):
        _fail(EngineFailureClass.IMPORT_FAILED)
    return native


def run_native_probe(
    verified: VerifiedEngineArtifact,
    *,
    fixture_root: Path = _DEFAULT_FIXTURE_ROOT,
    native_module: Any | None = None,
) -> EngineAvailability:
    """Run the private probe and bind only its stable canonical result."""

    bundle = load_fixture_bundle(fixture_root)
    if (
        bundle.fixture_digest != verified.identity.sentinel_fixture_digest
        or bundle.configuration_digest != verified.identity.sentinel_configuration_digest
    ):
        _fail(EngineFailureClass.SENTINEL_FAILED)
    native = _import_verified_native(verified) if native_module is None else native_module
    try:
        if verified.identity.adapter_version == "battlebelief-poke-engine-v2-legal-choices":
            result = run_legal_choice_probe(native)
        else:
            result = execute_native_probe(native, bundle)
    except EngineArtifactError:
        raise
    except BaseException as error:
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        _fail(EngineFailureClass.NATIVE_UNHEALTHY)
    if manifest_digest(result) != verified.identity.sentinel_result_digest:
        _fail(EngineFailureClass.SENTINEL_FAILED)
    return EngineAvailability(status="available", identity=verified.identity, failure_class=None)


__all__: list[str] = []
