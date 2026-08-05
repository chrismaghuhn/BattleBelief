from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from battlebelief_core.canonicalization import manifest_digest
from battlebelief_core.domain.records.decision_record import (
    MeasurementRunContext,
    ResolvedDecisionRecordBinding,
    RunScopePayload,
    RuntimeAndContractDigests,
)
from battlebelief_lab.evaluation.measurement_runner import MeasurementRunner
from battlebelief_lab.evaluation.schedule import ScheduleRow, SideAssignment
from battlebelief_lab.evaluation.seed_families import SeedFamily
from battlebelief_lab.registration_validation import (
    artifact_digest,
    validate_repository_artifacts,
)
from battlebelief_runtime.adapters.showdown_protocol.frame_decoder import RoomLine
from battlebelief_runtime.adapters.telemetry.jsonl_decision_trace import JsonlDecisionTrace
from battlebelief_runtime.testing.fake_connection import FakeConnection
from battlebelief_runtime.testing.measurement_session import MeasurementSession
from battlebelief_runtime.testing.recording_trace_sink import RecordingTraceSink

ROOT = Path(__file__).resolve().parents[2]
REGISTRATION = ROOT / "registrations/gen9ou/m1-5-core-comparisons-v1.json"
IMPLEMENTATION = ROOT / "registrations/gen9ou/bindings/heuristic_v0-implementation-v2.json"
RUN_P1 = ROOT / "registrations/gen9ou/bindings/heuristic_v0-m15-synthetic-run-p1.json"
RUN_P2 = ROOT / "registrations/gen9ou/bindings/heuristic_v0-m15-synthetic-run-p2.json"
FIXTURES = ROOT / "registrations/gen9ou/synthetic/m15-acceptance-inputs-v1.json"
AUDIT = ROOT / "docs/operations/m1-5-measurement-harness-evidence.md"
REQUEST_FIXTURE = ROOT / "tests/fixtures/requests/move.json"
ROOM_ID = "battle-gen9ou-m15-synthetic"
EXPECTED_ARTIFACT_DIGESTS = {
    REGISTRATION: "sha256:c05cbeb123bcc797d325807a739402266ccdaf0c8e4de9691764af012a3ad03b",
    IMPLEMENTATION: "sha256:56db0a62df44fe708397c5e55f3cff1f17b599f6067bf9ec54846aba4b90ec78",
    FIXTURES: "sha256:10c90ba770cb6b6b4e8c631727463c4356ae20169db796d6f47ed05e4bcb7ce8",
    RUN_P1: "sha256:7a548f890527f9e03cf9b4b2279aa97f3dcdb52eb10bb9c101662ea753fef30c",
    RUN_P2: "sha256:2be21c771b7cfce0cc601f056e9ff98b324c544aa7f4acdf8b34af0105d0b9d1",
}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _room_line(payload: str) -> RoomLine:
    return RoomLine(room_id=ROOM_ID, payload=payload)


def _battle_input(row: ScheduleRow) -> list[RoomLine]:
    request = json.loads(REQUEST_FIXTURE.read_text(encoding="utf-8"))
    request["rqid"] = 5
    our_side = row.side_assignment.value
    request["side"]["id"] = our_side
    for pokemon in request["side"]["pokemon"]:
        pokemon["ident"] = pokemon["ident"].replace("p1:", f"{our_side}:", 1)
    users = {"p1": "misty", "p2": "misty"}
    users[our_side] = "ash"
    metadata = [
        "|init|battle",
        "|gametype|singles",
        "|gen|9",
        "|tier|[Gen 9] OU",
        f"|player|p1|{users['p1']}|1|",
        f"|player|p2|{users['p2']}|1|",
        "|start|",
        f"|switch|{our_side}a: Garchomp|Garchomp, L50, M|183/183",
    ]
    return [
        *(_room_line(line) for line in metadata),
        _room_line("|request|" + json.dumps(request, separators=(",", ":"))),
    ]


class _RetainingBytesIO(io.BytesIO):
    """Keep deterministic test bytes readable after the owned sink closes."""

    def close(self) -> None:
        return None


def _schedule_row(fixture: dict[str, Any], binding: dict[str, Any]) -> ScheduleRow:
    row_value = next(
        row for row in fixture["schedule_rows"] if row["row_id"] == binding["schedule_row_id"]
    )
    return ScheduleRow(
        row_id=row_value["row_id"],
        base_matchup_id=row_value["base_matchup_id"],
        side_assignment=SideAssignment(row_value["side_assignment"]),
        schedule_block=row_value["schedule_block"],
        seed_family=SeedFamily(**row_value["seed_family"]),
        repetition_index=row_value["repetition_index"],
    )


