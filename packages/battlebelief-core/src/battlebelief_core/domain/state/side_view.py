from __future__ import annotations

from dataclasses import dataclass

from battlebelief_core.domain.state.pokemon_view import PokemonView
from battlebelief_core.domain.state.values import PreviewPokemon


@dataclass(frozen=True, slots=True)
class SideView:
    side_id: str
    user_id: str | None
    display_name: str | None
    team_size: int | None
    preview_roster: tuple[PreviewPokemon, ...]
    active_slot: int | None
    pokemon: tuple[PokemonView, ...]
    side_conditions: tuple[tuple[str, int], ...]  # sorted (condition, layer_count)
