from __future__ import annotations

from pathlib import Path

import pytest

from battlebelief_runtime.adapters.team_files.loader import load_packed_team
from battlebelief_runtime.adapters.team_files.packed_team import PackedTeam
from battlebelief_runtime.errors.setup import TeamValidationError

_REPO_ROOT = Path(__file__).resolve().parents[4]
_TEAMS_DIR = _REPO_ROOT / "tests" / "fixtures" / "teams"


def _load(name: str) -> str:
    return (_TEAMS_DIR / name).read_text(encoding="utf-8")


class TestValidPackedTeam:
    def test_example_fixture_loads(self) -> None:
        team = load_packed_team(_load("gen9ou-example-packed.txt"))
        assert isinstance(team, PackedTeam)
        assert team.sealed.member_count == 6

    def test_trailing_newline_is_stripped_not_treated_as_content(self) -> None:
        raw = _load("gen9ou-example-packed.txt")
        assert raw.endswith("\n")
        team = load_packed_team(raw)
        assert not team.packed.endswith("\n")

    def test_digest_is_stable(self) -> None:
        raw = _load("gen9ou-example-packed.txt")
        team1 = load_packed_team(raw)
        team2 = load_packed_team(raw)
        assert team1.sealed.digest == team2.sealed.digest

    def test_digest_changes_with_content(self) -> None:
        raw = _load("gen9ou-example-packed.txt")
        team1 = load_packed_team(raw)
        modified = raw.replace("Garchomp", "Garchompp")
        team2 = load_packed_team(modified)
        assert team1.sealed.digest != team2.sealed.digest

    def test_single_pokemon_team_is_valid(self) -> None:
        team = load_packed_team(
            "Garchomp||rockyhelmet|roughskin|earthquake|jolly|0,252,0,0,4,252|M|,0,,,,|S|50|,,,,,Ground\n"
        )
        assert team.sealed.member_count == 1


class TestRejectedInputs:
    def test_inner_carriage_return_is_rejected(self) -> None:
        with pytest.raises(TeamValidationError):
            load_packed_team("Garchomp||item|ability|move\rmore|jolly|stats|M|ivs|S|50|misc\n")

    def test_inner_newline_is_rejected(self) -> None:
        with pytest.raises(TeamValidationError):
            load_packed_team(
                "Garchomp||item|ability|move|jolly|stats|M|ivs|S|50|misc\nRotom||item2\n"
            )

    def test_empty_input_is_rejected(self) -> None:
        with pytest.raises(TeamValidationError):
            load_packed_team("")

    def test_seven_members_is_rejected(self) -> None:
        one = "Mon||item|ability|move|jolly|0,0,0,0,0,0|M|,,,,,|S|50|,,,,,Normal"
        seven = "]".join([one] * 7) + "\n"
        with pytest.raises(TeamValidationError):
            load_packed_team(seven)

    def test_entry_without_pipe_structure_is_rejected(self) -> None:
        with pytest.raises(TeamValidationError):
            load_packed_team("justaname\n")

    def test_human_export_format_is_not_line_joined(self) -> None:
        human_export = (
            "Garchomp @ Rocky Helmet\n"
            "Ability: Rough Skin\n"
            "Level: 50\n"
            "- Earthquake\n"
            "- Swords Dance\n"
        )
        with pytest.raises(TeamValidationError):
            load_packed_team(human_export)

    def test_empty_entry_between_brackets_is_rejected(self) -> None:
        with pytest.raises(TeamValidationError):
            load_packed_team(
                "Mon||item|ability|move|jolly|0,0,0,0,0,0|M|,,,,,|S|50|,,,,,Normal]]\n"
            )


class TestNoLegalityClaim:
    def test_loader_does_not_expose_a_legality_field(self) -> None:
        team = load_packed_team(_load("gen9ou-example-packed.txt"))
        assert not hasattr(team.sealed, "legal")
        assert not hasattr(team, "legal")
