from __future__ import annotations

from battlebelief_core.application.observation.reducer import ObservationReducer
from battlebelief_core.domain.records.public_projection import (
    canonical_public_bytes,
    project_observed_state,
)
from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_runtime.adapters.showdown_protocol.parser import parse_battle_line


def test_parser_reducer_projection_redacts_transform_nickname_and_annotation() -> None:
    state = ObservationReducer.reduce(
        ObservationReducer.reduce(
            ObservationReducer.reduce(
                ObservedState.initial("ash"),
                parse_battle_line("|switch|p1a: Ditto|Ditto, L50|100/100", 0),
            ),
            parse_battle_line("|-transform|p1a: Ditto|p2a: SecretNickname", 1),
        ),
        parse_battle_line("|move|p1a: Ditto|Transform|[of] p2a: SecretNickname", 2),
    )

    encoded = canonical_public_bytes(project_observed_state(state)).decode("utf-8")

    assert "SecretNickname" not in encoded
