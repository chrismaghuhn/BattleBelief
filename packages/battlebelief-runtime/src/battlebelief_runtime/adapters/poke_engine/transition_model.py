"""Verified poke-engine implementation of the frozen Core transition port."""

from __future__ import annotations

import hashlib
import importlib
import importlib.machinery
import importlib.resources
import json
import math
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from types import ModuleType
from typing import Any, Literal, NoReturn, cast

from battlebelief_core.canonicalization import manifest_digest
from battlebelief_core.domain.actions import BattleSubmission, SafeSubmissionSet
from battlebelief_core.domain.engine_capabilities import CapabilityCatalog, CapabilityId
from battlebelief_core.domain.records.public_projection import (
    request_identity_digest,
    safe_submission_set_digest,
)
from battlebelief_core.domain.search import (
    InformationStateKey,
    PlayerView,
    PreparedRootIdentity,
    PreparedWorld,
    SearchAction,
    TransitionOutcome,
    TransitionSuccessor,
    TransitionWork,
)
from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_core.ports.transition_model import EngineBackendHealth
from battlebelief_runtime.search_status import EngineArtifactIdentity

from .action_mapper import (
    _ActionBinding,
    _ActionMappingError,
    binding_for_action,
    map_native_actions,
    map_root_actions,
    safe_submissions_from_document,
)
from .artifact import RuntimeEnvironment, VerifiedEngineArtifact, verify_installed_artifact
from .errors import EngineArtifactError, EngineFailureClass
from .mapping_report import (
    MappingReport,
    PokeEngineMappingFailure,
    RequiredCapabilities,
)
from .state_mapper import (
    _MappedNativeState,
    _StateMappingError,
    map_complete_world,
    map_native_state,
    map_observed_root,
)

_ADAPTER_ID = "battlebelief.poke-engine-transition"
_ADAPTER_VERSION = "1"
_EXPECTED_ARTIFACT_ADAPTER = "battlebelief-poke-engine-v2-legal-choices"
_EXPECTED_FEATURES = ("poke-engine/gen9", "poke-engine/terastallization")
_EXPECTED_CATALOG_DIGEST = "sha256:2adcf3c13b89f88c81a05368fd330fbc72fddcda91654433a04f8e21d75fdb11"
# adapter-source-digest:start
_EXPECTED_ADAPTER_SOURCE_DIGEST = (
    "sha256:453b854f6dfd7cff527cbcc15869873f0cd94df9660b1c5d1959af954975cc5f"
)
# adapter-source-digest:end
_EXPECTED_CORE_CONTRACT_DIGEST = (
    "sha256:3503a9f074adb2e8256420fe8366e735440a9dc7213e30ead080b230d31f0be3"
)
_SOURCE_FILES = (
    "__init__.py",
    "state_mapper.py",
    "action_mapper.py",
    "mapping_report.py",
    "transition_model.py",
)
_PERCENT_MASS_TOLERANCE = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class _VerifiedBackend:
    native: Any = field(repr=False, compare=False)
    artifact_identity: EngineArtifactIdentity
    backend_identity_digest: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class _PokeEngineWorld:
    """Deeply immutable adapter payload; native objects never cross the port."""

    native_state: str = field(repr=False)
    observed_state_digest: str = field(repr=False)
    root_player: Literal["p1", "p2"]
    view_digests: tuple[str, str] = field(repr=False)
    active_indexes: tuple[int, int]
    _active_types: tuple[tuple[str, str], tuple[str, str]]
    terastallized: tuple[bool, bool]
    terminal_outcome: Literal["p1", "p2", "tie"] | None
    public_hp: tuple[tuple[str, int], tuple[str, int]] = field(repr=False)
    root_bindings: tuple[_ActionBinding, ...] = field(repr=False)
    required_capabilities: tuple[CapabilityId, ...]
    report: MappingReport = field(repr=False)
    ply: int = 0


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _adapter_source_digest() -> str:
    root = Path(__file__).parent
    entries: list[dict[str, str]] = []
    try:
        for name in _SOURCE_FILES:
            data = (root / name).read_bytes().replace(b"\r\n", b"\n")
            if name == "transition_model.py":
                start = b"# adapter-source-digest:start\n"
                end = b"# adapter-source-digest:end\n"
                before, marked = data.split(start, maxsplit=1)
                _, after = marked.split(end, maxsplit=1)
                data = (
                    before
                    + start
                    + b'_EXPECTED_ADAPTER_SOURCE_DIGEST = "sha256:'
                    + b"0" * 64
                    + b'"\n'
                    + end
                    + after
                )
            entries.append({"name": name, "sha256": _sha256(data)})
    except (OSError, ValueError):
        return manifest_digest({"adapter_id": _ADAPTER_ID, "adapter_version": _ADAPTER_VERSION})
    return manifest_digest({"files": entries})


