"""Opaque, immutable values shared by engine-neutral information-set search."""

from __future__ import annotations

import re
from collections.abc import MutableMapping, MutableSequence, MutableSet
from dataclasses import dataclass, field, fields, is_dataclass
from decimal import Decimal
from enum import Enum
from fractions import Fraction
from typing import Literal, Self, cast

from battlebelief_core.canonicalization import manifest_digest
from battlebelief_core.domain.engine_capabilities import CapabilityId

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_INTERNAL_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*)+$")
_PLAYERS = frozenset({"p1", "p2"})
_ACTION_KINDS = frozenset({"move", "switch", "pass"})
_MUTABLE_OPAQUE_TYPES = (MutableMapping, MutableSequence, MutableSet, bytearray)


def _require_deeply_immutable_payload(value: object, seen: frozenset[int] = frozenset()) -> None:
    """Accept only recursively immutable adapter values without exposing their contents."""

    if isinstance(value, _MUTABLE_OPAQUE_TYPES):
        raise ValueError("prepared world payload must be a deeply immutable adapter value")
    if type(value) in {type(None), bool, int, float, complex, str, bytes, Decimal, Fraction}:
        return
    if isinstance(value, Enum):
        _require_deeply_immutable_payload(value.value, seen)
        return
    identity = id(value)
    if identity in seen:
        raise ValueError("prepared world payload must not contain reference cycles")
    nested_seen = seen | {identity}
    if type(value) is tuple:
        for item in cast(tuple[object, ...], value):
            _require_deeply_immutable_payload(item, nested_seen)
        return
    if type(value) is frozenset:
        for item in cast(frozenset[object], value):
            _require_deeply_immutable_payload(item, nested_seen)
        return
    if is_dataclass(value) and not isinstance(value, type):
        parameters = getattr(type(value), "__dataclass_params__", None)
        if parameters is not None and parameters.frozen:
            for item in fields(value):
                _require_deeply_immutable_payload(getattr(value, item.name), nested_seen)
            return
    raise ValueError("prepared world payload must be a deeply immutable adapter value")


def _digest(value: object, name: str) -> str:
    if type(value) is not str or not _DIGEST_RE.fullmatch(value):
        raise ValueError(f"{name} must be a sha256 digest")
    return value


def _player(value: object, name: str = "player") -> Literal["p1", "p2"]:
    if type(value) is not str or value not in _PLAYERS:
        raise ValueError(f"{name} must be p1 or p2")
    return value  # type: ignore[return-value]


def _internal_id(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or not (_INTERNAL_ID_RE.fullmatch(value) or _DIGEST_RE.fullmatch(value))
    ):
        raise ValueError("invalid private transition identifier")
    return value


def _capabilities(values: tuple[CapabilityId, ...], catalog_digest: str | None = None) -> None:
    if type(values) is not tuple or any(not isinstance(value, CapabilityId) for value in values):
        raise ValueError("required_capabilities must be a tuple of CapabilityId values")
    identifiers = tuple(value.value for value in values)
    digests = {value.catalog_digest for value in values}
    if identifiers != tuple(sorted(identifiers)) or len(set(identifiers)) != len(identifiers):
        raise ValueError("required_capabilities must be uniquely sorted by value")
    if len(digests) > 1 or (catalog_digest is not None and digests and digests != {catalog_digest}):
        raise ValueError("required_capabilities must use one matching catalog")


