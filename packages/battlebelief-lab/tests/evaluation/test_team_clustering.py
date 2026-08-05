from __future__ import annotations

import pytest

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


def test_exact_team_cluster_has_a_frozen_vector() -> None:
    team = [_member("Mr. Mime"), _member("Pikachu")]
    team.extend(_member(f"Slot {i}") for i in range(4))
    assert (
        team_cluster_id(team)
        == "sha256:5151382bec2d7e1b8b25aa9c2cc9935312af34b68d6e28601267319e6301f09f"
    )


def test_team_cluster_rejects_duplicate_members_and_excessive_evs() -> None:
    team = [_member("Pikachu") for _ in range(6)]
    with pytest.raises(ValueError, match="duplicate"):
        team_cluster_id(team)
    team = [_member(f"Slot {i}") for i in range(6)]
    team[0]["evs"] = {"hp": 252, "atk": 252, "def": 7, "spa": 0, "spd": 0, "spe": 0}
    with pytest.raises(ValueError, match="EV"):
        team_cluster_id(team)