def _core_contract_digest() -> str:
    try:
        import battlebelief_core.domain.search as search_module
        import battlebelief_core.ports.transition_model as port_module

        paths = (Path(search_module.__file__), Path(port_module.__file__))
        return manifest_digest(
            {
                "files": [
                    {
                        "name": path.name,
                        "sha256": _sha256(path.read_bytes().replace(b"\r\n", b"\n")),
                    }
                    for path in paths
                ]
            }
        )
    except (OSError, TypeError):
        return manifest_digest({"contract": "battlebelief.transition-model.task26"})


def _conformance_digest() -> str:
    return manifest_digest(
        {
            "adapter_id": _ADAPTER_ID,
            "adapter_version": _ADAPTER_VERSION,
            "methods": [
                "prepare_root",
                "player_view",
                "information_state_key",
                "legal_actions",
                "transition",
                "is_terminal",
                "terminal_value",
            ],
        }
    )


def _backend_digest(identity: EngineArtifactIdentity) -> str:
    return manifest_digest(
        {
            "engine_source_manifest_digest": identity.source_manifest_digest,
            "artifact_index_digest": identity.artifact_index_digest,
            "environment_cell_id": identity.cell_id,
            "engine_build_manifest_digest": identity.build_manifest_digest,
            "wheel_digest": identity.wheel_sha256,
            "transition_adapter_id": _ADAPTER_ID,
            "transition_adapter_version": _ADAPTER_VERSION,
            "transition_adapter_source_digest": _adapter_source_digest(),
            "transition_model_contract_digest": _core_contract_digest(),
            "transition_adapter_conformance_digest": _conformance_digest(),
        }
    )


def _sanitize_failure(failure: PokeEngineMappingFailure) -> PokeEngineMappingFailure:
    """Remove interpreter exception chaining before a public failure escapes."""

    failure.__context__ = None
    failure.__cause__ = None
    failure.__suppress_context__ = True
    return failure


def _import_verified_native(verified: VerifiedEngineArtifact) -> ModuleType:
    previous_bytecode_setting = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        package = importlib.import_module("poke_engine")
        extension = importlib.import_module("poke_engine.poke_engine")
        package_path = Path(cast(str, package.__file__)).resolve(strict=True)
        extension_path = Path(cast(str, extension.__file__)).resolve(strict=True)
        package_expected = (verified.package_root / "__init__.py").resolve(strict=True)
        extension_expected = verified.extension_path.resolve(strict=True)
    except BaseException as error:
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        raise RuntimeError("verified native import failed") from None
    finally:
        sys.dont_write_bytecode = previous_bytecode_setting
    extension_spec = getattr(extension, "__spec__", None)
    if (
        package_path != package_expected
        or extension_path != extension_expected
        or extension_spec is None
        or not isinstance(extension_spec.loader, importlib.machinery.ExtensionFileLoader)
    ):
        raise RuntimeError("verified native origin mismatch")
    return package


def _load_catalog() -> CapabilityCatalog:
    relative = Path("artifacts/gen9ou/m2/engine-capability-catalog-v1.json")
    for parent in Path(__file__).resolve().parents:
        candidate = parent / relative
        if not candidate.is_file():
            continue
        try:
            document = json.loads(candidate.read_text(encoding="utf-8"))
            if not isinstance(document, Mapping):
                break
            catalog = CapabilityCatalog.from_document(document)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            break
        if catalog.catalog_digest == _EXPECTED_CATALOG_DIGEST:
            return catalog
        break
    raise ValueError("canonical capability catalog unavailable")


def _canonical_capabilities(values: tuple[CapabilityId, ...]) -> tuple[CapabilityId, ...]:
    return RequiredCapabilities.canonical(values).values