@dataclass(frozen=True, slots=True, init=False)
class PreparedRootIdentity:
    request_identity_digest: str = field(repr=False)
    safe_submission_set_digest: str = field(repr=False)
    observed_state_digest: str = field(repr=False)
    prepared_root_digest: str = field(repr=False)
    ruleset_digest: str = field(repr=False)
    backend_identity_digest: str = field(repr=False)
    capability_catalog_digest: str = field(repr=False)
    root_player: Literal["p1", "p2"]

    def __init__(self, *_: object, **__: object) -> None:
        raise TypeError("PreparedRootIdentity values are created by PreparedRootIdentity.create")

    @classmethod
    def create(
        cls,
        *,
        request_identity_digest: str,
        safe_submission_set_digest: str,
        observed_state_digest: str,
        root_player: Literal["p1", "p2"],
        ruleset_digest: str,
        backend_identity_digest: str,
        capability_catalog_digest: str,
    ) -> Self:
        for name, value in (
            ("request_identity_digest", request_identity_digest),
            ("safe_submission_set_digest", safe_submission_set_digest),
            ("observed_state_digest", observed_state_digest),
            ("ruleset_digest", ruleset_digest),
            ("backend_identity_digest", backend_identity_digest),
            ("capability_catalog_digest", capability_catalog_digest),
        ):
            _digest(value, name)
        _player(root_player, "root_player")
        instance = object.__new__(cls)
        for name, value in (
            ("request_identity_digest", request_identity_digest),
            ("safe_submission_set_digest", safe_submission_set_digest),
            ("observed_state_digest", observed_state_digest),
            ("ruleset_digest", ruleset_digest),
            ("backend_identity_digest", backend_identity_digest),
            ("capability_catalog_digest", capability_catalog_digest),
            ("root_player", root_player),
        ):
            object.__setattr__(instance, name, value)
        object.__setattr__(
            instance,
            "prepared_root_digest",
            manifest_digest(
                {
                    "request_identity_digest": request_identity_digest,
                    "safe_submission_set_digest": safe_submission_set_digest,
                    "observed_state_digest": observed_state_digest,
                    "root_player": root_player,
                    "ruleset_digest": ruleset_digest,
                    "backend_identity_digest": backend_identity_digest,
                    "capability_catalog_digest": capability_catalog_digest,
                }
            ),
        )
        return instance


@dataclass(frozen=True, slots=True, eq=False)
class PreparedWorld[WorldT]:
    """Opaque adapter-owned world bound to one immutable prepared root."""

    _opaque: WorldT = field(repr=False, compare=False)
    root_identity: PreparedRootIdentity
    root_actions: tuple[SearchAction, ...] = field(repr=False)
    required_capabilities: tuple[CapabilityId, ...]

    def __post_init__(self) -> None:
        _require_deeply_immutable_payload(self._opaque)
        if not isinstance(self.root_identity, PreparedRootIdentity):
            raise ValueError("root_identity must be a PreparedRootIdentity")
        if type(self.root_actions) is not tuple or any(
            not isinstance(action, SearchAction) for action in self.root_actions
        ):
            raise ValueError("root_actions must be a tuple of SearchAction values")
        for index, action in enumerate(self.root_actions):
            if action.root_identity != self.root_identity or action.root_submission_index != index:
                raise ValueError("root_actions must be canonical root actions for this root")
        _capabilities(self.required_capabilities, self.root_identity.capability_catalog_digest)

    def public_summary(self) -> dict[str, object]:
        """Return the canonical public identity without serializing the payload."""

        return {
            "prepared_root_digest": self.root_identity.prepared_root_digest,
            "root_action_count": len(self.root_actions),
            "required_capability_count": len(self.required_capabilities),
        }


@dataclass(frozen=True, slots=True)
class SearchAction:
    action_id: str = field(repr=False)
    kind: Literal["move", "switch", "pass"] = "pass"
    required_capabilities: tuple[CapabilityId, ...] = ()
    root_submission_index: int | None = None
    root_identity: PreparedRootIdentity | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _internal_id(self.action_id)
        if type(self.kind) is not str or self.kind not in _ACTION_KINDS:
            raise ValueError("invalid search action")
        if (self.root_submission_index is None) != (self.root_identity is None):
            raise ValueError("invalid search action")
        if self.root_submission_index is not None and (
            type(self.root_submission_index) is not int or self.root_submission_index < 0
        ):
            raise ValueError("invalid search action")
        if self.root_identity is not None and not isinstance(
            self.root_identity, PreparedRootIdentity
        ):
            raise ValueError("invalid search action")
        _capabilities(
            self.required_capabilities,
            None if self.root_identity is None else self.root_identity.capability_catalog_digest,
        )

    def public_summary(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "required_capability_count": len(self.required_capabilities),
            "is_root_action": self.root_identity is not None,
        }


@dataclass(frozen=True, slots=True)
class PlayerView:
    player: Literal["p1", "p2"]
    view_digest: str = field(repr=False)

    def __post_init__(self) -> None:
        _player(self.player)
        _digest(self.view_digest, "view_digest")


@dataclass(frozen=True, slots=True)
class InformationStateKey:
    player: Literal["p1", "p2"]
    information_state_digest: str = field(repr=False)

    def __post_init__(self) -> None:
        _player(self.player)
        _digest(self.information_state_digest, "information_state_digest")


