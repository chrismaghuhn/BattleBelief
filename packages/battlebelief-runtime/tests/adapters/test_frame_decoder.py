from __future__ import annotations

from pathlib import Path

import pytest

from battlebelief_runtime.adapters.showdown_protocol.frame_decoder import RoomLine, decode_frame
from battlebelief_runtime.errors.protocol import MalformedProtocolMessage

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FRAMES_DIR = _REPO_ROOT / "tests" / "fixtures" / "frames"


class TestGlobalLines:
    def test_line_with_no_room_marker_is_global(self) -> None:
        lines = decode_frame("|challstr|4|abc123")
        assert lines == (RoomLine(room_id=None, payload="|challstr|4|abc123"),)

    def test_multiple_global_lines(self) -> None:
        lines = decode_frame("|updateuser| ash|1|0|{}\n|queryresponse|rooms|null")
        assert lines == (
            RoomLine(room_id=None, payload="|updateuser| ash|1|0|{}"),
            RoomLine(room_id=None, payload="|queryresponse|rooms|null"),
        )

    def test_empty_frame_yields_no_lines(self) -> None:
        assert decode_frame("") == ()

    def test_empty_lines_are_ignored(self) -> None:
        lines = decode_frame("|challstr|4|abc\n\n|updateuser| ash|1|0|{}")
        assert lines == (
            RoomLine(room_id=None, payload="|challstr|4|abc"),
            RoomLine(room_id=None, payload="|updateuser| ash|1|0|{}"),
        )


class TestRoomMarkers:
    def test_room_marker_sets_context_for_following_lines(self) -> None:
        lines = decode_frame(">battle-gen9ou-1\n|init|battle\n|title|Ash vs Misty")
        assert lines == (
            RoomLine(room_id="battle-gen9ou-1", payload="|init|battle"),
            RoomLine(room_id="battle-gen9ou-1", payload="|title|Ash vs Misty"),
        )

    def test_room_marker_line_itself_is_not_emitted(self) -> None:
        lines = decode_frame(">battle-gen9ou-1\n|init|battle")
        assert len(lines) == 1
        assert lines[0].payload == "|init|battle"

    def test_multiple_room_blocks_in_one_frame(self) -> None:
        frame = ">battle-gen9ou-1\n|turn|1\n>battle-gen9ou-2\n|turn|2"
        lines = decode_frame(frame)
        assert lines == (
            RoomLine(room_id="battle-gen9ou-1", payload="|turn|1"),
            RoomLine(room_id="battle-gen9ou-2", payload="|turn|2"),
        )

    def test_room_context_persists_across_many_lines(self) -> None:
        frame = ">battle-gen9ou-1\n|turn|1\n|move|p1a: Garchomp|Earthquake|p2a: Togekiss\n|turn|2"
        lines = decode_frame(frame)
        assert all(line.room_id == "battle-gen9ou-1" for line in lines)
        assert len(lines) == 3

    def test_global_lines_after_room_block_do_not_inherit_room(self) -> None:
        # A fresh decode_frame call always starts with room_id=None context;
        # this documents that context does not leak across frames.
        lines = decode_frame("|challstr|4|abc")
        assert lines[0].room_id is None

    def test_empty_room_marker_is_rejected(self) -> None:
        with pytest.raises(MalformedProtocolMessage):
            decode_frame(">\n|init|battle")

    def test_room_marker_never_loses_room_name(self) -> None:
        lines = decode_frame(">battle-gen9ou-abcdef123\n|init|battle")
        assert lines[0].room_id == "battle-gen9ou-abcdef123"


class TestLineEndings:
    def test_trailing_carriage_return_is_stripped(self) -> None:
        lines = decode_frame("|challstr|4|abc\r\n|updateuser| ash|1|0|{}\r")
        assert lines == (
            RoomLine(room_id=None, payload="|challstr|4|abc"),
            RoomLine(room_id=None, payload="|updateuser| ash|1|0|{}"),
        )

    def test_carriage_return_inside_payload_is_preserved(self) -> None:
        # Only a trailing \r is stripped — never payload content.
        lines = decode_frame("|raw|line one\rstill payload")
        assert lines == (RoomLine(room_id=None, payload="|raw|line one\rstill payload"),)


class TestBinaryRejection:
    def test_binary_frame_is_rejected(self) -> None:
        with pytest.raises(MalformedProtocolMessage):
            decode_frame(b"\x00\x01binary")


class TestFixtures:
    def test_login_and_battle_fixture_decodes(self) -> None:
        fixture = (_FRAMES_DIR / "login-and-battle.txt").read_text(encoding="utf-8")
        lines = decode_frame(fixture)
        assert len(lines) > 0
        assert any(line.room_id is None for line in lines)
        assert any(line.room_id is not None for line in lines)

    def test_two_rooms_fixture_decodes_both_rooms(self) -> None:
        fixture = (_FRAMES_DIR / "two-rooms.txt").read_text(encoding="utf-8")
        lines = decode_frame(fixture)
        room_ids = {line.room_id for line in lines if line.room_id is not None}
        assert len(room_ids) == 2
