"""Evaluation-only, deterministic session orchestration for Showdown stdio."""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Protocol, cast

from battlebelief_core.canonicalization import canonicalize, manifest_digest
from battlebelief_lab.oracle.showdown.errors import OracleFailureClass
from battlebelief_lab.oracle.showdown.installation import BuildOracleError, verify_build_manifest
from battlebelief_lab.oracle.showdown.manifests import ShowdownBuildManifest, ShowdownSourceManifest
from battlebelief_lab.oracle.showdown.network import NetworkGuardError, guarded_node_environment
from battlebelief_lab.oracle.showdown.process import (
    OracleProcessError,
    OracleProcessResult,
    ProcessInteractionStep,
    ProcessResponseBarrier,
    ShowdownProcessLimits,
    ShowdownProcessRunner,
    ShowdownProcessSpec,
)
from battlebelief_lab.oracle.showdown.protocol import (
    EndMessage,
    PlayerSide,
    ProtocolMessage,
    SideErrorMessage,
    SideUpdateMessage,
    UpdateMessage,
    encode_commands,
)

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_FIXTURE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_MAX_SAFE_INTEGER = 9_007_199_254_740_991
_EXPECTED_FIXTURE_FIELDS = frozenset(
    {
        "schema_version",
        "fixture_id",
        "format_id",
        "ruleset_snapshot_digest",
        "seed_domain",
        "seed",
        "players",
        "expected_tera_line",
    }
)
_EXPECTED_PLAYER_FIELDS = frozenset({"name", "team", "team_choice", "move_choice"})
_SOURCE_TO_BUILD_ERROR = "build manifest does not bind the configured source manifest"
_APPROVED_TERA_LINE = "|-terastallize|p1a: Garchomp|Ground"


class _ProcessRunner(Protocol):
    async def run(
        self, spec: ShowdownProcessSpec, limits: ShowdownProcessLimits
    ) -> OracleProcessResult: ...


def _require_digest(value: object, field_name: str) -> str:
    if type(value) is not str or _DIGEST_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase sha256 digest")
    return value


