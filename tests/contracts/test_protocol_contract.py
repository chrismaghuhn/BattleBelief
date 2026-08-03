from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from battlebelief_core.application.observation.reducer import ObservationReducer
from battlebelief_core.domain.events import (
    AbilityChanged,
    BattleInit,
    BattleRated,
    BattleStarted,
    BattleTied,
    BattleWon,
    BoostChanged,
    BoostsCleared,
    BoostsCopied,
    BoostsInverted,
    BoostsSwapped,
    FieldConditionChanged,
    FormChanged,
    GameTypeDeclared,
    GenerationDeclared,
    HealthChanged,
    IdentityChanged,
    IgnoredDisplayEvent,
    ItemChanged,
    MovePrevented,
    MoveUsed,
    PlayerDeclared,
    PokemonDragged,
    PokemonFainted,
    PokemonSwitched,
    PokemonTransformed,
    PreviewCleared,
    PreviewPokemonDeclared,
    RechargeChanged,
    RuleDeclared,
    SideConditionChanged,
    SideConditionsSwapped,
    StatusChanged,
    TeamPreviewStarted,
    TeamSizeDeclared,
    TeamStatusCured,
    Terastallized,
    TierDeclared,
    TurnStarted,
    VisibleEvidence,
    VolatileChanged,
    WeatherChanged,
)
from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_runtime.adapters.showdown_protocol.parser import (
    parse_battle_line,
    parse_inactive_line,
)
from battlebelief_runtime.adapters.showdown_protocol.room_payload_classifier import (
    RoomPayloadKind,
    classify_room_payload,
)
from battlebelief_runtime.errors.protocol import TimerOrForfeit

_ROOT = Path(__file__).resolve().parents[2]
_PROTOCOL_DIR = (_ROOT / "tests" / "fixtures" / "protocol").resolve(strict=True)
_CORPUS = json.loads((_PROTOCOL_DIR / "corpus.json").read_text(encoding="utf-8"))
_ROOM_ID = "battle-gen9ou-corpus-1"

# Every Task-2 canonical event type. The corpus, taken together, must
# construct each of these at least once.
_REQUIRED_EVENT_TYPES = {
    BattleInit,
    PlayerDeclared,
    TeamSizeDeclared,
    GameTypeDeclared,
    GenerationDeclared,
    TierDeclared,
    BattleRated,
    RuleDeclared,
    PreviewPokemonDeclared,
    PreviewCleared,
    TeamPreviewStarted,
    BattleStarted,
    TurnStarted,
    BattleWon,
    BattleTied,
    PokemonSwitched,
    PokemonDragged,
    PokemonFainted,
    MoveUsed,
    MovePrevented,
    HealthChanged,
    StatusChanged,
    TeamStatusCured,
    BoostChanged,
    BoostsSwapped,
    BoostsCopied,
    BoostsCleared,
    BoostsInverted,
    ItemChanged,
    AbilityChanged,
    IdentityChanged,
    FormChanged,
    PokemonTransformed,
    Terastallized,
    VolatileChanged,
    RechargeChanged,
    WeatherChanged,
    FieldConditionChanged,
    SideConditionChanged,
    SideConditionsSwapped,
    VisibleEvidence,
    IgnoredDisplayEvent,
}


@dataclass(frozen=True, slots=True)
class _CorpusRun:
    state: ObservedState
    observed_types: frozenset[type]
    terminal_classifications: tuple[str, ...]
    unknown_count: int


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


def _load_fixture_lines(name: str) -> list[str]:
    text = _fixture_path(name).read_text(encoding="utf-8")
    return text.split("\n")[:-1] if text.endswith("\n") else text.split("\n")


def _process_fixture(name: str) -> _CorpusRun:
    """Classify, parse, and reduce one fixture end to end.

    Returns the final state, concrete event types, terminal classifications,
    and the UNKNOWN-classification count.
    """
    state = ObservedState.initial("ash")
    observed_types: set[type] = set()
    terminal_classifications: list[str] = []
    unknown_count = 0
    event_index = 0

    for line in _load_fixture_lines(name):
        if line == "":
            # A truly blank source line carries no signal (frame_decoder
            # already drops these at the room-framing layer); only the
            # literal spacer payload "|" is meaningful.
            continue
        classified = classify_room_payload(line)
        if classified.kind == RoomPayloadKind.UNKNOWN:
            unknown_count += 1
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
        event_index += 1
        observed_types.add(type(event))
        state = ObservationReducer.reduce(state, event)

    return _CorpusRun(
        state=state,
        observed_types=frozenset(observed_types),
        terminal_classifications=tuple(terminal_classifications),
        unknown_count=unknown_count,
    )


class TestProtocolCorpusContract:
    def test_corpus_manifest_lists_all_three_fixtures(self) -> None:
        assert set(_CORPUS["fixtures"]) == {
            "metadata-and-preview.txt",
            "state-transitions.txt",
            "evidence-and-display.txt",
        }

    def test_each_manifest_fixture_exists_strictly_beneath_protocol_directory(self) -> None:
        for name in _CORPUS["fixtures"]:
            _fixture_path(name)

    def test_each_fixture_parses_and_reduces_without_error(self) -> None:
        for name in _CORPUS["fixtures"]:
            _process_fixture(name)  # raises on any UnknownProtocolEvent / Malformed / Invariant

    def test_no_unknown_protocol_events_in_corpus(self) -> None:
        for name in _CORPUS["fixtures"]:
            result = _process_fixture(name)
            assert result.unknown_count == 0, f"{name} contains unclassified lines"

    def test_corpus_covers_every_task2_event_type(self) -> None:
        all_observed: set[type] = set()
        for name in _CORPUS["fixtures"]:
            all_observed |= _process_fixture(name).observed_types
        missing = _REQUIRED_EVENT_TYPES - all_observed
        assert not missing, f"corpus never constructs: {sorted(t.__name__ for t in missing)}"

    def test_metadata_fixture_ends_with_teampreview_state(self) -> None:
        state = _process_fixture("metadata-and-preview.txt").state
        assert state.generation == 9
        assert state.tier == "[Gen 9] OU"
        assert state.our_side == "p1"
        assert state.battle_started is True
        assert state.turn == 1

    def test_state_transitions_fixture_ends_tied(self) -> None:
        state = _process_fixture("state-transitions.txt").state
        assert state.tied is True

    def test_evidence_fixture_ends_won(self) -> None:
        state = _process_fixture("evidence-and-display.txt").state
        assert state.winner == "ash"

    def test_terminal_classifications_are_counted(self) -> None:
        assert _process_fixture("metadata-and-preview.txt").terminal_classifications == ()
        assert _process_fixture("state-transitions.txt").terminal_classifications == ()
        assert _process_fixture("evidence-and-display.txt").terminal_classifications == (
            TimerOrForfeit.code,
            TimerOrForfeit.code,
            TimerOrForfeit.code,
        )