def _run_once(binding_path: Path) -> tuple[dict[str, Any], bytes, tuple[bytes, ...]]:
    implementation = _load(IMPLEMENTATION)
    binding = _load(binding_path)
    fixture = _load(FIXTURES)
    row = _schedule_row(fixture, binding)
    implementation_digest = artifact_digest(implementation)
    runtime_digests = RuntimeAndContractDigests(
        runtime_digest=implementation["runtime_digest"],
        contract_set_digest=implementation["contract_set_digest"],
        policy_digest=implementation["components"]["policy"]["digest"],
        fallback_and_safety_digest=implementation["components"]["fallback_and_safety"]["digest"],
    )
    resolved_binding = ResolvedDecisionRecordBinding(
        evaluation_run_binding_digest=artifact_digest(binding),
        registration_digest=binding["registration_digest"],
        arm_binding_digest=implementation_digest,
        schedule_digest=binding["schedule_digest"],
        budget_profile_digest=binding["budget_profile_digest"],
        seed_family_digest=binding["seed_family_digest"],
        arm_id="heuristic_v0",
        runtime_and_contract_digests=runtime_digests,
    )
    context = MeasurementRunContext.create(
        resolved_binding=resolved_binding,
        run_scope=RunScopePayload(
            registration_digest=binding["registration_digest"],
            arm_binding_digest=implementation_digest,
            schedule_digest=binding["schedule_digest"],
            schedule_row_id=row.row_id,
            budget_profile_digest=binding["budget_profile_digest"],
            seed_family_digest=row.seed_family.digest,
            runtime_digest=implementation["runtime_digest"],
            contract_set_digest=implementation["contract_set_digest"],
        ),
        battle_ordinal=0,
    )
    stream = _RetainingBytesIO()
    sink = RecordingTraceSink(JsonlDecisionTrace(stream))
    session = MeasurementSession(
        connection=FakeConnection(_battle_input(row)),
        room_id=ROOM_ID,
        our_user_id="ash",
        decision_record_context=context,
        trace_sink=sink,
    )
    result = asyncio.run(
        MeasurementRunner(
            session=session,
            trace_sink=sink,
            run_context=context,
            schedule_row=row,
        ).run()
    )
    actual_state = session._session.result_snapshot().state
    record_bytes = tuple(record.canonical_envelope_bytes() for record in sink.records)
    assert result.run_context_digest == context.run_context_digest
    assert actual_state.our_side == row.side_assignment.value
    assert len(sink.records) == 1
    assert sink.records[0].record_status.value == "submitted"
    assert result.explicit_submission_count == 1
    assert result.decision_record_digests == tuple(record.record_digest for record in sink.records)
    assert stream.getvalue() == b"".join(value + b"\n" for value in record_bytes)
    assert b"\r\n" not in stream.getvalue()
    assert all(value.decode("utf-8") for value in record_bytes)
    return result.to_dict(), stream.getvalue(), record_bytes


def test_task21_registration_graph_is_frozen_and_holdouts_are_closed() -> None:
    assert validate_repository_artifacts(ROOT) == []
    for path, expected_digest in EXPECTED_ARTIFACT_DIGESTS.items():
        assert path.is_file(), path
        assert artifact_digest(_load(path)) == expected_digest
    registration = _load(REGISTRATION)
    implementation = _load(IMPLEMENTATION)
    assert registration["registration_status"] == "frozen"
    assert implementation["registration_digest"] == artifact_digest(registration)
    assert registration["pool_access"] == {
        "development": "available",
        "selection": "unopened",
        "power_pilot": "unopened",
        "release_holdout": "unopened",
    }


@pytest.mark.parametrize("binding_path", (RUN_P1, RUN_P2), ids=("p1", "p2"))
def test_each_frozen_run_binding_executes_twice_with_identical_record_bytes(
    binding_path: Path,
) -> None:
    first = _run_once(binding_path)
    second = _run_once(binding_path)
    assert first == second
    result, trace_bytes, record_bytes = first
    assert result["run_status"] == "completed"
    assert result["trace_status"] == "emitted"
    assert record_bytes
    assert trace_bytes == b"".join(value + b"\n" for value in record_bytes)
    for forbidden in (
        ROOM_ID.encode("utf-8"),
        b"ash",
        b"misty",
        b"Garchomp",
        b"Rotom",
        b"p1: Garchomp",
        b"p2: Garchomp",
        b"password",
        b"assertion",
        b"packed-team-secret",
        b"private opponent data",
        b"/var/run",
    ):
        assert forbidden not in trace_bytes
        assert all(forbidden not in value for value in record_bytes)


def test_m15_audit_is_non_normative_and_keeps_live_and_strength_claims_narrow() -> None:
    text = AUDIT.read_text(encoding="utf-8")
    frontmatter_text, body = text.split("---", 2)[1:]
    frontmatter = yaml.safe_load(frontmatter_text)
    registration = _load(REGISTRATION)
    assert frontmatter["document_type"] == "audit"
    assert frontmatter["normative"] is False
    assert "eeb608e6d2f897665b6d01c97e56010ff7f73d56" in body
    assert "11bb983bb39f0e48a9e6b27ea2771e7b3b39e0e6" in body
    assert "31006644403" in body
    assert "registrations/gen9ou/m1-5-core-comparisons-v1.json" in body
    assert artifact_digest(registration) in body
    assert "selection: unopened" in body
    assert "power_pilot: unopened" in body
    assert "release_holdout: unopened" in body
    assert "Observed live measurement coverage: not established" in body
    forbidden_positive_claims = (
        "MVP complete",
        "production ready",
        "engine parity is established",
        "strong bot",
    )
    assert not any(claim.casefold() in body.casefold() for claim in forbidden_positive_claims)
    assert "No strength, parity, release, or MVP claim is made" in body
    for secret_label in ("password", "assertion", "packed-team-secret", "sampled hidden world"):
        assert secret_label not in body


def test_registration_and_run_context_digests_use_the_published_canonicalizer() -> None:
    registration = _load(REGISTRATION)
    implementation = _load(IMPLEMENTATION)
    assert artifact_digest(registration) == manifest_digest(registration)
    assert artifact_digest(implementation) == manifest_digest(implementation)
