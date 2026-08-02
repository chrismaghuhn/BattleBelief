from __future__ import annotations

from pathlib import Path

from battlebelief_runtime.adapters.showdown_protocol.frame_decoder import decode_frame
from battlebelief_runtime.adapters.showdown_protocol.room_payload_classifier import (
    ClassifiedRoomPayload,
    RoomPayloadKind,
    classify_room_payload,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FRAMES_DIR = _REPO_ROOT / "tests" / "fixtures" / "frames"


def _classify(payload: str) -> RoomPayloadKind:
    return classify_room_payload(payload).kind


class TestSpacerAndChat:
    def test_exact_spacer_is_battle_event(self) -> None:
        assert _classify("|") == RoomPayloadKind.BATTLE_EVENT

    def test_double_pipe_message_is_room_control_or_chat(self) -> None:
        assert _classify("||This is a raw message") == RoomPayloadKind.ROOM_CONTROL_OR_CHAT

    def test_plaintext_without_leading_pipe_is_room_control_or_chat(self) -> None:
        assert _classify("just some text") == RoomPayloadKind.ROOM_CONTROL_OR_CHAT


class TestDecisionRequestAndError:
    def test_request_is_decision_request(self) -> None:
        assert _classify('|request|{"active":[]}') == RoomPayloadKind.DECISION_REQUEST

    def test_error_is_battle_error(self) -> None:
        assert _classify("|error|[Invalid choice] Can't do that") == RoomPayloadKind.BATTLE_ERROR


class TestTimerMessages:
    def test_inactive_is_timer_message(self) -> None:
        assert _classify("|inactive|Time left: 150 sec") == RoomPayloadKind.TIMER_MESSAGE

    def test_inactiveoff_is_timer_message(self) -> None:
        assert _classify("|inactiveoff|Timer is now off.") == RoomPayloadKind.TIMER_MESSAGE


class TestBattleEvents:
    def test_move_is_battle_event(self) -> None:
        assert _classify("|move|p1a: Garchomp|Earthquake|p2a: Togekiss") == (
            RoomPayloadKind.BATTLE_EVENT
        )

    def test_damage_is_battle_event(self) -> None:
        assert _classify("|-damage|p2a: Togekiss|50/100") == RoomPayloadKind.BATTLE_EVENT

    def test_display_only_types_are_still_battle_events(self) -> None:
        assert _classify("|upkeep") == RoomPayloadKind.BATTLE_EVENT
        assert _classify("|-anim|p1a: Garchomp|Earthquake|p2a: Togekiss") == (
            RoomPayloadKind.BATTLE_EVENT
        )


class TestRoomControlAndChat:
    def test_title_is_room_control_or_chat(self) -> None:
        assert _classify("|title|Ash vs. Misty") == RoomPayloadKind.ROOM_CONTROL_OR_CHAT

    def test_join_variants_are_room_control_or_chat(self) -> None:
        for tag in ("join", "j", "J"):
            assert _classify(f"|{tag}|ash") == RoomPayloadKind.ROOM_CONTROL_OR_CHAT

    def test_leave_variants_are_room_control_or_chat(self) -> None:
        for tag in ("leave", "l", "L"):
            assert _classify(f"|{tag}|ash") == RoomPayloadKind.ROOM_CONTROL_OR_CHAT

    def test_chat_variants_are_room_control_or_chat(self) -> None:
        for tag in ("chat", "c", "c:", ":"):
            assert _classify(f"|{tag}|1234|ash|hello") == RoomPayloadKind.ROOM_CONTROL_OR_CHAT

    def test_html_variants_are_room_control_or_chat(self) -> None:
        for tag in ("html", "uhtml", "uhtmlchange", "notify"):
            assert _classify(f"|{tag}|box|<b>hi</b>") == RoomPayloadKind.ROOM_CONTROL_OR_CHAT

    def test_battle_room_hints_are_room_control_or_chat(self) -> None:
        assert _classify("|b|battle-gen9ou-1|ash|misty") == RoomPayloadKind.ROOM_CONTROL_OR_CHAT
        assert _classify("|B|battle-gen9ou-1|ash|misty") == RoomPayloadKind.ROOM_CONTROL_OR_CHAT

    def test_bx_is_not_a_room_hint_and_is_unknown(self) -> None:
        assert _classify("|Bx|battle-gen9ou-1|ash|misty") == RoomPayloadKind.UNKNOWN

    def test_chat_with_embedded_request_is_not_split(self) -> None:
        payload = "|c:|1700000000|ash|check this |request|{}"
        result = classify_room_payload(payload)
        assert result.kind == RoomPayloadKind.ROOM_CONTROL_OR_CHAT
        assert result.payload == payload


class TestUnknown:
    def test_unrecognized_room_scoped_type_is_unknown(self) -> None:
        assert _classify("|totally-not-a-real-type|x") == RoomPayloadKind.UNKNOWN


class TestOrderedSequence:
    def test_full_sequence_classified_correctly(self) -> None:
        sequence = [
            ("|title|Ash vs. Misty", RoomPayloadKind.ROOM_CONTROL_OR_CHAT),
            ("|J|ash", RoomPayloadKind.ROOM_CONTROL_OR_CHAT),
            (
                "|c:|1700000000|ash|gl hf, my |request| is good",
                RoomPayloadKind.ROOM_CONTROL_OR_CHAT,
            ),
            ("|move|p1a: Garchomp|Earthquake|p2a: Togekiss", RoomPayloadKind.BATTLE_EVENT),
            ('|request|{"active":[]}', RoomPayloadKind.DECISION_REQUEST),
            ("|L|ash", RoomPayloadKind.ROOM_CONTROL_OR_CHAT),
        ]
        results = [classify_room_payload(payload).kind for payload, _ in sequence]
        assert results == [expected for _, expected in sequence]


class TestClassifiedRoomPayloadShape:
    def test_returns_dataclass_with_payload_preserved(self) -> None:
        result = classify_room_payload("|turn|5")
        assert isinstance(result, ClassifiedRoomPayload)
        assert result.payload == "|turn|5"
        assert result.kind == RoomPayloadKind.BATTLE_EVENT


class TestFrameIntegration:
    def test_battle_room_multiplex_fixture_decodes_and_classifies_in_order(self) -> None:
        fixture = (_FRAMES_DIR / "battle-room-multiplex.txt").read_text(encoding="utf-8")
        room_lines = decode_frame(fixture)
        assert all(line.room_id == "battle-gen9ou-1" for line in room_lines)
        kinds = [classify_room_payload(line.payload).kind for line in room_lines]
        assert kinds == [
            RoomPayloadKind.ROOM_CONTROL_OR_CHAT,  # title
            RoomPayloadKind.ROOM_CONTROL_OR_CHAT,  # J
            RoomPayloadKind.ROOM_CONTROL_OR_CHAT,  # c: with embedded |request|
            RoomPayloadKind.BATTLE_EVENT,  # move
            RoomPayloadKind.DECISION_REQUEST,  # real request
            RoomPayloadKind.ROOM_CONTROL_OR_CHAT,  # L
        ]

    def test_chat_room_control_does_not_reach_battle_or_request_parsing(self) -> None:
        fixture = (_FRAMES_DIR / "battle-room-multiplex.txt").read_text(encoding="utf-8")
        room_lines = decode_frame(fixture)
        battle_and_request_payloads = [
            line.payload
            for line in room_lines
            if classify_room_payload(line.payload).kind
            in (RoomPayloadKind.BATTLE_EVENT, RoomPayloadKind.DECISION_REQUEST)
        ]
        assert battle_and_request_payloads == [
            "|move|p1a: Garchomp|Earthquake|p2a: Togekiss",
            '|request|{"active":[{"moves":[]}]}',
        ]
