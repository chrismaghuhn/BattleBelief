"""Public Lab session tests for the local Showdown mechanics oracle."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

import pytest
from tools.canonicalize_manifest import manifest_digest

from battlebelief_core.canonicalization import canonicalize
from battlebelief_lab.oracle.showdown import session as session_module
from battlebelief_lab.oracle.showdown.errors import OracleFailureClass
from battlebelief_lab.oracle.showdown.installation import BuildOracleError
from battlebelief_lab.oracle.showdown.manifests import ShowdownBuildManifest, ShowdownSourceManifest
from battlebelief_lab.oracle.showdown.network import NetworkGuardError
from battlebelief_lab.oracle.showdown.process import (
    OracleProcessError,
    OracleProcessResult,
    ProcessInteractionStep,
    ShowdownProcessLimits,
    ShowdownProcessSpec,
)
from battlebelief_lab.oracle.showdown.protocol import (
    EndMessage,
    SideErrorMessage,
    SideUpdateMessage,
    UpdateMessage,
)
from battlebelief_lab.oracle.showdown.session import (
    OracleRequestIdentity,
    OracleResult,
    ShowdownOracleConfig,
    ShowdownOracleSession,
)

ROOT = Path(__file__).resolve().parents[5]
FIXTURES = ROOT / "packages/battlebelief-lab/tests/fixtures/showdown_oracle"
_DIGEST = "sha256:" + "0" * 64


def _fixture(name: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def _source_manifest() -> ShowdownSourceManifest:
    document = json.loads(
        (ROOT / "schemas/examples/showdown-oracle-source.example.json").read_text(encoding="utf-8")
    )
    return ShowdownSourceManifest.from_dict(document)


def _build_manifest(source: ShowdownSourceManifest) -> ShowdownBuildManifest:
    document = json.loads(
        (ROOT / "schemas/examples/showdown-oracle-build.example.json").read_text(encoding="utf-8")
    )
    assert document["source_manifest_digest"] == source.digest
    return ShowdownBuildManifest.from_dict(document)


def _limits() -> ShowdownProcessLimits:
    return ShowdownProcessLimits(
        start_timeout_seconds=1.0,
        write_timeout_seconds=1.0,
        response_timeout_seconds=1.0,
        fixture_timeout_seconds=2.0,
        graceful_shutdown_timeout_seconds=1.0,
        forced_shutdown_timeout_seconds=1.0,
        max_stdout_bytes=1024 * 1024,
        max_messages=100,
        max_input_bytes=1024 * 1024,
        max_stderr_bytes=1024,
    )


class _FakeRunner:
    def __init__(
        self,
        result: OracleProcessResult | BaseException,
        *,
        on_run: Callable[[], None] | None = None,
    ) -> None:
        self._result = result
        self._on_run = on_run
        self.specs: list[ShowdownProcessSpec] = []

    async def run(
        self, spec: ShowdownProcessSpec, limits: ShowdownProcessLimits
    ) -> OracleProcessResult:
        self.specs.append(spec)
        assert limits == _limits()
        if self._on_run is not None:
            self._on_run()
        if isinstance(self._result, BaseException):
            raise self._result
        return self._result


@pytest.fixture(autouse=True)
def _replace_installation_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_module, "verify_build_manifest", lambda **_kwargs: None)


def _process_result(*, tera: bool = False) -> OracleProcessResult:
    p1_request = SideUpdateMessage(
        side="p1", lines=('|request|{"active":[]}',), request_json=b'{"active":[]}'
    )
    p2_request = SideUpdateMessage(
        side="p2", lines=('|request|{"active":[]}',), request_json=b'{"active":[]}'
    )
    transition = (
        "|-terastallize|p1a: Garchomp|Ground"
        if tera
        else "|-move|p1a: Garchomp|Earthquake|p2a: Blissey"
    )
    return OracleProcessResult(
        messages=(
            UpdateMessage(lines=("|start",)),
            p1_request,
            p2_request,
            p1_request,
            p2_request,
            UpdateMessage(lines=(transition,)),
            p1_request,
            p2_request,
            UpdateMessage(lines=("|tie",)),
            EndMessage(log_json=b'{"turns":1,"winner":""}'),
        ),
        returncode=0,
        sanitized_stderr="",
        forced_shutdown=False,
        completed_barriers=True,
        terminal_side_error=None,
    )


def _session(
    runner: _FakeRunner,
    *,
    build: ShowdownBuildManifest | None = None,
) -> ShowdownOracleSession:
    source = _source_manifest()
    return ShowdownOracleSession(
        ShowdownOracleConfig(
            source_manifest=source,
            build_manifest=build or _build_manifest(source),
            source_directory=Path("C:/oracle source with spaces"),
            node_executable=Path("C:/node/node.exe"),
            npm_executable=Path("C:/node/npm.cmd"),
            process_limits=_limits(),
            environment={"SYSTEMROOT": "C:/Windows"},
        ),
        runner=runner,
    )


def test_session_executes_one_staged_process_and_emits_stable_request_identities() -> None:
    fixture = _fixture("minimal_gen9ou_input.json")
    first_runner = _FakeRunner(_process_result())
    second_runner = _FakeRunner(_process_result())

    first = asyncio.run(_session(first_runner).run_fixture(fixture))
    second = asyncio.run(_session(second_runner).run_fixture(fixture))

    assert first.status == "success"
    assert first.failure_class is None
    assert first.canonical_bytes() == second.canonical_bytes()
    assert len(first_runner.specs) == 1
    assert first_runner.specs[0].argv[-2:] == ("--skip-build", "simulate-battle")
    assert [step.barrier.end for step in first_runner.specs[0].steps] == [False, False, False, True]
    assert all(isinstance(step, ProcessInteractionStep) for step in first_runner.specs[0].steps)
    assert [step.input_bytes for step in first_runner.specs[0].steps] == [
        (
            b'>start {"formatid":"gen9ou","seed":[1,2,3,4]}\n'
            b'>player p1 {"name":"p1","team":"Garchomp||Leftovers|RoughSkin|Earthquake|Jolly|252,252,4,,,|||||,,,,,Ground"}\n'
            b'>player p2 {"name":"p2","team":"Blissey||Leftovers|NaturalCure|SeismicToss|Bold|252,,252,,4,||,0,,,,|||,,,,,Normal"}\n'
        ),
        b">p1 team 1\n>p2 team 1\n",
        b">p1 move 1\n>p2 move 1\n",
        b">forcetie\n",
    ]
    assert [identity.sequence for identity in first.request_identities] == list(
        range(len(first.request_identities))
    )
    assert {identity.side for identity in first.request_identities} == {"p1", "p2"}
    assert "rqid" not in first.to_dict()
    assert "source_directory" not in first.to_dict()
    assert "node_executable" not in first.to_dict()
    assert first.to_dict()["input"] == json.loads(first.canonical_input)
    assert first.to_dict()["transcript"] == json.loads(first.canonical_transcript)
    assert first.input_digest == manifest_digest(json.loads(first.canonical_input))
    assert first.transcript_digest == manifest_digest(json.loads(first.canonical_transcript))


def test_session_overrides_caller_node_options_with_the_packaged_network_guard() -> None:
    runner = _FakeRunner(_process_result())
    source = _source_manifest()
    session = ShowdownOracleSession(
        ShowdownOracleConfig(
            source_manifest=source,
            build_manifest=_build_manifest(source),
            source_directory=Path("C:/oracle source with spaces"),
            node_executable=Path("C:/node/node.exe"),
            npm_executable=Path("C:/node/npm.cmd"),
            process_limits=_limits(),
            environment={"SYSTEMROOT": "C:/Windows", "NODE_OPTIONS": "--inspect"},
        ),
        runner=runner,
    )

    result = asyncio.run(session.run_fixture(_fixture("minimal_gen9ou_input.json")))

    assert result.status == "success"
    assert runner.specs[0].env["NODE_OPTIONS"].startswith("--require ")
    assert "--inspect" not in runner.specs[0].env["NODE_OPTIONS"]


def test_preflight_runs_before_the_process_and_blocks_a_failed_installation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class OrderedRunner(_FakeRunner):
        async def run(
            self, spec: ShowdownProcessSpec, limits: ShowdownProcessLimits
        ) -> OracleProcessResult:
            events.append("runner")
            return await super().run(spec, limits)

    def reject_installation(**_kwargs: object) -> None:
        events.append("verifier")
        raise BuildOracleError(OracleFailureClass.LOCKFILE_MISMATCH, "private detail")

    monkeypatch.setattr(session_module, "verify_build_manifest", reject_installation)
    runner = OrderedRunner(_process_result())
    result = asyncio.run(_session(runner).run_fixture(_fixture("minimal_gen9ou_input.json")))

    assert events == ["verifier"]
    assert runner.specs == []
    assert result.status == "failure"
    assert result.failure_class is OracleFailureClass.LOCKFILE_MISMATCH
    assert result.canonical_transcript == b"[]"
    assert json.loads(result.canonical_input)["fixture_id"] == "minimal-gen9ou-v1"


@pytest.mark.parametrize(
    "failure_class",
    (
        OracleFailureClass.SOURCE_COMMIT_MISMATCH,
        OracleFailureClass.NODE_VERSION_NOT_APPROVED,
        OracleFailureClass.NPM_VERSION_MISMATCH,
        OracleFailureClass.BUILD_OUTPUT_MISSING,
    ),
)
def test_preflight_mismatches_are_retained_as_stable_oracle_failures(
    failure_class: OracleFailureClass,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _FakeRunner(_process_result())

    def reject_installation(**_kwargs: object) -> None:
        raise BuildOracleError(failure_class, "operational-only diagnostic")

    monkeypatch.setattr(session_module, "verify_build_manifest", reject_installation)
    result = asyncio.run(_session(runner).run_fixture(_fixture("minimal_gen9ou_input.json")))

    assert runner.specs == []
    assert result.status == "failure"
    assert result.failure_class is failure_class
    assert result.canonical_transcript == b"[]"


def test_default_session_verifier_is_not_a_silent_no_op(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class OrderedRunner(_FakeRunner):
        async def run(
            self, spec: ShowdownProcessSpec, limits: ShowdownProcessLimits
        ) -> OracleProcessResult:
            events.append("runner")
            return await super().run(spec, limits)

    def verify_build_manifest(**_kwargs: object) -> None:
        events.append("verifier")

    monkeypatch.setattr(session_module, "verify_build_manifest", verify_build_manifest)
    source = _source_manifest()
    config = ShowdownOracleConfig(
        source_manifest=source,
        build_manifest=_build_manifest(source),
        source_directory=Path("C:/oracle source with spaces"),
        node_executable=Path("C:/node/node.exe"),
        npm_executable=Path("C:/node/npm.cmd"),
        process_limits=_limits(),
        environment={"SYSTEMROOT": "C:/Windows"},
    )
    result = asyncio.run(
        ShowdownOracleSession(config, runner=OrderedRunner(_process_result())).run_fixture(
            _fixture("minimal_gen9ou_input.json")
        )
    )

    assert result.status == "success"
    assert events == ["verifier", "runner"]


def test_public_session_constructor_rejects_verifier_injection() -> None:
    source = _source_manifest()
    config = ShowdownOracleConfig(
        source_manifest=source,
        build_manifest=_build_manifest(source),
        source_directory=Path("C:/oracle source with spaces"),
        node_executable=Path("C:/node/node.exe"),
        npm_executable=Path("C:/node/npm.cmd"),
        process_limits=_limits(),
        environment={"SYSTEMROOT": "C:/Windows"},
    )

    with pytest.raises(TypeError, match="verifier"):
        ShowdownOracleSession(  # type: ignore[call-arg]
            config,
            runner=_FakeRunner(_process_result()),
            verifier=lambda _config: None,
        )


def test_tera_fixture_requires_the_exact_authoritative_transition_line() -> None:
    result = asyncio.run(
        _session(_FakeRunner(_process_result(tera=True))).run_fixture(
            _fixture("tera_transition_input.json")
        )
    )

    assert result.status == "success"
    assert result.failure_class is None
    assert result.transcript_digest == manifest_digest(
        [
            {"kind": "update", "lines": ["|start"]},
            {"kind": "side_request", "side": "p1", "request_json": {"active": []}},
            {"kind": "side_request", "side": "p2", "request_json": {"active": []}},
            {"kind": "side_request", "side": "p1", "request_json": {"active": []}},
            {"kind": "side_request", "side": "p2", "request_json": {"active": []}},
            {"kind": "update", "lines": ["|-terastallize|p1a: Garchomp|Ground"]},
            {"kind": "side_request", "side": "p1", "request_json": {"active": []}},
            {"kind": "side_request", "side": "p2", "request_json": {"active": []}},
            {"kind": "update", "lines": ["|tie"]},
            {"kind": "end", "log_json": {"turns": 1, "winner": ""}},
        ]
    )


def test_missing_tera_line_is_a_stable_ruleset_rejection() -> None:
    result = asyncio.run(
        _session(_FakeRunner(_process_result())).run_fixture(_fixture("tera_transition_input.json"))
    )

    assert result.status == "failure"
    assert result.failure_class is OracleFailureClass.RULESET_REJECTED


def test_tera_fixture_rejects_any_line_other_than_the_approved_transition() -> None:
    fixture = _fixture("tera_transition_input.json")
    fixture["expected_tera_line"] = "|-terastallize|p1a: Garchomp|Fire"

    with pytest.raises(ValueError, match="approved"):
        asyncio.run(_session(_FakeRunner(_process_result(tera=True))).run_fixture(fixture))


def test_process_failure_is_canonicalized_without_raw_diagnostic() -> None:
    result = asyncio.run(
        _session(
            _FakeRunner(
                OracleProcessError(
                    OracleFailureClass.RESPONSE_TIMEOUT, "C:/private/secret token=abc"
                )
            )
        ).run_fixture(_fixture("minimal_gen9ou_input.json"))
    )

    assert result.status == "failure"
    assert result.failure_class is OracleFailureClass.RESPONSE_TIMEOUT
    assert "private" not in result.canonical_bytes().decode("utf-8")
    assert "token" not in result.canonical_bytes().decode("utf-8")
    assert result.canonical_transcript == b"[]"
    assert result.to_dict()["transcript"] == []


def test_unexpected_runner_error_propagates_for_debugging() -> None:
    with pytest.raises(RuntimeError, match="fake implementation failure"):
        asyncio.run(
            _session(_FakeRunner(RuntimeError("fake implementation failure"))).run_fixture(
                _fixture("minimal_gen9ou_input.json")
            )
        )


def test_missing_network_guard_is_a_stable_build_output_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _MissingGuard:
        def __enter__(self) -> Mapping[str, str]:
            raise NetworkGuardError("private package path")

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(
        session_module,
        "guarded_node_environment",
        lambda _environment: _MissingGuard(),
    )

    result = asyncio.run(
        _session(_FakeRunner(_process_result())).run_fixture(_fixture("minimal_gen9ou_input.json"))
    )

    assert result.status == "failure"
    assert result.failure_class is OracleFailureClass.BUILD_OUTPUT_MISSING
    assert "private" not in result.canonical_bytes().decode("utf-8")


def test_nested_fixture_mutation_after_runner_start_cannot_change_bound_evidence() -> None:
    fixture = _fixture("minimal_gen9ou_input.json")
    original_fixture_bytes = canonicalize(fixture)
    original_team = fixture["players"]["p1"]["team"]  # type: ignore[index]

    def mutate_fixture() -> None:
        fixture["players"]["p1"]["team"] = "different team"  # type: ignore[index]

    result = asyncio.run(
        _session(_FakeRunner(_process_result(), on_run=mutate_fixture)).run_fixture(fixture)
    )

    assert result.fixture_digest == manifest_digest(json.loads(original_fixture_bytes))
    assert original_team in json.loads(result.canonical_input)["steps"][0]
    assert "different team" not in json.loads(result.canonical_input)["steps"][0]


def test_side_error_is_classified_as_ruleset_rejection() -> None:
    result = asyncio.run(
        _session(
            _FakeRunner(
                OracleProcessResult(
                    messages=(
                        UpdateMessage(lines=("|start",)),
                        SideErrorMessage(side="p1", line="|error|[Invalid choice] Can't move"),
                    ),
                    returncode=0,
                    sanitized_stderr="",
                    forced_shutdown=True,
                    completed_barriers=False,
                    terminal_side_error=SideErrorMessage(
                        side="p1", line="|error|[Invalid choice] Can't move"
                    ),
                )
            )
        ).run_fixture(_fixture("minimal_gen9ou_input.json"))
    )

    assert result.status == "failure"
    assert result.failure_class is OracleFailureClass.RULESET_REJECTED


def test_session_rejects_tampered_fixture_and_source_build_mismatch() -> None:
    fixture = _fixture("minimal_gen9ou_input.json")
    tampered: Mapping[str, object] = {**fixture, "rqid": "synthetic"}

    with pytest.raises(ValueError, match="fields"):
        asyncio.run(_session(_FakeRunner(_process_result())).run_fixture(tampered))

    source = _source_manifest()
    build_document = _build_manifest(source).to_dict()
    build_document["source_manifest_digest"] = "sha256:" + "f" * 64
    mismatched_build = ShowdownBuildManifest.from_dict(build_document)
    with pytest.raises(ValueError, match="source manifest"):
        ShowdownOracleConfig(
            source_manifest=source,
            build_manifest=mismatched_build,
            source_directory=Path("C:/oracle"),
            node_executable=Path("C:/node/node.exe"),
            npm_executable=Path("C:/node/npm.cmd"),
            process_limits=_limits(),
            environment={"SYSTEMROOT": "C:/Windows"},
        )


def test_config_requires_an_explicit_subprocess_environment() -> None:
    source = _source_manifest()

    with pytest.raises(TypeError, match="environment"):
        ShowdownOracleConfig(
            source_manifest=source,
            build_manifest=_build_manifest(source),
            source_directory=Path("C:/oracle"),
            node_executable=Path("C:/node/node.exe"),
            npm_executable=Path("C:/node/npm.cmd"),
            process_limits=_limits(),
            # Explicitly omitted to prove the public constructor rejects an implicit environment.
            # type: ignore[call-arg]
        )


@pytest.mark.skipif(os.name != "nt", reason="only Node on Windows requires SYSTEMROOT")
def test_windows_config_requires_systemroot_without_inheriting_host_environment() -> None:
    source = _source_manifest()

    with pytest.raises(ValueError, match="SYSTEMROOT"):
        ShowdownOracleConfig(
            source_manifest=source,
            build_manifest=_build_manifest(source),
            source_directory=Path("C:/oracle"),
            node_executable=Path("C:/node/node.exe"),
            npm_executable=Path("C:/node/npm.cmd"),
            process_limits=_limits(),
            environment={},
        )


def test_request_identity_is_digest_bound_and_has_no_rqid_field() -> None:
    identity = OracleRequestIdentity(
        fixture_id="minimal-gen9ou-v1",
        sequence=0,
        side="p1",
        request_digest=manifest_digest({"active": []}),
    )
    input_document = {"fixture_id": "minimal-gen9ou-v1", "steps": []}
    transcript_document: list[object] = [
        {
            "kind": "side_request",
            "side": "p1",
            "request_json": {"active": []},
        }
    ]
    result = OracleResult(
        fixture_id="minimal-gen9ou-v1",
        status="failure",
        failure_class=OracleFailureClass.RULESET_REJECTED,
        source_manifest_digest=_DIGEST,
        build_manifest_digest=_DIGEST,
        ruleset_snapshot_digest=_DIGEST,
        fixture_digest=_DIGEST,
        seed_digest=_DIGEST,
        input_digest=manifest_digest(input_document),
        transcript_digest=manifest_digest(transcript_document),
        canonical_input=canonicalize(input_document),
        canonical_transcript=canonicalize(transcript_document),
        request_identities=(identity,),
    )

    assert result.to_dict()["request_identities"] == [identity.to_dict()]
    assert "rqid" not in result.canonical_bytes().decode("utf-8")


def test_oracle_result_rejects_canonical_input_for_a_different_fixture() -> None:
    input_document = {"fixture_id": "different-fixture-v1", "steps": []}
    transcript_document: list[object] = []

    with pytest.raises(ValueError, match="input fixture_id"):
        OracleResult(
            fixture_id="minimal-gen9ou-v1",
            status="failure",
            failure_class=OracleFailureClass.RULESET_REJECTED,
            source_manifest_digest=_DIGEST,
            build_manifest_digest=_DIGEST,
            ruleset_snapshot_digest=_DIGEST,
            fixture_digest=_DIGEST,
            seed_digest=_DIGEST,
            input_digest=manifest_digest(input_document),
            transcript_digest=manifest_digest(transcript_document),
            canonical_input=canonicalize(input_document),
            canonical_transcript=canonicalize(transcript_document),
            request_identities=(),
        )


@pytest.mark.parametrize(
    "identities",
    [
        (),
        (
            OracleRequestIdentity(
                fixture_id="minimal-gen9ou-v1",
                sequence=0,
                side="p2",
                request_digest=manifest_digest({"active": []}),
            ),
        ),
        (
            OracleRequestIdentity(
                fixture_id="minimal-gen9ou-v1",
                sequence=0,
                side="p1",
                request_digest=manifest_digest({"active": ["different"]}),
            ),
        ),
    ],
)
def test_oracle_result_rejects_request_identity_not_bound_to_transcript(
    identities: tuple[OracleRequestIdentity, ...],
) -> None:
    input_document = {"fixture_id": "minimal-gen9ou-v1", "steps": []}
    transcript_document = [
        {
            "kind": "side_request",
            "side": "p1",
            "request_json": {"active": []},
        }
    ]

    with pytest.raises(ValueError, match="request identities do not bind transcript"):
        OracleResult(
            fixture_id="minimal-gen9ou-v1",
            status="failure",
            failure_class=OracleFailureClass.RULESET_REJECTED,
            source_manifest_digest=_DIGEST,
            build_manifest_digest=_DIGEST,
            ruleset_snapshot_digest=_DIGEST,
            fixture_digest=_DIGEST,
            seed_digest=_DIGEST,
            input_digest=manifest_digest(input_document),
            transcript_digest=manifest_digest(transcript_document),
            canonical_input=canonicalize(input_document),
            canonical_transcript=canonicalize(transcript_document),
            request_identities=identities,
        )