class PokeEngineTransitionModel:
    """Concrete verified Runtime adapter; it performs no eligibility decision."""

    def __init__(
        self,
        *,
        catalog: CapabilityCatalog,
        _artifact_environment: RuntimeEnvironment | None = None,
        _staged_wheel: Path | None = None,
    ) -> None:
        try:
            self._initialize(
                catalog=catalog,
                _artifact_environment=_artifact_environment,
                _staged_wheel=_staged_wheel,
            )
        except PokeEngineMappingFailure as failure:
            raise _sanitize_failure(failure) from None

    def _initialize(
        self,
        *,
        catalog: CapabilityCatalog,
        _artifact_environment: RuntimeEnvironment | None = None,
        _staged_wheel: Path | None = None,
    ) -> None:
        fallback_digest = manifest_digest({"adapter_id": _ADAPTER_ID, "state": "unavailable"})
        try:
            selected_catalog = catalog
            if selected_catalog.catalog_digest != _EXPECTED_CATALOG_DIGEST:
                self._raise_failure(
                    "capability_ambiguity", backend_digest=fallback_digest, work_units=0
                )
            if (
                _adapter_source_digest() != _EXPECTED_ADAPTER_SOURCE_DIGEST
                or _core_contract_digest() != _EXPECTED_CORE_CONTRACT_DIGEST
            ):
                self._raise_failure(
                    "adapter_identity_mismatch", backend_digest=fallback_digest, work_units=0
                )
            verified = verify_installed_artifact(
                environment=_artifact_environment, staged_wheel=_staged_wheel
            )
            identity = verified.identity
            if (
                identity.adapter_version != _EXPECTED_ARTIFACT_ADAPTER
                or identity.features != _EXPECTED_FEATURES
            ):
                self._raise_failure(
                    "artifact_identity_mismatch", backend_digest=fallback_digest, work_units=0
                )
            try:
                native = _import_verified_native(verified)
            except BaseException as error:
                if isinstance(error, (KeyboardInterrupt, SystemExit)):
                    raise
                self._raise_failure(
                    "adapter_identity_mismatch", backend_digest=fallback_digest, work_units=0
                )
            if not callable(getattr(native, "legal_choices", None)):
                self._raise_failure(
                    "adapter_identity_mismatch", backend_digest=fallback_digest, work_units=0
                )
        except PokeEngineMappingFailure:
            raise
        except EngineArtifactError as error:
            failure_class = (
                "artifact_identity_mismatch"
                if error.failure_class is EngineFailureClass.ARTIFACT_MISMATCH
                else "backend_unavailable"
            )
            self._raise_failure(failure_class, backend_digest=fallback_digest, work_units=0)
        except ValueError:
            self._raise_failure(
                "capability_ambiguity", backend_digest=fallback_digest, work_units=0
            )
        except BaseException as error:
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            self._raise_failure("backend_unavailable", backend_digest=fallback_digest, work_units=0)
        self._catalog = selected_catalog
        self._backend = _VerifiedBackend(
            native=native,
            artifact_identity=identity,
            backend_identity_digest=_backend_digest(identity),
        )
        self._backend_health = EngineBackendHealth.HEALTHY

    @property
    def backend_identity_digest(self) -> str:
        return self._backend.backend_identity_digest

    @property
    def backend_health(self) -> EngineBackendHealth:
        return self._backend_health

    def safe_submissions_from_document(self, document: Mapping[str, object]) -> SafeSubmissionSet:
        try:
            return safe_submissions_from_document(document)
        except _ActionMappingError as error:
            failure_class = error.failure_class
        self._raise_failure(failure_class, work_units=0)

    def prepare_battle_root(
        self,
        *,
        observed_state: ObservedState,
        safe_submissions: SafeSubmissionSet,
        complete_world: Mapping[str, object],
        ruleset_digest: str,
        root_identity: PreparedRootIdentity | None = None,
    ) -> PreparedWorld[_PokeEngineWorld]:
        try:
            return self._prepare_battle_root_impl(
                observed_state=observed_state,
                safe_submissions=safe_submissions,
                complete_world=complete_world,
                ruleset_digest=ruleset_digest,
                root_identity=root_identity,
            )
        except PokeEngineMappingFailure as failure:
            raise _sanitize_failure(failure) from None

    def _prepare_battle_root_impl(
        self,
        *,
        observed_state: ObservedState,
        safe_submissions: SafeSubmissionSet,
        complete_world: Mapping[str, object],
        ruleset_digest: str,
        root_identity: PreparedRootIdentity | None = None,
    ) -> PreparedWorld[_PokeEngineWorld]:
        observed_digest: str | None = None
        request_digest: str | None = None
        safe_digest: str | None = None
        try:
            observed = map_observed_root(observed_state)
            observed_digest = observed.digest
            request_digest = request_identity_digest(safe_submissions.request_identity)
            safe_digest = safe_submission_set_digest(safe_submissions)
            mapped = map_complete_world(
                self._backend.native,
                complete_world,
                observed.digest,
                public_hp=observed.public_hp,
            )
            expected_root = PreparedRootIdentity.create(
                request_identity_digest=request_digest,
                safe_submission_set_digest=safe_digest,
                observed_state_digest=observed.digest,
                root_player=observed.root_player,
                ruleset_digest=ruleset_digest,
                backend_identity_digest=self.backend_identity_digest,
                capability_catalog_digest=self._catalog.catalog_digest,
            )
            if root_identity is not None:
                if root_identity.request_identity_digest != request_digest:
                    self._raise_failure(
                        "request_identity_mismatch",
                        observed_digest=observed_digest,
                        request_digest=request_digest,
                        safe_digest=safe_digest,
                        work_units=0,
                    )
                if root_identity.safe_submission_set_digest != safe_digest:
                    self._raise_failure(
                        "safe_submission_mismatch",
                        observed_digest=observed_digest,
                        request_digest=request_digest,
                        safe_digest=safe_digest,
                        work_units=0,
                    )
                if (
                    root_identity.observed_state_digest != expected_root.observed_state_digest
                    or root_identity.root_player != expected_root.root_player
                    or root_identity.ruleset_digest != expected_root.ruleset_digest
                ):
                    self._raise_failure(
                        "safe_submission_mismatch",
                        observed_digest=observed_digest,
                        request_digest=request_digest,
                        safe_digest=safe_digest,
                        work_units=0,
                    )
            selected_root = expected_root if root_identity is None else root_identity
            if root_identity is not None:
                if root_identity.backend_identity_digest != expected_root.backend_identity_digest:
                    self._raise_failure(
                        "adapter_identity_mismatch",
                        observed_digest=observed_digest,
                        request_digest=request_digest,
                        safe_digest=safe_digest,
                        work_units=0,
                    )
                if (
                    root_identity.capability_catalog_digest
                    != expected_root.capability_catalog_digest
                ):
                    self._raise_failure(
                        "capability_ambiguity",
                        observed_digest=observed_digest,
                        request_digest=request_digest,
                        safe_digest=safe_digest,
                        work_units=0,
                    )
            state = self._state_from_string(mapped.native_state)
            choices = self._legal_choice_values(state)
            player_index = 0 if observed.root_player == "p1" else 1
            side = state.side_one if player_index == 0 else state.side_two
            team_ids = tuple(str(pokemon.id).lower() for pokemon in side.pokemon)
            active = side.pokemon[int(side.active_index)]
            active_move_ids = tuple(str(move.id).lower() for move in active.moves)
            root_bindings = map_root_actions(
                safe_set=safe_submissions,
                root_identity=selected_root,
                native_choices=choices[player_index],
                team_ids=team_ids,
                active_move_ids=active_move_ids,
                force_switch=bool(side.force_switch),
                catalog=self._catalog,
            )
            if {binding.native_choice for binding in root_bindings} != set(choices[player_index]):
                self._raise_failure(
                    "safe_submission_mismatch",
                    observed_digest=observed_digest,
                    request_digest=request_digest,
                    safe_digest=safe_digest,
                    work_units=0,
                )
            root_actions = tuple(binding.action for binding in root_bindings)
            requirements = self._preflight_capabilities(
                state, choices, root_bindings, observed.root_player
            )
            report = self._report(
                classification="mapped",
                observed_digest=observed_digest,
                request_digest=request_digest,
                safe_digest=safe_digest,
                capabilities=requirements,
                work_units=0,
            )
            world = _PokeEngineWorld(
                native_state=mapped.native_state,
                observed_state_digest=observed.digest,
                root_player=observed.root_player,
                view_digests=mapped.view_digests,
                active_indexes=mapped.active_indexes,
                _active_types=mapped.active_types,
                terastallized=mapped.terastallized,
                terminal_outcome=mapped.terminal_outcome,
                public_hp=mapped.public_hp,
                root_bindings=root_bindings,
                required_capabilities=requirements,
                report=report,
            )
            return self.prepare_root(world, root_identity=selected_root, root_actions=root_actions)
        except PokeEngineMappingFailure as failure:
            raise _sanitize_failure(failure) from None
        except (_StateMappingError, _ActionMappingError) as error:
            self._raise_failure(
                error.failure_class,
                observed_digest=observed_digest,
                request_digest=request_digest,
                safe_digest=safe_digest,
                work_units=0,
            )
        except (TypeError, ValueError):
            self._raise_failure(
                "unsupported_mapping",
                observed_digest=observed_digest,
                request_digest=request_digest,
                safe_digest=safe_digest,
                work_units=0,
            )
        except BaseException as error:
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            self._backend_health = EngineBackendHealth.UNHEALTHY
            self._raise_failure(
                "native_exception",
                observed_digest=observed_digest,
                request_digest=request_digest,
                safe_digest=safe_digest,
                work_units=0,
            )

    def prepare_root(
        self,
        world: _PokeEngineWorld,
        *,
        root_identity: PreparedRootIdentity,
        root_actions: tuple[SearchAction, ...],
    ) -> PreparedWorld[_PokeEngineWorld]:
        if not isinstance(world, _PokeEngineWorld):
            self._raise_failure("unsupported_mapping", work_units=0)
        if (
            root_identity.backend_identity_digest != self.backend_identity_digest
            or root_identity.capability_catalog_digest != self._catalog.catalog_digest
        ):
            self._raise_failure("adapter_identity_mismatch", work_units=0)
        if tuple(binding.action for binding in world.root_bindings) != root_actions:
            self._raise_failure("safe_submission_mismatch", work_units=0)
        try:
            return PreparedWorld(
                _opaque=world,
                root_identity=root_identity,
                root_actions=root_actions,
                required_capabilities=world.required_capabilities,
            )
        except (TypeError, ValueError):
            self._raise_failure("unsupported_mapping", work_units=0)

    def player_view(
        self, world: PreparedWorld[_PokeEngineWorld], player: Literal["p1", "p2"]
    ) -> PlayerView:
        index = self._player_index(player)
        try:
            return PlayerView(player=player, view_digest=world._opaque.view_digests[index])
        except (AttributeError, IndexError, TypeError, ValueError):
            self._raise_failure("inconsistent_player_view", work_units=0)

    def information_state_key(self, view: PlayerView) -> InformationStateKey:
        if not isinstance(view, PlayerView):
            self._raise_failure("inconsistent_player_view", work_units=0)
        return InformationStateKey(
            player=view.player,
            information_state_digest=manifest_digest(
                {
                    "player": view.player,
                    "view_digest": view.view_digest,
                }
            ),
        )

    def legal_actions(
        self, world: PreparedWorld[_PokeEngineWorld], player: Literal["p1", "p2"]
    ) -> tuple[SearchAction, ...]:
        try:
            index = self._player_index(player)
            if world._opaque.ply == 0 and player == world._opaque.root_player:
                return world.root_actions
            return tuple(binding.action for binding in self._deep_bindings(world, index))
        except PokeEngineMappingFailure as failure:
            raise _sanitize_failure(failure) from None

    def transition(
        self,
        world: PreparedWorld[_PokeEngineWorld],
        p1_action: SearchAction,
        p2_action: SearchAction,
    ) -> TransitionOutcome[_PokeEngineWorld]:
        try:
            return self._transition_impl(world, p1_action, p2_action)
        except PokeEngineMappingFailure as failure:
            raise _sanitize_failure(failure) from None

    def _transition_impl(
        self,
        world: PreparedWorld[_PokeEngineWorld],
        p1_action: SearchAction,
        p2_action: SearchAction,
    ) -> TransitionOutcome[_PokeEngineWorld]:
        try:
            state = self._state_from_string(world._opaque.native_state)
            choices = self._legal_choice_values(state)
            p1_binding = binding_for_action(
                self._bindings(world, 0, state=state, choices=choices), p1_action
            )
            p2_binding = binding_for_action(
                self._bindings(world, 1, state=state, choices=choices), p2_action
            )
        except _ActionMappingError:
            self._raise_failure("invalid_joint_action", work_units=0)
        try:
            instructions = self._generate_instructions(
                state, p1_binding.native_choice, p2_binding.native_choice
            )
        except PokeEngineMappingFailure as failure:
            raise _sanitize_failure(failure) from None
        except BaseException as error:
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            self._backend_health = EngineBackendHealth.UNHEALTHY
            self._raise_failure("native_exception", work_units=1)
        try:
            mapped_weights = self._mapped_successors(
                state,
                instructions,
                world._opaque.observed_state_digest,
                world._opaque.view_digests,
                world._opaque.public_hp,
            )
            capabilities = self._transition_capabilities(p1_action, p2_action)
            successors = self._successors(
                source=world,
                mapped_weights=mapped_weights,
                capabilities=capabilities,
            )
            denominator = sum(item.probability_numerator for item in successors)
            try:
                outcome = TransitionOutcome(
                    successors=successors,
                    probability_denominator=denominator,
                    work=TransitionWork(units=1),
                    required_capabilities=capabilities,
                )
                outcome.validate_against_source(world)
            except (TypeError, ValueError):
                self._raise_failure("work_accounting_inconsistency", work_units=1)
            return outcome
        except PokeEngineMappingFailure as failure:
            raise _sanitize_failure(failure) from None
        except (_StateMappingError, _ActionMappingError) as error:
            self._raise_failure(error.failure_class, work_units=1)
        except (InvalidOperation, ArithmeticError, TypeError, ValueError):
            self._raise_failure("chance_normalization_failure", work_units=1)
        except BaseException as error:
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            self._backend_health = EngineBackendHealth.UNHEALTHY
            self._raise_failure("malformed_native_result", work_units=1)

    def is_terminal(self, world: PreparedWorld[_PokeEngineWorld]) -> bool:
        return world._opaque.terminal_outcome is not None

    def terminal_value(
        self, world: PreparedWorld[_PokeEngineWorld], player: Literal["p1", "p2"]
    ) -> Fraction | None:
        self._player_index(player)
        outcome = world._opaque.terminal_outcome
        if outcome is None:
            return None
        if outcome == "tie":
            return Fraction(0)
        return Fraction(1 if outcome == player else -1)

    def root_submission(
        self, world: PreparedWorld[_PokeEngineWorld], action: SearchAction
    ) -> BattleSubmission:
        failure_class: str | None
        try:
            binding = binding_for_action(world._opaque.root_bindings, action)
        except _ActionMappingError:
            failure_class = "safe_submission_mismatch"
        else:
            failure_class = None
        if failure_class is not None:
            self._raise_failure(failure_class, work_units=0)
        if binding.submission is None:
            self._raise_failure("safe_submission_mismatch", work_units=0)
        return binding.submission

    def mapping_report(self, world: PreparedWorld[_PokeEngineWorld]) -> MappingReport:
        if not isinstance(world._opaque, _PokeEngineWorld):
            self._raise_failure("unsupported_mapping", work_units=0)
        return world._opaque.report

    def required_capabilities(self, world: PreparedWorld[_PokeEngineWorld]) -> RequiredCapabilities:
        return RequiredCapabilities(world.required_capabilities)

    def _state_from_string(self, value: str) -> Any:
        try:
            return self._backend.native.State.from_string(value)
        except BaseException as error:
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            self._backend_health = EngineBackendHealth.UNHEALTHY
            self._raise_failure("malformed_native_result", work_units=0)

    def _legal_choice_values(self, state: Any) -> tuple[tuple[str, ...], tuple[str, ...]]:
        try:
            result = self._backend.native.legal_choices(state)
        except BaseException as error:
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            self._backend_health = EngineBackendHealth.UNHEALTHY
            self._raise_failure("native_exception", work_units=0)
        if (
            not isinstance(result, tuple)
            or len(result) != 2
            or any(not isinstance(side, list) for side in result)
            or any(type(choice) is not str for side in result for choice in side)
        ):
            self._raise_failure("malformed_native_result", work_units=0)
        return (tuple(result[0]), tuple(result[1]))

    def _deep_bindings(
        self,
        world: PreparedWorld[_PokeEngineWorld],
        index: int,
        *,
        state: Any | None = None,
        choices: tuple[tuple[str, ...], tuple[str, ...]] | None = None,
    ) -> tuple[_ActionBinding, ...]:
        selected_state = (
            self._state_from_string(world._opaque.native_state) if state is None else state
        )
        selected_choices = self._legal_choice_values(selected_state) if choices is None else choices
        side = selected_state.side_one if index == 0 else selected_state.side_two
        try:
            return map_native_actions(
                native_choices=selected_choices[index],
                force_switch=bool(side.force_switch),
                catalog=self._catalog,
            )
        except _ActionMappingError as error:
            self._raise_failure(error.failure_class, work_units=0)

    def _bindings(
        self,
        world: PreparedWorld[_PokeEngineWorld],
        index: int,
        *,
        state: Any | None = None,
        choices: tuple[tuple[str, ...], tuple[str, ...]] | None = None,
    ) -> tuple[_ActionBinding, ...]:
        player = "p1" if index == 0 else "p2"
        if world._opaque.ply == 0 and player == world._opaque.root_player:
            return world._opaque.root_bindings
        return self._deep_bindings(world, index, state=state, choices=choices)

    def _generate_instructions(self, state: Any, p1_choice: str, p2_choice: str) -> Any:
        return self._backend.native.generate_instructions(state, p1_choice, p2_choice)

    def _mapped_successors(
        self,
        state: Any,
        instructions: object,
        observed_digest: str,
        prior_view_digests: tuple[str, str],
        public_hp: tuple[tuple[str, int], tuple[str, int]],
    ) -> tuple[tuple[_MappedNativeState, Fraction], ...]:
        if not isinstance(instructions, list) or not instructions:
            self._raise_failure("malformed_native_result", work_units=1)
        by_state: dict[str, tuple[_MappedNativeState, Fraction]] = {}
        percentages: list[Decimal] = []
        for instruction in instructions:
            percentage = getattr(instruction, "percentage", None)
            if type(percentage) not in {int, float} or isinstance(percentage, bool):
                self._raise_failure("chance_normalization_failure", work_units=1)
            numeric_percentage = cast(int | float, percentage)
            if not math.isfinite(float(numeric_percentage)) or float(numeric_percentage) <= 0:
                self._raise_failure("chance_normalization_failure", work_units=1)
            try:
                percentages.append(Decimal(str(numeric_percentage)))
            except (InvalidOperation, ValueError):
                self._raise_failure("chance_normalization_failure", work_units=1)
        if abs(sum(percentages, Decimal(0)) - Decimal(100)) > _PERCENT_MASS_TOLERANCE:
            self._raise_failure("chance_normalization_failure", work_units=1)
        for instruction in instructions:
            percentage = getattr(instruction, "percentage", None)
            if type(percentage) not in {int, float} or isinstance(percentage, bool):
                self._raise_failure("chance_normalization_failure", work_units=1)
            numeric_percentage = cast(int | float, percentage)
            if not math.isfinite(float(numeric_percentage)) or float(numeric_percentage) <= 0:
                self._raise_failure("chance_normalization_failure", work_units=1)
            weight = Fraction(Decimal(str(numeric_percentage)))
            try:
                successor_state = state.apply_instructions(instruction)
            except BaseException as error:
                if isinstance(error, (KeyboardInterrupt, SystemExit)):
                    raise
                self._backend_health = EngineBackendHealth.UNHEALTHY
                self._raise_failure("native_exception", work_units=1)
            mapped = map_native_state(
                self._backend.native,
                successor_state,
                observed_digest,
                prior_view_digests=prior_view_digests,
                source_state=state,
                public_hp=public_hp,
            )
            previous = by_state.get(mapped.native_state)
            by_state[mapped.native_state] = (
                mapped,
                weight if previous is None else previous[1] + weight,
            )
        total = sum((weight for _, weight in by_state.values()), Fraction(0))
        if total <= 0:
            self._raise_failure("chance_normalization_failure", work_units=1)
        normalized = tuple((mapped, weight / total) for mapped, weight in by_state.values())
        return tuple(sorted(normalized, key=lambda item: item[0].native_state))

    def _successors(
        self,
        *,
        source: PreparedWorld[_PokeEngineWorld],
        mapped_weights: tuple[tuple[_MappedNativeState, Fraction], ...],
        capabilities: tuple[CapabilityId, ...],
    ) -> tuple[TransitionSuccessor[_PokeEngineWorld], ...]:
        denominator = math.lcm(*(weight.denominator for _, weight in mapped_weights))
        result: list[TransitionSuccessor[_PokeEngineWorld]] = []
        for mapped, weight in mapped_weights:
            report = self._report(
                classification="transitioned",
                observed_digest=source._opaque.observed_state_digest,
                request_digest=source._opaque.report.request_identity_digest,
                safe_digest=source._opaque.report.safe_submission_set_digest,
                capabilities=capabilities,
                work_units=1,
            )
            payload = _PokeEngineWorld(
                native_state=mapped.native_state,
                observed_state_digest=source._opaque.observed_state_digest,
                root_player=source._opaque.root_player,
                view_digests=mapped.view_digests,
                active_indexes=mapped.active_indexes,
                _active_types=mapped.active_types,
                terastallized=mapped.terastallized,
                terminal_outcome=mapped.terminal_outcome,
                public_hp=mapped.public_hp,
                root_bindings=source._opaque.root_bindings,
                required_capabilities=_canonical_capabilities(
                    source.required_capabilities + capabilities
                ),
                report=report,
                ply=source._opaque.ply + 1,
            )
            prepared = PreparedWorld(
                _opaque=payload,
                root_identity=source.root_identity,
                root_actions=source.root_actions,
                required_capabilities=payload.required_capabilities,
            )
            outcome_id = manifest_digest(
                {
                    "native_state_digest": _sha256(mapped.native_state.encode("utf-8")),
                    "ply": payload.ply,
                }
            )
            result.append(
                TransitionSuccessor(
                    outcome_id=outcome_id,
                    world=prepared,
                    probability_numerator=weight.numerator * (denominator // weight.denominator),
                )
            )
        return tuple(sorted(result, key=lambda item: item.outcome_id))

    def _preflight_capabilities(
        self,
        _state: Any,
        _choices: tuple[tuple[str, ...], tuple[str, ...]],
        _root_bindings: tuple[_ActionBinding, ...],
        _root_player: Literal["p1", "p2"],
    ) -> tuple[CapabilityId, ...]:
        return _canonical_capabilities(
            tuple(
                self._catalog.id_for(definition.value) for definition in self._catalog.definitions
            )
        )

    def _transition_capabilities(
        self, p1_action: SearchAction, p2_action: SearchAction
    ) -> tuple[CapabilityId, ...]:
        values = [
            "gen9.transition.terminal.detection",
            "gen9.transition.terminal.value",
        ]
        if "move" in {p1_action.kind, p2_action.kind}:
            values.extend(
                (
                    "gen9.transition.chance.damage-roll",
                    "gen9.transition.move.direct-damage",
                    "gen9.transition.order.priority",
                    "gen9.transition.order.speed",
                )
            )
        if "switch" in {p1_action.kind, p2_action.kind}:
            values.append("gen9.transition.switch.active-slot")
            values.append("gen9.transition.order.speed")
        if any(
            capability.value == "gen9.legality.terastallization.activation"
            for action in (p1_action, p2_action)
            for capability in action.required_capabilities
        ):
            values.extend(
                (
                    "gen9.transition.terastallization.damage",
                    "gen9.transition.terastallization.type-change",
                )
            )
        return _canonical_capabilities(tuple(self._catalog.id_for(value) for value in values))

    @staticmethod
    def _player_index(player: object) -> int:
        if player == "p1":
            return 0
        if player == "p2":
            return 1
        raise PokeEngineMappingFailure(
            "inconsistent_player_view",
            report=MappingReport(
                classification="failed",
                adapter_id=_ADAPTER_ID,
                adapter_version=_ADAPTER_VERSION,
                backend_identity_digest=manifest_digest({"adapter_id": _ADAPTER_ID}),
                work_units=0,
                failure_class="inconsistent_player_view",
            ),
            work_units=0,
        )

    def _report(
        self,
        *,
        classification: str,
        observed_digest: str | None = None,
        request_digest: str | None = None,
        safe_digest: str | None = None,
        capabilities: tuple[CapabilityId, ...] = (),
        work_units: int,
        failure_class: str | None = None,
    ) -> MappingReport:
        return MappingReport(
            classification=classification,
            adapter_id=_ADAPTER_ID,
            adapter_version=_ADAPTER_VERSION,
            backend_identity_digest=self.backend_identity_digest,
            observed_state_digest=observed_digest,
            request_identity_digest=request_digest,
            safe_submission_set_digest=safe_digest,
            capability_ids=tuple(sorted({value.value for value in capabilities})),
            work_units=work_units,
            failure_class=failure_class,
        )

    def _raise_failure(
        self,
        failure_class: str,
        *,
        backend_digest: str | None = None,
        observed_digest: str | None = None,
        request_digest: str | None = None,
        safe_digest: str | None = None,
        work_units: int,
    ) -> NoReturn:
        digest = backend_digest
        if digest is None:
            backend = getattr(self, "_backend", None)
            digest = (
                backend.backend_identity_digest
                if isinstance(backend, _VerifiedBackend)
                else manifest_digest({"adapter_id": _ADAPTER_ID, "state": "unavailable"})
            )
        report = MappingReport(
            classification="failed",
            adapter_id=_ADAPTER_ID,
            adapter_version=_ADAPTER_VERSION,
            backend_identity_digest=digest,
            observed_state_digest=observed_digest,
            request_identity_digest=request_digest,
            safe_submission_set_digest=safe_digest,
            work_units=work_units,
            failure_class=failure_class,
        )
        raise PokeEngineMappingFailure(failure_class, report=report, work_units=work_units)


def _run_bounded_conformance_smoke(
    catalog: CapabilityCatalog,
    *,
    fixture_root: Path | None = None,
    _artifact_environment: RuntimeEnvironment | None = None,
    _staged_wheel: Path | None = None,
) -> MappingReport:
    """Run one reviewed Gen-9/Tera joint transition without search or claims."""

    from dataclasses import replace as replace_value

    selected_fixture_root = (
        importlib.resources.files("battlebelief_runtime.adapters.poke_engine").joinpath("fixtures")
        if fixture_root is None
        else fixture_root
    )
    observed_document = json.loads(
        selected_fixture_root.joinpath("observed_root_mapping.json").read_text(encoding="utf-8")
    )
    complete_world = json.loads(
        selected_fixture_root.joinpath("complete_world_mapping.json").read_text(encoding="utf-8")
    )
    joint_document = json.loads(
        selected_fixture_root.joinpath("joint_transition_mapping.json").read_text(encoding="utf-8")
    )
    if not all(
        isinstance(document, Mapping)
        for document in (observed_document, complete_world, joint_document)
    ):
        raise RuntimeError("bounded adapter fixtures are malformed")
    if (
        set(joint_document)
        != {"schema_version", "fixture_id", "p1_choice", "p2_choice", "expected"}
        or joint_document["schema_version"] != 1
        or not isinstance(joint_document["p1_choice"], str)
        or not isinstance(joint_document["p2_choice"], str)
        or not isinstance(joint_document["expected"], Mapping)
    ):
        raise RuntimeError("bounded joint fixture is malformed")
    observed = replace_value(
        ObservedState.initial("bounded-smoke"),
        room_initialized=True,
        generation=9,
        game_type="singles",
        tier="gen9ou",
        battle_started=True,
        our_side="p1",
        turn=1,
    )
    model = PokeEngineTransitionModel(
        catalog=catalog,
        _artifact_environment=_artifact_environment,
        _staged_wheel=_staged_wheel,
    )
    prepared = model.prepare_battle_root(
        observed_state=observed,
        safe_submissions=model.safe_submissions_from_document(observed_document),
        complete_world=complete_world,
        ruleset_digest=manifest_digest({"fixture": "task27-bounded-gen9-tera"}),
    )
    try:
        p1_action = next(
            binding.action
            for binding in prepared._opaque.root_bindings
            if binding.native_choice == joint_document["p1_choice"]
        )
        p2_action = next(
            binding.action
            for binding in model._deep_bindings(prepared, 1)
            if binding.native_choice == joint_document["p2_choice"]
        )
    except StopIteration:
        raise RuntimeError("bounded joint fixture choice is unavailable") from None
    outcome = model.transition(prepared, p1_action, p2_action)
    expected = joint_document["expected"]
    work_units = expected.get("work_units")
    minimum_successors = expected.get("minimum_successors")
    p1_terastallized = expected.get("p1_terastallized")
    p1_active_types = expected.get("p1_active_types")
    if (
        type(work_units) is not int
        or type(minimum_successors) is not int
        or type(p1_terastallized) is not bool
        or not isinstance(p1_active_types, list)
        or any(type(value) is not str for value in p1_active_types)
    ):
        raise RuntimeError("bounded joint fixture expectation is malformed")
    if (
        outcome.work != TransitionWork(work_units)
        or len(outcome.successors) < minimum_successors
        or any(
            successor.world._opaque.terastallized[0] is not p1_terastallized
            for successor in outcome.successors
        )
        or any(
            tuple(successor.world._opaque._active_types[0]) != tuple(p1_active_types)
            for successor in outcome.successors
        )
    ):
        raise RuntimeError("bounded adapter transition did not conform")
    return model.mapping_report(outcome.successors[0].world)


__all__ = ["PokeEngineTransitionModel"]
