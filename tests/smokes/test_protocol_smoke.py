from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from battlebelief_core.application.observation.reducer import ObservationReducer
from battlebelief_core.domain.events.base import BattleEvent
from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_core.errors import ReducerInvariantError
from battlebelief_runtime.adapters.showdown_protocol.parser import (
    parse_battle_line,
    parse_inactive_line,
)
from battlebelief_runtime.adapters.showdown_protocol.room_payload_classifier import (
    RoomPayloadKind,
    classify_room_payload,
)
from battlebelief_runtime.errors.protocol import (
    MalformedProtocolMessage,
    TimerOrForfeit,
    UnknownProtocolEvent,
)

_ROOT = Path(__file__).resolve().parents[2]
_PROTOCOL_DIR = (_ROOT / "tests" / "fixtures" / "protocol").resolve(strict=True)
_CORPUS = json.loads((_PROTOCOL_DIR / "corpus.json").read_text(encoding="utf-8"))
_ROOM_ID = "battle-gen9ou-corpus-smoke-1"


@dataclass(frozen=True, slots=True)
class _FixtureRun:
    final_state: ObservedState
    event_type_sequence: tuple[type[BattleEvent], ...]
    terminal_classification_sequence: tuple[str, ...]
    terminal_classification_counts: tuple[tuple[str, int], ...]
    unknown_count: int
    failures: tuple[str, ...]


def _fixture_path(name: str) -> Path:
    try:
        path = (_PROTOCOL_DIR / name).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise AssertionError(f"protocol fixture does not exist: {name!r}") from exc
    assert path != _PROTOCOL_DIR and path.is_relative_to(_PROTOCOL_DIR), (
        f"protocol fixture must resolve strictly beneath {_PROTOCOL_DIR}: {name!r} -> {path}"
    )
    assert path.is_file(), f"protocol fixture is not a file: {name!r} -> {path}"
    return path


def _failure(name: str, line_number: int, code: str, detail: object) -> str:
    message = str(detail).replace("\r", "\\r").replace("\n", "\\n")
    return f"{name}:{line_number}: {code}: {message}"


