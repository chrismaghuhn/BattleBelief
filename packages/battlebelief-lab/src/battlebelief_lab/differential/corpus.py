"""Fail-closed loading for versioned differential-corpus closures.

The corpus format is deliberately data-only: every fixture is a canonical JSON
document with its own digest, and the index is a separate canonical document
that closes over the sorted fixture set.  This module performs no oracle or
engine execution.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from types import MappingProxyType
from typing import Any, Self, cast
from weakref import WeakKeyDictionary

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from rfc8785 import CanonicalizationError

from battlebelief_core.canonicalization import canonicalize, manifest_digest
from battlebelief_core.domain.engine_capabilities import CapabilityCatalog

_CORPUS_SCHEMA_FILENAME = "differential-corpus.schema.json"
_FIXTURE_SCHEMA_FILENAME = "differential-fixture.schema.json"
_CORPUS_SCHEMA_ID = "urn:battlebelief:schema:evaluation:differential-corpus:v1"
_FIXTURE_SCHEMA_ID = "urn:battlebelief:schema:evaluation:differential-fixture:v1"
_LOCAL_ABSOLUTE_PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|(?<![A-Za-z0-9])/(?:[^\\s/]+))")
_HOSTNAME_RE = re.compile(
    r"(?i)\b(?:localhost|(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}|"
    r"(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})(?:\.(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})){3})\b"
)
_URI_RE = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://")
_HOST_ASSIGNMENT_RE = re.compile(r"(?i)\b(?:host|hostname)\s*=\s*[a-z0-9][a-z0-9-]*")
_CORPUS_FIXTURE_RELATIVE_PATH_RE = re.compile(r"^fixtures/[a-z][a-z0-9]*(?:-[a-z0-9]+)*\.json$")
_SchemaResource = Path | Traversable
_FIXED_SCHEMA_PATH_SEGMENTS = frozenset(
    {
        "schema_version",
        "corpus_id",
        "corpus_version",
        "fixture_id",
        "fixture_digest",
        "generation",
        "format",
        "ruleset",
        "seed",
        "initial_authoritative_full_state",
        "player_views",
        "joint_action_intent",
        "chance_inputs",
        "capability_ids",
        "observation_checkpoints",
        "declared_comparison_fields",
        "normalization",
        "classification_policy",
        "provenance",
    }
)
_INDEX_MEMBER_NAMES = frozenset(
    {
        "schema_version",
        "corpus_id",
        "corpus_version",
        "corpus_digest",
        "schema_bindings",
        "canonicalization",
        "catalog",
        "ruleset",
        "normalization",
        "classifier",
        "fixtures",
        "coverage",
    }
)
_FIXTURE_MEMBER_NAMES = frozenset(_FIXED_SCHEMA_PATH_SEGMENTS)
_TRUSTED_MEMBER_NAMES_BY_LOCATION = {
    "fixture": _FIXTURE_MEMBER_NAMES,
    "fixture.ruleset": frozenset({"ruleset_id", "ruleset_digest", "snapshot"}),
    "fixture.ruleset.snapshot": frozenset({"format_id", "ruleset_id", "ruleset_version"}),
    "fixture.seed": frozenset({"seed_id", "seed_value"}),
    "fixture.player_views[]": frozenset({"player_id", "view"}),
    "fixture.joint_action_intent[]": frozenset({"actor", "action"}),
    "fixture.observation_checkpoints[]": frozenset({"checkpoint_id", "comparison_fields"}),
    "fixture.normalization": frozenset({"profile_id", "profile_version", "profile_digest"}),
    "fixture.classification_policy": frozenset(
        {
            "classifier_id",
            "classifier_version",
            "classifier_source_digest",
            "known_divergence_id",
        }
    ),
    "fixture.provenance": frozenset({"source_type", "source_id", "license_id", "reviewed"}),
    "corpus index": _INDEX_MEMBER_NAMES,
    "corpus index.schema_bindings[]": frozenset({"schema_id", "schema_version", "schema_digest"}),
    "corpus index.canonicalization": frozenset(
        {"canonicalization_id", "canonicalization_version", "canonicalization_digest"}
    ),
    "corpus index.catalog": frozenset({"catalog_id", "catalog_version", "catalog_digest"}),
    "corpus index.ruleset": frozenset({"ruleset_id", "ruleset_digest", "snapshot"}),
    "corpus index.ruleset.snapshot": frozenset({"format_id", "ruleset_id", "ruleset_version"}),
    "corpus index.normalization": frozenset({"profile_id", "profile_version", "profile_digest"}),
    "corpus index.classifier": frozenset(
        {
            "classifier_id",
            "classifier_version",
            "classifier_source_digest",
            "known_divergence_definitions",
        }
    ),
    "corpus index.classifier.known_divergence_definitions[]": frozenset(
        {"known_divergence_id", "affected_capability_ids"}
    ),
    "corpus index.fixtures[]": frozenset({"fixture_id", "path", "fixture_digest"}),
    "corpus index.coverage[]": frozenset(
        {"capability_id", "coverage_kind", "fixture_ids", "known_divergence_id"}
    ),
}


class CorpusValidationError(ValueError):
    """Raised when a corpus document or its closure is not fail-closed valid."""


def _reject_nonfinite(value: str) -> None:
    raise CorpusValidationError(f"JSON constant {value!r} is not permitted")


def _reject_duplicate_object_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for name, value in pairs:
        if name in document:
            raise CorpusValidationError("duplicate JSON member is not permitted")
        document[name] = value
    return document


def _parse_json_object(text: str, filename: str) -> dict[str, Any]:
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_object_members,
            parse_constant=_reject_nonfinite,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        if isinstance(error, CorpusValidationError):
            raise
        raise CorpusValidationError(f"cannot load JSON document {filename}") from error
    if not isinstance(value, dict):
        raise CorpusValidationError(f"JSON document {filename} must be an object")
    return value


def _load_json(path: _SchemaResource) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise CorpusValidationError(f"cannot load JSON document {path.name}") from error
    return _parse_json_object(text, path.name)


def _load_canonical_json(path: Path) -> dict[str, Any]:
    """Load a corpus member only when its raw bytes are exactly RFC8785/JCS."""

    try:
        raw_bytes = path.read_bytes()
        # Decode a BOM only so that it can be reported as a canonical-byte
        # mismatch below rather than accepted or silently retained.
        text = raw_bytes.decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        raise CorpusValidationError(f"cannot load canonical JSON document {path.name}") from error
    document = _parse_json_object(text, path.name)
    try:
        canonical_bytes = canonicalize(document)
    except (CanonicalizationError, OverflowError, RecursionError) as error:
        raise CorpusValidationError("canonical JSON value is invalid") from error
    if raw_bytes != canonical_bytes:
        raise CorpusValidationError(f"canonical JSON bytes differ for {path.name}")
    return document


def _source_schema_directory() -> Path:
    return Path(__file__).resolve().parents[5] / "schemas" / "evaluation"


def _schema_resource(filename: str, schema_directory: Path | None) -> _SchemaResource:
    """Find source schemas first, then the exact bytes bundled in a wheel."""

    source_path = (schema_directory or _source_schema_directory()) / filename
    if source_path.is_file():
        return source_path
    resource = resources.files("battlebelief_lab.differential").joinpath("schemas", filename)
    if not resource.is_file():
        raise CorpusValidationError(f"schema resource {filename} is missing")
    return resource


def _schema_error_summary(error: Any) -> str:
    """Render only schema-controlled diagnostic metadata, never instance data."""

    validator = error.validator if isinstance(error.validator, str) else "unknown"
    path = "$"
    for position, segment in enumerate(error.absolute_path):
        if isinstance(segment, int):
            path += f"[{segment}]"
        elif position == 0 and segment in _FIXED_SCHEMA_PATH_SEGMENTS:
            path += f".{segment}"
        else:
            path += ".*"
    return f"schema violation ({validator}) at {path}"


def _schema_errors(document: Mapping[str, object], schema_path: _SchemaResource) -> list[str]:
    schema = _load_json(schema_path)
    validator = Draft202012Validator(schema)
    return sorted(_schema_error_summary(error) for error in validator.iter_errors(document))


def _validate_schema(document: Mapping[str, object], schema_path: _SchemaResource) -> None:
    errors = _schema_errors(document, schema_path)
    if errors:
        raise CorpusValidationError(f"schema validation failed: {errors[0]}")


def _required_mapping(document: Mapping[str, object], name: str) -> Mapping[str, object]:
    value = document[name]
    if not isinstance(value, Mapping):
        raise CorpusValidationError(f"{name} must be an object")
    return value


def _required_sequence(document: Mapping[str, object], name: str) -> Sequence[object]:
    value = document[name]
    if not isinstance(value, list):
        raise CorpusValidationError(f"{name} must be an array")
    return value


def _require_sorted_unique(values: Sequence[object], name: str) -> tuple[str, ...]:
    if any(type(value) is not str for value in values):
        raise CorpusValidationError(f"{name} must contain strings")
    normalized = tuple(cast(str, value) for value in values)
    if normalized != tuple(sorted(normalized)):
        raise CorpusValidationError(f"{name} must be sorted")
    if len(set(normalized)) != len(normalized):
        raise CorpusValidationError(f"{name} must be unique")
    return normalized


def _without(document: Mapping[str, object], field_name: str) -> dict[str, object]:
    return {name: value for name, value in document.items() if name != field_name}


def _canonical_json_copy(document: Mapping[str, object]) -> dict[str, object]:
    copied = json.loads(canonicalize(document))
    if not isinstance(copied, dict):  # pragma: no cover - canonical JSON object input
        raise CorpusValidationError("canonical JSON copy must be an object")
    return cast(dict[str, object], copied)


def _raw_file_digest(path: _SchemaResource) -> str:
    try:
        return "sha256:" + sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise CorpusValidationError(f"schema file {path.name} is unreadable") from error


def _is_reparse_point(path: Path) -> bool:
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError as error:
        raise CorpusValidationError("fixture directory entry is unreadable") from error
    return bool(attributes & 0x400)


def _is_structural_nonhost_string(value: str, location: str) -> bool:
    """Recognize the two data-grammar strings that intentionally contain dots.

    Capability identifiers and the canonical relative fixture path are still
    validated by their own schema and closure rules. They are not hostnames.
    """

    return (
        value.startswith("gen9.")
        and (
            location.endswith(".capability_id")
            or ".capability_ids[" in location
            or ".affected_capability_ids[" in location
        )
    ) or (
        location.startswith("corpus index.fixtures[")
        and location.endswith(".path")
        and _CORPUS_FIXTURE_RELATIVE_PATH_RE.fullmatch(value) is not None
    )


def _trusted_child_location(location: str, name: str) -> str:
    """Keep only schema-owned member names in public diagnostic paths."""

    normalized_location = re.sub(r"\[\d+\]", "[]", location)
    if name in _TRUSTED_MEMBER_NAMES_BY_LOCATION.get(normalized_location, frozenset()):
        return f"{location}.{name}"
    return f"{location}.*"


def _validate_safe_fixture_value(value: object, location: str) -> None:
    """Reject host and local-path data from the intentionally generic fixture payloads.

    The recursive JSON schema accepts only JSON scalars, arrays, and objects in
    these payloads.  This matching semantic pass applies the same deliberately
    bounded forbidden-string policy to every value and object member name.
    """

    if type(value) is str:
        if unicodedata.normalize("NFC", value) != value:
            raise CorpusValidationError(f"{location} is not NFC normalized")
        if _LOCAL_ABSOLUTE_PATH_RE.search(value):
            raise CorpusValidationError(f"{location} contains an absolute local path")
        if not _is_structural_nonhost_string(value, location) and (
            _HOSTNAME_RE.search(value) or _URI_RE.search(value) or _HOST_ASSIGNMENT_RE.search(value)
        ):
            raise CorpusValidationError(f"{location} contains a hostname")
        return
    if value is None or type(value) is bool or type(value) is int:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise CorpusValidationError(f"{location} contains a non-finite number")
        return
    if isinstance(value, list):
        for index, nested_value in enumerate(value):
            _validate_safe_fixture_value(nested_value, f"{location}[{index}]")
        return
    if isinstance(value, Mapping):
        for name, nested_value in value.items():
            if type(name) is not str:
                raise CorpusValidationError(f"{location} has a non-string member name")
            _validate_safe_fixture_value(name, f"{location} member name")
            _validate_safe_fixture_value(nested_value, _trusted_child_location(location, name))
        return
    raise CorpusValidationError(f"{location} is not a canonical JSON value")


def _string(document: Mapping[str, object], name: str) -> str:
    value = document[name]
    if type(value) is not str:
        raise CorpusValidationError(f"{name} must be a string")
    return value


def _optional_string(document: Mapping[str, object], name: str) -> str | None:
    value = document[name]
    if value is None:
        return None
    if type(value) is not str:
        raise CorpusValidationError(f"{name} must be null or a string")
    return value


def _integer(document: Mapping[str, object], name: str) -> int:
    value = document[name]
    if type(value) is not int:
        raise CorpusValidationError(f"{name} must be an integer")
    return value


def _validate_ruleset_binding(ruleset: Mapping[str, object], location: str) -> None:
    """Require the explicit ruleset snapshot to bind its declared digest."""

    snapshot = _required_mapping(ruleset, "snapshot")
    if _string(snapshot, "ruleset_id") != _string(ruleset, "ruleset_id"):
        raise CorpusValidationError(f"{location} snapshot ID does not match its ruleset ID")
    try:
        expected_digest = manifest_digest(snapshot)
    except (CanonicalizationError, OverflowError, RecursionError) as error:
        raise CorpusValidationError(f"{location} snapshot is not canonical") from error
    if _string(ruleset, "ruleset_digest") != expected_digest:
        raise CorpusValidationError(f"{location} snapshot digest does not bind its snapshot")


def _validate_transition_state(document: Mapping[str, object]) -> None:
    """Check relationships that JSON Schema cannot express for the closed v1 state."""

    state = _required_mapping(document, "initial_authoritative_full_state")
    players = _required_mapping(state, "players")
    for player_id in ("p1", "p2"):
        player = _required_mapping(players, player_id)
        active_slot = _string(player, "active_slot")
        if not active_slot.startswith(player_id):
            raise CorpusValidationError("active slot does not belong to its player")
        team = _required_sequence(player, "team")
        team_slots: set[str] = set()
        active_count = 0
        for combatant_value in team:
            if not isinstance(combatant_value, Mapping):
                raise CorpusValidationError("team combatant must be an object")
            slot_id = _string(combatant_value, "slot_id")
            if not slot_id.startswith(player_id):
                raise CorpusValidationError("team combatant slot does not belong to its player")
            if slot_id in team_slots:
                raise CorpusValidationError("team combatant slots must be unique")
            team_slots.add(slot_id)
            if slot_id == active_slot:
                active_count += 1
            hp = _required_mapping(combatant_value, "hp")
            if _integer(hp, "current") > _integer(hp, "maximum"):
                raise CorpusValidationError("combatant current HP exceeds maximum HP")
            moves = _required_sequence(combatant_value, "moves")
            move_ids: set[str] = set()
            for move_value in moves:
                if not isinstance(move_value, Mapping):
                    raise CorpusValidationError("combatant move must be an object")
                move_id = _string(move_value, "move_id")
                if move_id in move_ids:
                    raise CorpusValidationError("combatant move IDs must be unique")
                move_ids.add(move_id)
                pp = _required_mapping(move_value, "pp")
                if _integer(pp, "current") > _integer(pp, "maximum"):
                    raise CorpusValidationError("move current PP exceeds maximum PP")
        if active_count != 1:
            raise CorpusValidationError("player active slot must resolve to exactly one combatant")
    terminal = _required_mapping(state, "terminal")
    terminal_value = terminal["value"]
    expected_terminal_values: Mapping[str, int | None] = {
        "ongoing": None,
        "p1-win": 1,
        "p2-win": -1,
        "tie": 0,
    }
    if terminal_value != expected_terminal_values[_string(terminal, "state")]:
        raise CorpusValidationError("terminal value does not match terminal state")


@dataclass(frozen=True, slots=True, weakref_slot=True)
class DifferentialFixture:
    """One independently content-addressed differential fixture."""

    corpus_id: str
    corpus_version: str
    fixture_id: str
    fixture_digest: str
    ruleset_id: str
    ruleset_digest: str
    seed_id: str
    capability_ids: tuple[str, ...]
    declared_comparison_fields: tuple[str, ...]
    classifier_id: str
    classifier_version: str
    classifier_source_digest: str
    normalization_profile_id: str
    normalization_profile_version: str
    normalization_profile_digest: str
    known_divergence_id: str | None

    @staticmethod
    def derive_digest(document: Mapping[str, object]) -> str:
        """Digest the fixture's complete canonical payload except its self-field."""

        return manifest_digest(_without(document, "fixture_digest"))

    @classmethod
    def from_document(
        cls,
        document: Mapping[str, object],
        *,
        schema_directory: Path | None = None,
        _corpus_digest_for_runner: str | None = None,
    ) -> Self:
        """Validate and materialize a fixture without accepting implicit defaults."""

        _validate_safe_fixture_value(document, "fixture")
        _validate_schema(document, _schema_resource(_FIXTURE_SCHEMA_FILENAME, schema_directory))
        expected_digest = cls.derive_digest(document)
        if document["fixture_digest"] != expected_digest:
            raise CorpusValidationError("fixture digest does not bind the fixture payload")
        capability_ids = _require_sorted_unique(
            _required_sequence(document, "capability_ids"), "capability_ids"
        )
        comparison_fields = _require_sorted_unique(
            _required_sequence(document, "declared_comparison_fields"),
            "declared_comparison_fields",
        )
        checkpoints = _required_sequence(document, "observation_checkpoints")
        if len(checkpoints) != 1:
            raise CorpusValidationError("fixture must contain exactly one observation checkpoint")
        checkpoint_ids: list[str] = []
        for checkpoint_value in checkpoints:
            if not isinstance(checkpoint_value, Mapping):
                raise CorpusValidationError("observation checkpoint must be an object")
            checkpoint_id = checkpoint_value["checkpoint_id"]
            if type(checkpoint_id) is not str:
                raise CorpusValidationError("checkpoint ID must be a string")
            checkpoint_ids.append(checkpoint_id)
            checkpoint_fields = _require_sorted_unique(
                _required_sequence(checkpoint_value, "comparison_fields"),
                "checkpoint comparison fields",
            )
            if checkpoint_fields != comparison_fields:
                raise CorpusValidationError(
                    "checkpoint comparison fields must exactly match declared comparison fields"
                )
        _require_sorted_unique(checkpoint_ids, "observation checkpoint IDs")
        ruleset = _required_mapping(document, "ruleset")
        _validate_ruleset_binding(ruleset, "fixture ruleset")
        _validate_transition_state(document)
        seed = _required_mapping(document, "seed")
        normalization = _required_mapping(document, "normalization")
        policy = _required_mapping(document, "classification_policy")
        player_views = _required_sequence(document, "player_views")
        player_ids = tuple(
            _string(player_view, "player_id")
            for player_view in player_views
            if isinstance(player_view, Mapping)
        )
        if len(player_ids) != len(player_views) or player_ids != ("p1", "p2"):
            raise CorpusValidationError("player views must be ordered p1, p2 exactly once")
        joint_action_intent = _required_sequence(document, "joint_action_intent")
        actor_ids = tuple(
            _string(intent, "actor")
            for intent in joint_action_intent
            if isinstance(intent, Mapping)
        )
        if len(actor_ids) != len(joint_action_intent) or actor_ids != ("p1", "p2"):
            raise CorpusValidationError("joint action intent must contain p1 and p2 exactly once")
        fixture = cls(
            corpus_id=_string(document, "corpus_id"),
            corpus_version=_string(document, "corpus_version"),
            fixture_id=_string(document, "fixture_id"),
            fixture_digest=_string(document, "fixture_digest"),
            ruleset_id=_string(ruleset, "ruleset_id"),
            ruleset_digest=_string(ruleset, "ruleset_digest"),
            seed_id=_string(seed, "seed_id"),
            capability_ids=capability_ids,
            declared_comparison_fields=comparison_fields,
            classifier_id=_string(policy, "classifier_id"),
            classifier_version=_string(policy, "classifier_version"),
            classifier_source_digest=_string(policy, "classifier_source_digest"),
            normalization_profile_id=_string(normalization, "profile_id"),
            normalization_profile_version=_string(normalization, "profile_version"),
            normalization_profile_digest=_string(normalization, "profile_digest"),
            known_divergence_id=_optional_string(policy, "known_divergence_id"),
        )
        _FIXTURE_EXECUTION_DOCUMENTS[fixture] = _canonical_json_copy(document)
        if _corpus_digest_for_runner is not None and (
            type(_corpus_digest_for_runner) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", _corpus_digest_for_runner) is None
        ):
            raise CorpusValidationError("runner corpus digest is invalid")
        _FIXTURE_CORPUS_DIGESTS[fixture] = _corpus_digest_for_runner
        return fixture

    def _execution_document_for_runner(self) -> dict[str, object]:
        """Return a detached full-state input for package-internal runner code only."""

        try:
            document = _FIXTURE_EXECUTION_DOCUMENTS[self]
        except KeyError as error:  # pragma: no cover - instances are always registered above
            raise CorpusValidationError("fixture execution document is unavailable") from error
        return _canonical_json_copy(document)

    def _corpus_digest_for_runner(self) -> str | None:
        """Return only the enclosing corpus digest for package-internal provenance binding."""

        return _FIXTURE_CORPUS_DIGESTS.get(self)