@dataclass(frozen=True, slots=True)
class TransitionWork:
    units: int

    def __post_init__(self) -> None:
        if type(self.units) is not int or self.units <= 0:
            raise ValueError("transition work must be positive")

    def __add__(self, other: object) -> Self:
        if not isinstance(other, TransitionWork):
            return NotImplemented
        return type(self)(self.units + other.units)


@dataclass(frozen=True, slots=True)
class TransitionSuccessor[WorldT]:
    outcome_id: str = field(repr=False)
    world: PreparedWorld[WorldT] = field(repr=False)
    probability_numerator: int = 1

    def __post_init__(self) -> None:
        _internal_id(self.outcome_id)
        if (
            not isinstance(self.world, PreparedWorld)
            or type(self.probability_numerator) is not int
            or self.probability_numerator <= 0
        ):
            raise ValueError("invalid transition successor")


@dataclass(frozen=True, slots=True)
class TransitionOutcome[WorldT]:
    successors: tuple[TransitionSuccessor[WorldT], ...]
    probability_denominator: int
    work: TransitionWork
    required_capabilities: tuple[CapabilityId, ...]

    def __post_init__(self) -> None:
        if (
            type(self.successors) is not tuple
            or not self.successors
            or any(not isinstance(item, TransitionSuccessor) for item in self.successors)
        ):
            raise ValueError("invalid transition outcome")
        if type(self.probability_denominator) is not int or self.probability_denominator <= 0:
            raise ValueError("invalid transition outcome")
        identifiers = tuple(item.outcome_id for item in self.successors)
        if identifiers != tuple(sorted(identifiers)) or len(set(identifiers)) != len(identifiers):
            raise ValueError("invalid transition outcome")
        if (
            sum(item.probability_numerator for item in self.successors)
            != self.probability_denominator
        ):
            raise ValueError("invalid transition outcome")
        if not isinstance(self.work, TransitionWork):
            raise ValueError("invalid transition outcome")
        root = self.successors[0].world.root_identity
        if any(item.world.root_identity != root for item in self.successors[1:]):
            raise ValueError("invalid transition outcome")
        _capabilities(self.required_capabilities, root.capability_catalog_digest)

    def public_summary(self) -> dict[str, object]:
        return {
            "successor_count": len(self.successors),
            "probability_denominator": self.probability_denominator,
            "work_units": self.work.units,
            "required_capability_count": len(self.required_capabilities),
        }

    def require_preflight_subset(self, preflight_capabilities: tuple[CapabilityId, ...]) -> None:
        """Fail closed unless runtime requirements were statically preflighted.

        Preflight construction is intentionally outside this value object: it must
        not require a transition outcome. This method is runtime conformance only.
        """

        root_catalog_digest = self.successors[0].world.root_identity.capability_catalog_digest
        _capabilities(preflight_capabilities, root_catalog_digest)
        preflight = frozenset(preflight_capabilities)
        if not frozenset(self.required_capabilities).issubset(preflight):
            raise ValueError("transition outcome requires an unpreflighted capability")


@dataclass(frozen=True, slots=True)
class WorldDistributionIdentity:
    distribution_id: str
    version: str
    digest: str = field(repr=False)
    generation: int
    format: str
    ruleset_digest: str = field(repr=False)
    public_evidence_digest: str = field(repr=False)
    support_digest: str = field(repr=False)
    support_count: int
    availability_status: Literal["available", "unavailable"]

    def __post_init__(self) -> None:
        if type(self.distribution_id) is not str or not _INTERNAL_ID_RE.fullmatch(
            self.distribution_id
        ):
            raise ValueError("distribution_id must be canonical")
        if type(self.version) is not str or not self.version:
            raise ValueError("version must be non-empty")
        if type(self.generation) is not int or self.generation != 9 or self.format != "gen9ou":
            raise ValueError("distribution identity must be Gen 9 OU")
        if self.availability_status not in {"available", "unavailable"}:
            raise ValueError("availability_status is invalid")
        for name in ("digest", "ruleset_digest", "public_evidence_digest", "support_digest"):
            _digest(getattr(self, name), name)
        if type(self.support_count) is not int or self.support_count < 0:
            raise ValueError("support_count must be non-negative")


__all__ = [
    "InformationStateKey",
    "PlayerView",
    "PreparedRootIdentity",
    "PreparedWorld",
    "SearchAction",
    "TransitionOutcome",
    "TransitionSuccessor",
    "TransitionWork",
    "WorldDistributionIdentity",
]
