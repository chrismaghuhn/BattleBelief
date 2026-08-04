from __future__ import annotations

from battlebelief_lab.evaluation.team_clustering import (
    canonical_team_projection,
    team_cluster_id,
)


def _member(species: str) -> dict[str, object]:
    return {
        "species": species,
        "moves": ["Protect", "Tackle", "Recover", "U-turn"],
        "item": "Leftovers",
        "ability": "Pressure",
        "nature": "Timid",
        "evs": {"hp": 0, "atk": 0, "def": 0, "spa": 252, "spd": 4, "spe": 252},
        "ivs": {"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31},
        "level": 100,
        "happiness": 255,
        "gender": None,
        "shiny": False,
        "pokeball": "poke ball",
        "hidden_power_type": None,
        "tera_type": "Water",
    }


def test_exact_team_cluster_is_member_order_independent() -> None:
    team = [_member("Mr. Mime"), _member("Pikachu")]
    team.extend(_member(f"Slot {i}") for i in range(4))
    reversed_team = list(reversed(team))
    assert team_cluster_id(team) == team_cluster_id(reversed_team)
    assert canonical_team_projection(team)["member_count"] == 6