_FIXTURE_EXECUTION_DOCUMENTS: WeakKeyDictionary[object, dict[str, object]] = WeakKeyDictionary()
_FIXTURE_CORPUS_DIGESTS: WeakKeyDictionary[object, str | None] = WeakKeyDictionary()


@dataclass(frozen=True, slots=True)
class DifferentialCorpus:
    """A digest-bound, complete, sorted set of differential fixtures."""

    corpus_id: str
    corpus_version: str
    corpus_digest: str
    catalog_id: str
    catalog_version: str
    catalog_digest: str
    ruleset_id: str
    ruleset_digest: str
    classifier_id: str
    classifier_version: str
    classifier_source_digest: str
    known_divergence_definitions: Mapping[str, tuple[str, ...]]
    normalization_profile_id: str
    normalization_profile_version: str
    normalization_profile_digest: str
    fixtures: tuple[DifferentialFixture, ...]
    capability_coverage: Mapping[str, tuple[str, ...]]

    @staticmethod
    def derive_digest(document: Mapping[str, object]) -> str:
        """Digest the canonical index payload except its self-field."""

        return manifest_digest(_without(document, "corpus_digest"))

    @classmethod
    def load(
        cls,
        directory: Path,
        catalog: CapabilityCatalog,
        *,
        schema_directory: Path | None = None,
    ) -> Self:
        """Load a corpus directory and reject every incomplete or loose closure."""

        if not isinstance(catalog, CapabilityCatalog):
            raise TypeError("catalog must be a CapabilityCatalog")
        if not directory.is_dir():
            raise CorpusValidationError("corpus directory is missing")
        index_path = directory / "index.json"
        if not index_path.is_file():
            raise CorpusValidationError("corpus index is missing")
        if index_path.is_symlink() or _is_reparse_point(index_path):
            raise CorpusValidationError("corpus index is not a regular file")
        index = _load_canonical_json(index_path)
        _validate_safe_fixture_value(index, "corpus index")
        _validate_schema(index, _schema_resource(_CORPUS_SCHEMA_FILENAME, schema_directory))
        if index["corpus_digest"] != cls.derive_digest(index):
            raise CorpusValidationError("corpus digest does not bind the index payload")
        known_divergence_definitions = cls._validate_index_bindings(
            index, catalog, schema_directory
        )

        fixture_entries = _required_sequence(index, "fixtures")
        fixture_ids = []
        fixture_paths = []
        for entry_value in fixture_entries:
            if not isinstance(entry_value, Mapping):
                raise CorpusValidationError("fixture entry must be an object")
            fixture_id = entry_value["fixture_id"]
            fixture_path = entry_value["path"]
            if type(fixture_id) is not str or type(fixture_path) is not str:
                raise CorpusValidationError("fixture entry fields must be strings")
            fixture_ids.append(fixture_id)
            fixture_paths.append(fixture_path)
        if len(set(fixture_ids)) != len(fixture_ids):
            raise CorpusValidationError("duplicate fixture ID in corpus index")
        if len(set(fixture_paths)) != len(fixture_paths):
            raise CorpusValidationError("duplicate fixture path in corpus index")
        _require_sorted_unique(fixture_ids, "fixtures")
        for fixture_id, fixture_path in zip(fixture_ids, fixture_paths, strict=True):
            if fixture_path != f"fixtures/{fixture_id}.json":
                raise CorpusValidationError("fixture entry path must bind its fixture ID")

        fixture_root = directory / "fixtures"
        if (
            not fixture_root.is_dir()
            or fixture_root.is_symlink()
            or _is_reparse_point(fixture_root)
        ):
            raise CorpusValidationError("fixtures directory is missing")
        entries = tuple(fixture_root.iterdir())
        if any(
            not entry.is_file() or entry.is_symlink() or _is_reparse_point(entry)
            for entry in entries
        ):
            raise CorpusValidationError("fixtures directory contains a non-regular fixture entry")
        actual_paths = {path.relative_to(directory).as_posix() for path in entries}
        expected_paths = set(fixture_paths)
        missing_paths = sorted(expected_paths - actual_paths)
        if missing_paths:
            raise CorpusValidationError("referenced fixture is missing")
        extra_paths = sorted(actual_paths - expected_paths)
        if extra_paths:
            raise CorpusValidationError("unreferenced fixture file is present")
        fixtures: list[DifferentialFixture] = []
        for entry_value in fixture_entries:
            assert isinstance(entry_value, Mapping)
            fixture_path = directory / entry_value["path"]
            fixture = DifferentialFixture.from_document(
                _load_canonical_json(fixture_path),
                schema_directory=schema_directory,
                _corpus_digest_for_runner=_string(index, "corpus_digest"),
            )
            if fixture.fixture_id != entry_value["fixture_id"]:
                raise CorpusValidationError("fixture ID does not match its index entry")
            if fixture.fixture_digest != entry_value["fixture_digest"]:
                raise CorpusValidationError("fixture digest does not match its index entry")
            cls._validate_fixture_bindings(
                fixture,
                index,
                catalog,
                known_divergence_definitions,
            )
            fixtures.append(fixture)
        coverage = cls._validate_coverage(index, catalog, fixtures, known_divergence_definitions)
        return cls(
            corpus_id=_string(index, "corpus_id"),
            corpus_version=_string(index, "corpus_version"),
            corpus_digest=_string(index, "corpus_digest"),
            catalog_id=catalog.catalog_id,
            catalog_version=catalog.catalog_version,
            catalog_digest=catalog.catalog_digest,
            ruleset_id=_string(_required_mapping(index, "ruleset"), "ruleset_id"),
            ruleset_digest=_string(_required_mapping(index, "ruleset"), "ruleset_digest"),
            classifier_id=_string(_required_mapping(index, "classifier"), "classifier_id"),
            classifier_version=_string(
                _required_mapping(index, "classifier"), "classifier_version"
            ),
            classifier_source_digest=_string(
                _required_mapping(index, "classifier"), "classifier_source_digest"
            ),
            known_divergence_definitions=MappingProxyType(known_divergence_definitions),
            normalization_profile_id=_string(
                _required_mapping(index, "normalization"), "profile_id"
            ),
            normalization_profile_version=_string(
                _required_mapping(index, "normalization"), "profile_version"
            ),
            normalization_profile_digest=_string(
                _required_mapping(index, "normalization"), "profile_digest"
            ),
            fixtures=tuple(fixtures),
            capability_coverage=MappingProxyType(coverage),
        )

    @staticmethod
    def _validate_index_bindings(
        index: Mapping[str, object], catalog: CapabilityCatalog, schema_directory: Path | None
    ) -> dict[str, tuple[str, ...]]:
        _validate_ruleset_binding(_required_mapping(index, "ruleset"), "corpus index ruleset")
        catalog_binding = _required_mapping(index, "catalog")
        if (
            catalog_binding["catalog_id"] != catalog.catalog_id
            or catalog_binding["catalog_version"] != catalog.catalog_version
        ):
            raise CorpusValidationError("catalog identity does not match the capability catalog")
        if catalog_binding["catalog_digest"] != catalog.catalog_digest:
            raise CorpusValidationError("catalog digest does not match the capability catalog")
        canonicalization = _required_mapping(index, "canonicalization")
        if (
            canonicalization["canonicalization_id"] != catalog.canonicalization_contract_id
            or canonicalization["canonicalization_version"]
            != catalog.canonicalization_contract_version
            or canonicalization["canonicalization_digest"]
            != catalog.canonicalization_contract_digest
        ):
            raise CorpusValidationError(
                "canonicalization identity does not match the capability catalog"
            )
        bindings = _required_sequence(index, "schema_bindings")
        schema_ids: list[str] = []
        for binding in bindings:
            if not isinstance(binding, Mapping) or type(binding["schema_id"]) is not str:
                raise CorpusValidationError("schema binding must contain a schema ID")
            schema_ids.append(binding["schema_id"])
        if tuple(schema_ids) != tuple(sorted(schema_ids)):
            raise CorpusValidationError("schema bindings must be sorted")
        if set(schema_ids) != {_CORPUS_SCHEMA_ID, _FIXTURE_SCHEMA_ID}:
            raise CorpusValidationError(
                "schema bindings must bind the v1 corpus and fixture schemas"
            )
        expected_schema_files = {
            _CORPUS_SCHEMA_ID: _schema_resource(_CORPUS_SCHEMA_FILENAME, schema_directory),
            _FIXTURE_SCHEMA_ID: _schema_resource(_FIXTURE_SCHEMA_FILENAME, schema_directory),
        }
        for binding in bindings:
            assert isinstance(binding, Mapping)
            schema_id = _string(binding, "schema_id")
            if binding["schema_version"] != 1:
                raise CorpusValidationError("schema binding has an unsupported schema version")
            if _string(binding, "schema_digest") != _raw_file_digest(
                expected_schema_files[schema_id]
            ):
                raise CorpusValidationError("schema binding digest does not match raw schema bytes")
        classifier = _required_mapping(index, "classifier")
        definitions = _required_sequence(classifier, "known_divergence_definitions")
        definition_ids: list[str] = []
        parsed_definitions: dict[str, tuple[str, ...]] = {}
        for definition_value in definitions:
            if not isinstance(definition_value, Mapping):
                raise CorpusValidationError("known divergence definition must be an object")
            known_divergence_id = _string(definition_value, "known_divergence_id")
            capability_ids = _require_sorted_unique(
                _required_sequence(definition_value, "affected_capability_ids"),
                "known divergence definition capability IDs",
            )
            if not capability_ids:
                raise CorpusValidationError(
                    "known divergence definition capability IDs may not be empty"
                )
            for capability_id in capability_ids:
                try:
                    catalog.id_for(capability_id)
                except ValueError as error:
                    raise CorpusValidationError(
                        "known divergence definition capability is not defined by the capability catalog"
                    ) from error
            definition_ids.append(known_divergence_id)
            parsed_definitions[known_divergence_id] = capability_ids
        _require_sorted_unique(definition_ids, "known divergence definitions")
        return parsed_definitions

    @staticmethod
    def _validate_fixture_bindings(
        fixture: DifferentialFixture,
        index: Mapping[str, object],
        catalog: CapabilityCatalog,
        known_divergence_definitions: Mapping[str, tuple[str, ...]],
    ) -> None:
        if fixture.corpus_id != index["corpus_id"]:
            raise CorpusValidationError("fixture corpus ID does not match the index")
        if fixture.corpus_version != index["corpus_version"]:
            raise CorpusValidationError("fixture corpus version does not match the index")
        ruleset = _required_mapping(index, "ruleset")
        if (
            fixture.ruleset_id != ruleset["ruleset_id"]
            or fixture.ruleset_digest != ruleset["ruleset_digest"]
        ):
            raise CorpusValidationError("fixture ruleset does not match the index")
        classifier = _required_mapping(index, "classifier")
        if (
            fixture.classifier_id != classifier["classifier_id"]
            or fixture.classifier_version != classifier["classifier_version"]
            or fixture.classifier_source_digest != classifier["classifier_source_digest"]
        ):
            raise CorpusValidationError("fixture classification policy does not match the index")
        normalization = _required_mapping(index, "normalization")
        if (
            fixture.normalization_profile_id != normalization["profile_id"]
            or fixture.normalization_profile_version != normalization["profile_version"]
            or fixture.normalization_profile_digest != normalization["profile_digest"]
        ):
            raise CorpusValidationError("fixture normalization profile does not match the index")
        for capability_id in fixture.capability_ids:
            try:
                catalog.id_for(capability_id)
            except ValueError as error:
                raise CorpusValidationError(
                    "fixture capability is not defined by the capability catalog"
                ) from error
        if fixture.known_divergence_id is not None:
            affected_capability_ids = known_divergence_definitions.get(fixture.known_divergence_id)
            if affected_capability_ids is None:
                raise CorpusValidationError(
                    "fixture known divergence is not defined by the index classifier"
                )
            if not set(fixture.capability_ids).issubset(affected_capability_ids):
                raise CorpusValidationError(
                    "known divergence definition does not cover fixture capability"
                )

    @staticmethod
    def _validate_coverage(
        index: Mapping[str, object],
        catalog: CapabilityCatalog,
        fixtures: Sequence[DifferentialFixture],
        known_divergence_definitions: Mapping[str, tuple[str, ...]],
    ) -> dict[str, tuple[str, ...]]:
        coverage_entries = _required_sequence(index, "coverage")
        capability_ids: list[str] = []
        coverage: dict[str, tuple[str, ...]] = {}
        fixtures_by_id = {fixture.fixture_id: fixture for fixture in fixtures}
        for entry_value in coverage_entries:
            if not isinstance(entry_value, Mapping):
                raise CorpusValidationError("coverage entry must be an object")
            capability_id = entry_value["capability_id"]
            if type(capability_id) is not str:
                raise CorpusValidationError("coverage capability ID must be a string")
            capability_ids.append(capability_id)
            fixture_ids = _require_sorted_unique(
                _required_sequence(entry_value, "fixture_ids"), "coverage fixture IDs"
            )
            if not fixture_ids:
                raise CorpusValidationError("coverage fixture IDs may not be empty")
            try:
                catalog.id_for(capability_id)
            except ValueError as error:
                raise CorpusValidationError(
                    "coverage capability is not defined by the capability catalog"
                ) from error
            for fixture_id in fixture_ids:
                fixture = fixtures_by_id.get(fixture_id)
                if fixture is None:
                    raise CorpusValidationError("coverage references an unknown fixture ID")
                if capability_id not in fixture.capability_ids:
                    raise CorpusValidationError("coverage fixture does not exercise its capability")
            coverage_kind = entry_value["coverage_kind"]
            known_divergence_id = entry_value["known_divergence_id"]
            if coverage_kind == "reviewed_fixture" and known_divergence_id is not None:
                raise CorpusValidationError(
                    "reviewed fixture coverage may not bind a known divergence"
                )
            if coverage_kind == "reviewed_fixture" and any(
                fixtures_by_id[fixture_id].known_divergence_id is not None
                for fixture_id in fixture_ids
            ):
                raise CorpusValidationError(
                    "reviewed fixture coverage may not reference a known divergence fixture"
                )
            if coverage_kind == "known_boundary":
                if known_divergence_id is None:
                    raise CorpusValidationError(
                        "known boundary coverage requires a known divergence ID"
                    )
                if any(
                    fixture.known_divergence_id != known_divergence_id
                    for fixture_id in fixture_ids
                    for fixture in (fixtures_by_id[fixture_id],)
                ):
                    raise CorpusValidationError(
                        "known boundary coverage must bind the fixture classification policy"
                    )
                affected_capability_ids = known_divergence_definitions.get(known_divergence_id)
                if affected_capability_ids is None:
                    raise CorpusValidationError(
                        "known boundary coverage requires a bound known divergence definition"
                    )
                if capability_id not in affected_capability_ids:
                    raise CorpusValidationError(
                        "known boundary definition does not affect its coverage capability"
                    )
            coverage[capability_id] = fixture_ids
        expected_capability_ids = tuple(definition.value for definition in catalog.definitions)
        if tuple(capability_ids) != expected_capability_ids:
            raise CorpusValidationError(
                "coverage must be sorted and complete for the capability catalog"
            )
        return coverage
