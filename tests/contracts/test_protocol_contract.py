from __future__ import annotations

import json
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
_PROTOCOL_DIR = _ROOT / "tests" / "fixtures" / "protocol"
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


def _load_fixture_lines(name: str) -> list[str]:
    text = (_PROTOCOL_DIR / name).read_text(encoding="utf-8")
    return text.split("\n")[:-1] if text.endswith("\n") else text.split("\n")


def _process_fixture(name: str) -> tuple[ObservedState, set[type], int]:
    """Classify, parse, and reduce one fixture end to end.

    Returns the final state, the set of concrete event types constructed,
    and the count of UNKNOWN classifications (must be zero for a valid
    corpus fixture).
    """
    state = ObservedState.initial("ash")
    observed_types: set[type] = set()
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
        if classified.kind == RoomPayloadKind.TIMER_MESSAGE:
            try:
                event = parse_inactive_line(line, event_index)
            except TimerOrForfeit:
                event_index += 1
                continue
        else:
            event = parse_battle_line(line, event_index, room_id=_ROOM_ID)
        event_index += 1
        observed_types.add(type(event))
        state = ObservationReducer.reduce(state, event)

    return state, observed_types, unknown_count


class TestProtocolCorpusContract:
    def test_corpus_manifest_lists_all_three_fixtures(self) -> None:
        assert set(_CORPUS["fixtures"]) == {
            "metadata-and-preview.txt",
            "state-transitions.txt",
            "evidence-and-display.txt",
        }

    def test_each_fixture_parses_and_reduces_without_error(self) -> None:
        for name in _CORPUS["fixtures"]:
            _process_fixture(name)  # raises on any UnknownProtocolEvent / Malformed / Invariant

    def test_no_unknown_protocol_events_in_corpus(self) -> None:
        for name in _CORPUS["fixtures"]:
            _, _, unknown_count = _process_fixture(name)
            assert unknown_count == 0, f"{name} contains unclassified lines"

    def test_corpus_covers_every_task2_event_type(self) -> None:
        all_observed: set[type] = set()
        for name in _CORPUS["fixtures"]:
            _, observed_types, _ = _process_fixture(name)
            all_observed |= observed_types
        missing = _REQUIRED_EVENT_TYPES - all_observed
        assert not missing, f"corpus never constructs: {sorted(t.__name__ for t in missing)}"

    def test_metadata_fixture_ends_with_teampreview_state(self) -> None:
        state, _, _ = _process_fixture("metadata-and-preview.txt")
        assert state.generation == 9
        assert state.tier == "[Gen 9] OU"
        assert state.our_side == "p1"
        assert state.battle_started is True
        assert state.turn == 1

    def test_state_transitions_fixture_ends_tied(self) -> None:
        state, _, _ = _process_fixture("state-transitions.txt")
        assert state.tied is True

    def test_evidence_fixture_ends_won(self) -> None:
        state, _, _ = _process_fixture("evidence-and-display.txt")
        assert state.winner == "ash"

    def test_no_reducer_invariant_failures(self) -> None:
        # A defect here would surface as ReducerInvariantError bubbling out
        # of _process_fixture above; this test documents the requirement
        # explicitly per protocol-state.md's zero-invariant-failure bar.
        try:
            for name in _CORPUS["fixtures"]:
                _process_fixture(name)
        except ReducerInvariantError as exc:  # pragma: no cover - documents intent
            raise AssertionError(f"reducer invariant failure in corpus: {exc}") from exc

    def test_no_malformed_protocol_messages(self) -> None:
        try:
            for name in _CORPUS["fixtures"]:
                _process_fixture(name)
        except MalformedProtocolMessage as exc:  # pragma: no cover - documents intent
            raise AssertionError(f"malformed protocol message in corpus: {exc}") from exc

    def test_no_unknown_protocol_event_raised(self) -> None:
        try:
            for name in _CORPUS["fixtures"]:
                _process_fixture(name)
        except UnknownProtocolEvent as exc:  # pragma: no cover - documents intent
            raise AssertionError(f"unknown protocol event in corpus: {exc}") from exc