def _run_lines(name: str, lines: list[str]) -> _FixtureRun:
    state = ObservedState.initial("ash")
    event_types: list[type[BattleEvent]] = []
    terminal_classifications: list[str] = []
    failures: list[str] = []
    unknown_count = 0
    event_index = 0

    for line_number, line in enumerate(lines, start=1):
        if line == "":
            continue

        try:
            classified = classify_room_payload(line)
        except Exception as exc:
            failures.append(
                _failure(
                    name,
                    line_number,
                    "unexpected_classifier_failure",
                    f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        if classified.kind == RoomPayloadKind.UNKNOWN:
            unknown_count += 1
            failures.append(
                _failure(name, line_number, UnknownProtocolEvent.code, repr(classified.payload))
            )
            continue
        if classified.kind in (
            RoomPayloadKind.DECISION_REQUEST,
            RoomPayloadKind.BATTLE_ERROR,
            RoomPayloadKind.ROOM_CONTROL_OR_CHAT,
        ):
            continue

        try:
            if classified.kind == RoomPayloadKind.TIMER_MESSAGE:
                event = parse_inactive_line(line, event_index)
            else:
                event = parse_battle_line(line, event_index, room_id=_ROOM_ID)
        except TimerOrForfeit as exc:
            terminal_classifications.append(exc.code)
            event_index += 1
            continue
        except (MalformedProtocolMessage, UnknownProtocolEvent) as exc:
            failures.append(_failure(name, line_number, exc.code, exc))
            event_index += 1
            continue
        except Exception as exc:
            failures.append(
                _failure(
                    name,
                    line_number,
                    "unexpected_parser_failure",
                    f"{type(exc).__name__}: {exc}",
                )
            )
            event_index += 1
            continue

        state_before = deepcopy(state)
        try:
            next_state = ObservationReducer.reduce(state, event)
        except ReducerInvariantError as exc:
            failures.append(_failure(name, line_number, "reducer_invariant_failure", exc))
            if state != state_before:
                failures.append(
                    _failure(
                        name,
                        line_number,
                        "reducer_state_mutation",
                        "failed reducer line mutated the prior valid state",
                    )
                )
            state = state_before
        except Exception as exc:
            failures.append(
                _failure(
                    name,
                    line_number,
                    "unexpected_reducer_failure",
                    f"{type(exc).__name__}: {exc}",
                )
            )
            if state != state_before:
                failures.append(
                    _failure(
                        name,
                        line_number,
                        "reducer_state_mutation",
                        "failed reducer line mutated the prior valid state",
                    )
                )
            state = state_before
        else:
            state = next_state
            event_types.append(type(event))
        event_index += 1

    terminal_counts = tuple(sorted(Counter(terminal_classifications).items()))
    return _FixtureRun(
        final_state=state,
        event_type_sequence=tuple(event_types),
        terminal_classification_sequence=tuple(terminal_classifications),
        terminal_classification_counts=terminal_counts,
        unknown_count=unknown_count,
        failures=tuple(failures),
    )


def _run_fixture(name: str) -> _FixtureRun:
    lines = _fixture_path(name).read_text(encoding="utf-8").splitlines()
    return _run_lines(name, lines)


def test_protocol_corpus_is_failure_free_and_deterministic() -> None:
    errors: list[str] = []

    for fixture_name in _CORPUS["fixtures"]:
        runs: list[_FixtureRun] = []
        for run_number in (1, 2):
            try:
                run = _run_fixture(fixture_name)
            except Exception as exc:
                errors.append(
                    _failure(
                        fixture_name,
                        0,
                        "fixture_error",
                        f"run {run_number}: {type(exc).__name__}: {exc}",
                    )
                )
                continue
            runs.append(run)
            errors.extend(f"{failure} (run {run_number})" for failure in run.failures)
            if run.unknown_count != 0:
                errors.append(
                    _failure(
                        fixture_name,
                        0,
                        "unknown_protocol_event_count",
                        f"run {run_number}: expected 0, got {run.unknown_count}",
                    )
                )

        if len(runs) != 2:
            continue

        first, second = runs
        deterministic_fields = (
            ("final_state", first.final_state, second.final_state),
            ("event_type_sequence", first.event_type_sequence, second.event_type_sequence),
            (
                "terminal_classification_sequence",
                first.terminal_classification_sequence,
                second.terminal_classification_sequence,
            ),
            (
                "terminal_classification_counts",
                first.terminal_classification_counts,
                second.terminal_classification_counts,
            ),
            ("unknown_count", first.unknown_count, second.unknown_count),
        )
        for field_name, first_value, second_value in deterministic_fields:
            if first_value != second_value:
                errors.append(
                    _failure(
                        fixture_name,
                        0,
                        "nondeterministic_protocol_run",
                        f"{field_name} differs between fresh runs",
                    )
                )

        expected_terminal_count = 3 if fixture_name == "evidence-and-display.txt" else 0
        expected_sequence = (TimerOrForfeit.code,) * expected_terminal_count
        if first.terminal_classification_sequence != expected_sequence:
            errors.append(
                _failure(
                    fixture_name,
                    0,
                    "terminal_classification_mismatch",
                    f"expected {expected_sequence!r}, got {first.terminal_classification_sequence!r}",
                )
            )
        expected_counts = ((TimerOrForfeit.code, 3),) if expected_terminal_count else ()
        if first.terminal_classification_counts != expected_counts:
            errors.append(
                _failure(
                    fixture_name,
                    0,
                    "terminal_classification_count_mismatch",
                    f"expected {expected_counts!r}, got {first.terminal_classification_counts!r}",
                )
            )

    assert not errors, "protocol smoke failures:\n" + "\n".join(errors)


def test_protocol_runner_collects_all_failures_without_mutating_valid_state() -> None:
    valid_run = _run_lines("synthetic.txt", ["|init|battle"])
    failed_run = _run_lines(
        "synthetic.txt",
        [
            "|init|battle",
            "|player|p3|ash|1|",
            "|turn|not-a-number",
            "|not-a-real-wire-type",
        ],
    )

    assert failed_run.final_state == valid_run.final_state
    assert failed_run.unknown_count == 1
    assert len(failed_run.failures) == 3
    assert failed_run.failures[0].startswith("synthetic.txt:2: reducer_invariant_failure:")
    assert failed_run.failures[1].startswith("synthetic.txt:3: malformed_protocol_message:")
    assert failed_run.failures[2].startswith("synthetic.txt:4: unknown_protocol_event:")