def _require_string(value: object, field_name: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    if "\r" in value or "\n" in value or "\x00" in value:
        raise ValueError(f"{field_name} must not contain a control line separator")
    return value


def _require_exact_keys(value: Mapping[str, object], expected: frozenset[str], name: str) -> None:
    if frozenset(value) != expected:
        missing = sorted(expected - frozenset(value))
        unknown = sorted(frozenset(value) - expected)
        raise ValueError(f"{name} fields differ: missing={missing}, unknown={unknown}")


def _canonical_json_object(raw: bytes) -> object:
    """Decode only an already-canonical JSON value emitted by the protocol layer."""

    value = json.loads(raw.decode("utf-8"))
    if canonicalize(value) != raw:
        raise ValueError("protocol message JSON was not canonical")
    return value


def _canonical_evidence_document(
    raw: bytes, field_name: str, expected_type: type[object]
) -> object:
    if type(raw) is not bytes:
        raise TypeError(f"{field_name} must be immutable canonical bytes")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{field_name} must contain valid UTF-8 JSON") from exc
    if type(value) is not expected_type or canonicalize(value) != raw:
        raise ValueError(f"{field_name} must be a canonical JCS {expected_type.__name__}")
    return value


@dataclass(frozen=True, slots=True)
class OracleRequestIdentity:
    """Lab-only identity for one emitted player request, never an ``rqid``."""

    fixture_id: str
    sequence: int
    side: PlayerSide
    request_digest: str

    def __post_init__(self) -> None:
        if _FIXTURE_ID_RE.fullmatch(self.fixture_id) is None:
            raise ValueError("fixture_id is invalid")
        if type(self.sequence) is not int or not 0 <= self.sequence <= _MAX_SAFE_INTEGER:
            raise ValueError("sequence must be a JCS-safe non-negative integer")
        if self.side not in {"p1", "p2"}:
            raise ValueError("side must be p1 or p2")
        _require_digest(self.request_digest, "request_digest")

    def to_dict(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "sequence": self.sequence,
            "side": self.side,
            "request_digest": self.request_digest,
        }

    @property
    def digest(self) -> str:
        return manifest_digest(self.to_dict())


@dataclass(frozen=True, slots=True)
class OracleResult:
    """Canonical Lab evidence for one fixture execution, without operational data."""

    fixture_id: str
    status: Literal["success", "failure"]
    failure_class: OracleFailureClass | None
    source_manifest_digest: str
    build_manifest_digest: str
    ruleset_snapshot_digest: str
    fixture_digest: str
    seed_digest: str
    input_digest: str
    transcript_digest: str
    canonical_input: bytes
    canonical_transcript: bytes
    request_identities: tuple[OracleRequestIdentity, ...]

    def __post_init__(self) -> None:
        if _FIXTURE_ID_RE.fullmatch(self.fixture_id) is None:
            raise ValueError("fixture_id is invalid")
        if self.status not in {"success", "failure"}:
            raise ValueError("status must be success or failure")
        if (self.status == "success") != (self.failure_class is None):
            raise ValueError("success/failure_class combination is invalid")
        if self.failure_class is not None and not isinstance(
            self.failure_class, OracleFailureClass
        ):
            raise ValueError("failure_class must be an OracleFailureClass")
        for field_name in (
            "source_manifest_digest",
            "build_manifest_digest",
            "ruleset_snapshot_digest",
            "fixture_digest",
            "seed_digest",
            "input_digest",
            "transcript_digest",
        ):
            _require_digest(getattr(self, field_name), field_name)
        input_document = _canonical_evidence_document(self.canonical_input, "canonical_input", dict)
        transcript_document = _canonical_evidence_document(
            self.canonical_transcript, "canonical_transcript", list
        )
        if manifest_digest(input_document) != self.input_digest:
            raise ValueError("input_digest does not match canonical_input")
        if manifest_digest(transcript_document) != self.transcript_digest:
            raise ValueError("transcript_digest does not match canonical_transcript")
        if cast(dict[str, object], input_document).get("fixture_id") != self.fixture_id:
            raise ValueError("canonical input fixture_id does not bind this result")
        if type(self.request_identities) is not tuple or any(
            not isinstance(identity, OracleRequestIdentity) for identity in self.request_identities
        ):
            raise ValueError("request_identities must be an immutable identity tuple")
        if [identity.sequence for identity in self.request_identities] != list(
            range(len(self.request_identities))
        ):
            raise ValueError("request identities must use contiguous canonical sequence numbers")
        if any(identity.fixture_id != self.fixture_id for identity in self.request_identities):
            raise ValueError("request identity fixture IDs must bind this result")
        transcript_identities: list[tuple[PlayerSide, str]] = []
        for entry in cast(list[object], transcript_document):
            if not isinstance(entry, dict) or entry.get("kind") != "side_request":
                continue
            side = entry.get("side")
            request_json = entry.get("request_json")
            if side not in {"p1", "p2"} or type(request_json) is not dict:
                raise ValueError("canonical transcript side_request is invalid")
            transcript_identities.append((cast(PlayerSide, side), manifest_digest(request_json)))
        if [
            (identity.side, identity.request_digest) for identity in self.request_identities
        ] != transcript_identities:
            raise ValueError("request identities do not bind transcript side requests")

    def to_dict(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "status": self.status,
            "failure_class": self.failure_class.value if self.failure_class is not None else None,
            "source_manifest_digest": self.source_manifest_digest,
            "build_manifest_digest": self.build_manifest_digest,
            "ruleset_snapshot_digest": self.ruleset_snapshot_digest,
            "fixture_digest": self.fixture_digest,
            "seed_digest": self.seed_digest,
            "input_digest": self.input_digest,
            "transcript_digest": self.transcript_digest,
            "input": _canonical_evidence_document(self.canonical_input, "canonical_input", dict),
            "transcript": _canonical_evidence_document(
                self.canonical_transcript, "canonical_transcript", list
            ),
            "request_identities": [identity.to_dict() for identity in self.request_identities],
        }

    def canonical_bytes(self) -> bytes:
        return canonicalize(self.to_dict())

    @property
    def digest(self) -> str:
        return manifest_digest(self.to_dict())


@dataclass(frozen=True, slots=True)
class ShowdownOracleConfig:
    """Operational configuration for the selected, candidate Node-22 oracle."""

    source_manifest: ShowdownSourceManifest
    build_manifest: ShowdownBuildManifest
    source_directory: Path
    node_executable: Path
    npm_executable: Path
    process_limits: ShowdownProcessLimits
    environment: Mapping[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.source_manifest, ShowdownSourceManifest):
            raise TypeError("source_manifest must be a ShowdownSourceManifest")
        if not isinstance(self.build_manifest, ShowdownBuildManifest):
            raise TypeError("build_manifest must be a ShowdownBuildManifest")
        if self.build_manifest.source_manifest_digest != self.source_manifest.digest:
            raise ValueError(_SOURCE_TO_BUILD_ERROR)
        if self.build_manifest.commit != self.source_manifest.commit:
            raise ValueError("build manifest commit does not bind the configured source")
        if self.build_manifest.probe_role != "candidate":
            raise ValueError("a runtime session requires the candidate Node-22 build")
        if (self.build_manifest.node_version, self.build_manifest.npm_version) != (
            "22.23.2",
            "10.9.8",
        ):
            raise ValueError("a runtime session requires the approved Node-22/npm pair")
        if not all(
            isinstance(value, Path)
            for value in (self.source_directory, self.node_executable, self.npm_executable)
        ):
            raise TypeError(
                "source_directory, node_executable, and npm_executable must be Path values"
            )
        if not isinstance(self.process_limits, ShowdownProcessLimits):
            raise TypeError("process_limits must be ShowdownProcessLimits")
        if any(
            type(key) is not str or type(value) is not str
            for key, value in self.environment.items()
        ):
            raise TypeError("environment keys and values must be strings")
        if os.name == "nt" and not self.environment.get("SYSTEMROOT"):
            raise ValueError("Windows Node execution requires an explicit non-empty SYSTEMROOT")
        object.__setattr__(self, "environment", MappingProxyType(dict(self.environment)))


@dataclass(frozen=True, slots=True)
class _FixturePlayer:
    name: str
    team: str
    team_choice: str
    move_choice: str


@dataclass(frozen=True, slots=True)
class _Fixture:
    fixture_id: str
    canonical_document: bytes
    fixture_digest: str
    ruleset_snapshot_digest: str
    seed_domain: str
    seed: tuple[int, int, int, int]
    p1: _FixturePlayer
    p2: _FixturePlayer
    expected_tera_line: str | None

    @property
    def seed_digest(self) -> str:
        return manifest_digest({"seed_domain": self.seed_domain, "seed": list(self.seed)})


def _parse_player(value: object, side: PlayerSide) -> _FixturePlayer:
    if not isinstance(value, Mapping):
        raise ValueError(f"players.{side} must be an object")
    _require_exact_keys(
        cast(Mapping[str, object], value), _EXPECTED_PLAYER_FIELDS, f"players.{side}"
    )
    name = _require_string(value["name"], f"players.{side}.name")
    if name != side:
        raise ValueError(f"players.{side}.name must bind its player side")
    team = _require_string(value["team"], f"players.{side}.team")
    team_choice = _require_string(value["team_choice"], f"players.{side}.team_choice")
    move_choice = _require_string(value["move_choice"], f"players.{side}.move_choice")
    if team_choice != "team 1":
        raise ValueError(f"players.{side}.team_choice must be team 1")
    if move_choice not in {"move 1", "move 1 terastallize"}:
        raise ValueError(f"players.{side}.move_choice is unsupported")
    return _FixturePlayer(name=name, team=team, team_choice=team_choice, move_choice=move_choice)


def _parse_fixture(value: Mapping[str, object]) -> _Fixture:
    if not isinstance(value, Mapping):
        raise ValueError("fixture must be an object")
    _require_exact_keys(value, _EXPECTED_FIXTURE_FIELDS, "fixture")
    if value["schema_version"] != 1:
        raise ValueError("fixture schema_version must be 1")
    fixture_id = _require_string(value["fixture_id"], "fixture_id")
    if _FIXTURE_ID_RE.fullmatch(fixture_id) is None:
        raise ValueError("fixture_id is invalid")
    if value["format_id"] != "gen9ou":
        raise ValueError("fixture format_id must be gen9ou")
    ruleset_snapshot_digest = _require_digest(
        value["ruleset_snapshot_digest"], "ruleset_snapshot_digest"
    )
    seed_domain = _require_string(value["seed_domain"], "seed_domain")
    if seed_domain != "showdown-fixture-v1":
        raise ValueError("fixture seed_domain is unsupported")
    seed_value = value["seed"]
    if (
        not isinstance(seed_value, list)
        or len(seed_value) != 4
        or any(type(item) is not int or not 0 <= item <= _MAX_SAFE_INTEGER for item in seed_value)
    ):
        raise ValueError("fixture seed must contain four JCS-safe non-negative integers")
    players = value["players"]
    if not isinstance(players, Mapping):
        raise ValueError("players must be an object")
    _require_exact_keys(cast(Mapping[str, object], players), frozenset({"p1", "p2"}), "players")
    p1 = _parse_player(players["p1"], "p1")
    p2 = _parse_player(players["p2"], "p2")
    expected_tera_line = value["expected_tera_line"]
    if expected_tera_line is not None:
        expected_tera_line = _require_string(expected_tera_line, "expected_tera_line")
        if expected_tera_line != _APPROVED_TERA_LINE:
            raise ValueError("expected_tera_line must bind the approved Tera transition")
    if (expected_tera_line is None) != (p1.move_choice == "move 1"):
        raise ValueError("fixture tera expectation must agree with the p1 move choice")
    if p2.move_choice != "move 1":
        raise ValueError("p2 fixture move must be move 1")
    canonical_document = canonicalize(
        {
            "schema_version": 1,
            "fixture_id": fixture_id,
            "format_id": "gen9ou",
            "ruleset_snapshot_digest": ruleset_snapshot_digest,
            "seed_domain": seed_domain,
            "seed": list(seed_value),
            "players": {
                "p1": {
                    "name": p1.name,
                    "team": p1.team,
                    "team_choice": p1.team_choice,
                    "move_choice": p1.move_choice,
                },
                "p2": {
                    "name": p2.name,
                    "team": p2.team,
                    "team_choice": p2.team_choice,
                    "move_choice": p2.move_choice,
                },
            },
            "expected_tera_line": expected_tera_line,
        }
    )
    return _Fixture(
        fixture_id=fixture_id,
        canonical_document=canonical_document,
        fixture_digest=manifest_digest(json.loads(canonical_document)),
        ruleset_snapshot_digest=ruleset_snapshot_digest,
        seed_domain=seed_domain,
        seed=cast(tuple[int, int, int, int], tuple(seed_value)),
        p1=p1,
        p2=p2,
        expected_tera_line=expected_tera_line,
    )


def _command_json(prefix: str, payload: object) -> str:
    return prefix + canonicalize(payload).decode("utf-8")


def _build_steps(fixture: _Fixture) -> tuple[ProcessInteractionStep, ...]:
    initial = encode_commands(
        (
            _command_json(">start ", {"formatid": "gen9ou", "seed": list(fixture.seed)}),
            _command_json(">player p1 ", {"name": fixture.p1.name, "team": fixture.p1.team}),
            _command_json(">player p2 ", {"name": fixture.p2.name, "team": fixture.p2.team}),
        )
    )
    teams = encode_commands((f">p1 {fixture.p1.team_choice}", f">p2 {fixture.p2.team_choice}"))
    moves = encode_commands((f">p1 {fixture.p1.move_choice}", f">p2 {fixture.p2.move_choice}"))
    tie = encode_commands((">forcetie",))
    requests = ProcessResponseBarrier(request_sides=frozenset({"p1", "p2"}))
    return (
        ProcessInteractionStep(input_bytes=initial, barrier=requests),
        ProcessInteractionStep(input_bytes=teams, barrier=requests),
        ProcessInteractionStep(input_bytes=moves, barrier=requests),
        ProcessInteractionStep(input_bytes=tie, barrier=ProcessResponseBarrier(end=True)),
    )


def _transcript_document(messages: Sequence[ProtocolMessage]) -> list[dict[str, object]]:
    transcript: list[dict[str, object]] = []
    for message in messages:
        if isinstance(message, UpdateMessage):
            transcript.append({"kind": "update", "lines": list(message.lines)})
        elif isinstance(message, SideUpdateMessage):
            transcript.append(
                {
                    "kind": "side_request",
                    "side": message.side,
                    "request_json": _canonical_json_object(message.request_json),
                }
            )
        elif isinstance(message, SideErrorMessage):
            transcript.append({"kind": "side_error", "side": message.side, "line": message.line})
        elif isinstance(message, EndMessage):
            transcript.append({"kind": "end", "log_json": _canonical_json_object(message.log_json)})
        else:
            raise AssertionError("unknown protocol message type")
    return transcript


def _request_identities(
    fixture_id: str, messages: Sequence[ProtocolMessage]
) -> tuple[OracleRequestIdentity, ...]:
    identities: list[OracleRequestIdentity] = []
    for message in messages:
        if isinstance(message, SideUpdateMessage):
            identities.append(
                OracleRequestIdentity(
                    fixture_id=fixture_id,
                    sequence=len(identities),
                    side=message.side,
                    request_digest=manifest_digest(_canonical_json_object(message.request_json)),
                )
            )
    return tuple(identities)


class ShowdownOracleSession:
    """Run one complete, deterministic Lab fixture in one simulator process."""

    def __init__(
        self,
        config: ShowdownOracleConfig,
        *,
        runner: _ProcessRunner | None = None,
    ) -> None:
        if not isinstance(config, ShowdownOracleConfig):
            raise TypeError("config must be a ShowdownOracleConfig")
        self._config = config
        self._runner: _ProcessRunner = runner if runner is not None else ShowdownProcessRunner()

    async def run_fixture(self, fixture_document: Mapping[str, object]) -> OracleResult:
        """Execute one parsed fixture and retain only canonical Lab evidence."""

        fixture = _parse_fixture(fixture_document)
        if fixture.ruleset_snapshot_digest != self._config.build_manifest.ruleset_snapshot_digest:
            raise ValueError("fixture ruleset snapshot does not bind the configured build")
        steps = _build_steps(fixture)
        input_document = {
            "fixture_id": fixture.fixture_id,
            "steps": [step.input_bytes.decode("utf-8") for step in steps],
        }
        canonical_input = canonicalize(input_document)
        input_digest = manifest_digest(input_document)
        evidence = {
            "fixture_id": fixture.fixture_id,
            "source_manifest_digest": self._config.source_manifest.digest,
            "build_manifest_digest": self._config.build_manifest.digest,
            "ruleset_snapshot_digest": fixture.ruleset_snapshot_digest,
            "fixture_digest": fixture.fixture_digest,
            "seed_digest": fixture.seed_digest,
            "input_digest": input_digest,
        }
        try:
            await asyncio.to_thread(
                verify_build_manifest,
                source_manifest=self._config.source_manifest,
                build_manifest=self._config.build_manifest,
                checkout_directory=self._config.source_directory,
                node_executable=self._config.node_executable,
                npm_executable=self._config.npm_executable,
            )
        except BuildOracleError as error:
            return self._failure_result(
                fixture,
                evidence,
                transcript=(),
                identities=(),
                failure_class=error.failure_class,
                canonical_input=canonical_input,
            )
        try:
            with guarded_node_environment(self._config.environment) as environment:
                spec = ShowdownProcessSpec(
                    argv=(
                        str(self._config.node_executable),
                        "pokemon-showdown",
                        "--skip-build",
                        "simulate-battle",
                    ),
                    cwd=self._config.source_directory,
                    env=environment,
                    steps=steps,
                )
                process_result = await self._runner.run(spec, self._config.process_limits)
        except NetworkGuardError:
            return self._failure_result(
                fixture,
                evidence,
                transcript=(),
                identities=(),
                failure_class=OracleFailureClass.BUILD_OUTPUT_MISSING,
                canonical_input=canonical_input,
            )
        except OracleProcessError as error:
            return self._failure_result(
                fixture,
                evidence,
                transcript=(),
                identities=(),
                failure_class=error.failure_class,
                canonical_input=canonical_input,
            )

        transcript = _transcript_document(process_result.messages)
        identities = _request_identities(fixture.fixture_id, process_result.messages)
        if process_result.terminal_side_error is not None:
            return self._failure_result(
                fixture,
                evidence,
                transcript=transcript,
                identities=identities,
                failure_class=OracleFailureClass.RULESET_REJECTED,
                canonical_input=canonical_input,
            )
        if not process_result.completed_barriers:
            return self._failure_result(
                fixture,
                evidence,
                transcript=transcript,
                identities=identities,
                failure_class=OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
                canonical_input=canonical_input,
            )
        if not any(isinstance(message, EndMessage) for message in process_result.messages):
            return self._failure_result(
                fixture,
                evidence,
                transcript=transcript,
                identities=identities,
                failure_class=OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
                canonical_input=canonical_input,
            )
        if fixture.expected_tera_line is not None and not any(
            isinstance(message, UpdateMessage) and fixture.expected_tera_line in message.lines
            for message in process_result.messages
        ):
            return self._failure_result(
                fixture,
                evidence,
                transcript=transcript,
                identities=identities,
                failure_class=OracleFailureClass.RULESET_REJECTED,
                canonical_input=canonical_input,
            )
        return OracleResult(
            **evidence,
            status="success",
            failure_class=None,
            transcript_digest=manifest_digest(transcript),
            canonical_input=canonical_input,
            canonical_transcript=canonicalize(transcript),
            request_identities=identities,
        )

    @staticmethod
    def _failure_result(
        fixture: _Fixture,
        evidence: Mapping[str, str],
        *,
        transcript: Sequence[dict[str, object]],
        identities: tuple[OracleRequestIdentity, ...],
        failure_class: OracleFailureClass,
        canonical_input: bytes,
    ) -> OracleResult:
        return OracleResult(
            **evidence,
            status="failure",
            failure_class=failure_class,
            transcript_digest=manifest_digest(list(transcript)),
            canonical_input=canonical_input,
            canonical_transcript=canonicalize(list(transcript)),
            request_identities=identities,
        )


__all__ = [
    "OracleRequestIdentity",
    "OracleResult",
    "ShowdownOracleConfig",
    "ShowdownOracleSession",
]
