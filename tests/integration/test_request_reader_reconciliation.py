from __future__ import annotations

from pathlib import Path

from battlebelief_core.application.observation.reducer import ObservationReducer
from battlebelief_core.application.safety.request_reconciler import (
    ReconciliationStatus,
    RequestReconciler,
)
from battlebelief_core.domain.events.metadata import (
    BattleInit,
    GameTypeDeclared,
    GenerationDeclared,
    PlayerDeclared,
    TeamSizeDeclared,
    TierDeclared,
)
from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_runtime.adapters.showdown_protocol.request_reader import read_request

_ROOT = Path(__file__).resolve().parents[2]
_REQUESTS_DIR = _ROOT / "tests" / "fixtures" / "requests"
_ROOM = "battle-gen9ou-1"
_USER = "ash"


def _base_state() -> ObservedState:
    state = ObservedState.initial(_USER)
    for event in (
        BattleInit(event_index=0, room_id=_ROOM),
        PlayerDeclared(event_index=1, side_id="p1", user_id=_USER, display_name=_USER),
        PlayerDeclared(event_index=2, side_id="p2", user_id="misty", display_name="misty"),
        GameTypeDeclared(event_index=3, game_type="singles"),
        GenerationDeclared(event_index=4, generation=9),
        TierDeclared(event_index=5, tier="[Gen 9] OU"),
        TeamSizeDeclared(event_index=6, side_id="p1", size=6),
        TeamSizeDeclared(event_index=7, side_id="p2", size=6),
    ):
        state = ObservationReducer.reduce(state, event)
    return state


def test_wait_fixture_reconciles_to_accept() -> None:
    payload = (_REQUESTS_DIR / "wait.json").read_text(encoding="utf-8")
    request = read_request(_ROOM, payload)
    result = RequestReconciler.reconcile(
        room_id=_ROOM,
        request=request,
        state=_base_state(),
        latest_rqid=None,
    )
    assert result.status == ReconciliationStatus.ACCEPT
