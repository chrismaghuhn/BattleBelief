"""Strict protocol tests for the local Showdown stdio oracle."""

from __future__ import annotations

import pytest

from battlebelief_lab.oracle.showdown.errors import OracleFailureClass
from battlebelief_lab.oracle.showdown.protocol import (
    EndMessage,
    OracleProtocolError,
    ShowdownProtocolDecoder,
    SideErrorMessage,
    SideUpdateMessage,
    UpdateMessage,
    encode_commands,
)


def _error_class(error: pytest.ExceptionInfo[OracleProtocolError]) -> OracleFailureClass:
    return error.value.failure_class


def test_decoder_accepts_partial_chunks_and_multiple_frames() -> None:
    decoder = ShowdownProtocolDecoder(max_frame_bytes=256, max_buffer_bytes=512)

    assert decoder.feed(b"upd") == ()
    messages = decoder.feed(
        b'ate\n|turn|1\n|move|p1a: A|Tackle|p2a: B\n\nsideupdate\np1\n|request|{"wait":true}\n\n'
    )
    final_messages = decoder.feed(b'end\n{"winner":"A","turns":1}\n\n')
    decoder.finish()

    assert messages == (
        UpdateMessage(lines=("|turn|1", "|move|p1a: A|Tackle|p2a: B")),
        SideUpdateMessage(
            side="p1", lines=('|request|{"wait":true}',), request_json=b'{"wait":true}'
        ),
    )
    assert final_messages == (EndMessage(log_json=b'{"turns":1,"winner":"A"}'),)


def test_decoder_rejects_incomplete_frame_at_finish() -> None:
    decoder = ShowdownProtocolDecoder()
    decoder.feed(b"update\n|turn|1")

    with pytest.raises(OracleProtocolError) as error:
        decoder.finish()

    assert _error_class(error) is OracleFailureClass.PROTOCOL_DESYNCHRONIZATION


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (b"update\n|turn|\xff\n\n", OracleFailureClass.MALFORMED_OUTPUT),
        (b'sideupdate\np1\n|request|{"x":1,"x":2}\n\n', OracleFailureClass.MALFORMED_OUTPUT),
        (b'sideupdate\np1\n|request|{"x":NaN}\n\n', OracleFailureClass.MALFORMED_OUTPUT),
        (b'sideupdate\np1\n|request|{"x":Infinity}\n\n', OracleFailureClass.MALFORMED_OUTPUT),
        (
            b'sideupdate\np1\n|request|"not-an-object"\n\n',
            OracleFailureClass.PROTOCOL_DESYNCHRONIZATION,
        ),
        (b"mystery\n|turn|1\n\n", OracleFailureClass.PROTOCOL_DESYNCHRONIZATION),
        (b"\n\n", OracleFailureClass.PROTOCOL_DESYNCHRONIZATION),
        (b"update\r\n|turn|1\n\n", OracleFailureClass.MALFORMED_OUTPUT),
    ],
)
def test_decoder_rejects_malformed_or_unknown_frames(
    payload: bytes, expected: OracleFailureClass
) -> None:
    decoder = ShowdownProtocolDecoder()
    if payload.startswith(b"sideupdate"):
        decoder.feed(b"update\n|start\n\n")

    with pytest.raises(OracleProtocolError) as error:
        decoder.feed(payload)

    assert _error_class(error) is expected


def test_decoder_accepts_request_object_and_null() -> None:
    decoder = ShowdownProtocolDecoder()
    decoder.feed(b"update\n|start\n\n")

    object_message = decoder.feed(b'sideupdate\np1\n|request|{"active":[]}\n\n')
    null_message = decoder.feed(b"sideupdate\np2\n|request|null\n\n")
    decoder.feed(b"end\n{}\n\n")
    decoder.finish()

    assert object_message == (
        SideUpdateMessage(
            side="p1", lines=('|request|{"active":[]}',), request_json=b'{"active":[]}'
        ),
    )
    assert null_message == (
        SideUpdateMessage(side="p2", lines=("|request|null",), request_json=b"null"),
    )


def test_semantically_equal_requests_have_identical_messages() -> None:
    first = ShowdownProtocolDecoder()
    second = ShowdownProtocolDecoder()
    first.feed(b"update\n|start\n\n")
    second.feed(b"update\n|start\n\n")

    first_message = first.feed(b'sideupdate\np1\n|request|{ "wait": true, "active": [] }\n\n')
    second_message = second.feed(b'sideupdate\np1\n|request|{"active":[],"wait":true}\n\n')

    assert (
        first_message
        == second_message
        == (
            SideUpdateMessage(
                side="p1",
                lines=('|request|{"active":[],"wait":true}',),
                request_json=b'{"active":[],"wait":true}',
            ),
        )
    )


@pytest.mark.parametrize("log_json", [b"null", b"[]", b'"winner"', b"1"])
def test_decoder_requires_end_json_object(log_json: bytes) -> None:
    decoder = ShowdownProtocolDecoder()
    decoder.feed(b"update\n|start\n\n")

    with pytest.raises(OracleProtocolError) as error:
        decoder.feed(b"end\n" + log_json + b"\n\n")

    assert _error_class(error) is OracleFailureClass.PROTOCOL_DESYNCHRONIZATION


def test_decoder_classifies_ruleset_error_lines() -> None:
    decoder = ShowdownProtocolDecoder()

    with pytest.raises(OracleProtocolError) as error:
        decoder.feed(b"update\n|error|Unrecognized format gen9ou-invalid\n\n")

    assert _error_class(error) is OracleFailureClass.RULESET_REJECTED


def test_decoder_accepts_first_side_error_then_normal_battle_messages() -> None:
    decoder = ShowdownProtocolDecoder()

    error_message = decoder.feed(b"sideupdate\np1\n|error|[Invalid choice] Can't move\n\n")
    update_message = decoder.feed(b"update\n|start\n\n")
    request_message = decoder.feed(b"sideupdate\np1\n|request|{}\n\n")
    decoder.feed(b"end\n{}\n\n")
    decoder.finish()

    assert error_message == (
        SideErrorMessage(side="p1", line="|error|[Invalid choice] Can't move"),
    )
    assert update_message == (UpdateMessage(lines=("|start",)),)
    assert request_message == (
        SideUpdateMessage(side="p1", lines=("|request|{}",), request_json=b"{}"),
    )


def test_decoder_failure_is_terminal() -> None:
    decoder = ShowdownProtocolDecoder()
    decoder.feed(b"update\n|start\n\n")
    with pytest.raises(OracleProtocolError):
        decoder.feed(b'sideupdate\np1\n|request|{"x":1,"x":2}\n\n')

    with pytest.raises(OracleProtocolError) as error:
        decoder.feed(b"sideupdate\np1\n|request|{}\n\n")

    assert _error_class(error) is OracleFailureClass.PROTOCOL_DESYNCHRONIZATION


def test_decoder_drops_only_exact_integer_timestamp_lines() -> None:
    decoder = ShowdownProtocolDecoder()
    messages = decoder.feed(
        b"update\n|t:|1720000000\n|t:|not-an-integer\n|-message|keep |t:|1720000000\n|turn|1\n\n"
    )
    decoder.feed(b"end\n{}\n\n")
    decoder.finish()

    assert messages == (
        UpdateMessage(
            lines=(
                "|t:|not-an-integer",
                "|-message|keep |t:|1720000000",
                "|turn|1",
            )
        ),
    )


def test_decoder_rejects_frame_larger_than_limit() -> None:
    decoder = ShowdownProtocolDecoder(max_frame_bytes=12, max_buffer_bytes=64)

    with pytest.raises(OracleProtocolError) as error:
        decoder.feed(b"update\n|turn|123\n\n")

    assert _error_class(error) is OracleFailureClass.OUTPUT_TOO_LARGE


def test_decoder_rejects_unterminated_buffer_larger_than_limit() -> None:
    decoder = ShowdownProtocolDecoder(max_frame_bytes=64, max_buffer_bytes=8)

    with pytest.raises(OracleProtocolError) as error:
        decoder.feed(b"update\n|t")

    assert _error_class(error) is OracleFailureClass.OUTPUT_TOO_LARGE


@pytest.mark.parametrize(
    "payload",
    [
        b"sideupdate\np1\n|request|{}\n\n",
        b"end\n{}\n\n",
    ],
)
def test_decoder_requires_initial_update(payload: bytes) -> None:
    decoder = ShowdownProtocolDecoder()

    with pytest.raises(OracleProtocolError) as error:
        decoder.feed(payload)

    assert _error_class(error) is OracleFailureClass.PROTOCOL_DESYNCHRONIZATION


def test_decoder_rejects_output_after_end() -> None:
    decoder = ShowdownProtocolDecoder()
    decoder.feed(b"update\n|start\n\nend\n{}\n\n")

    with pytest.raises(OracleProtocolError) as error:
        decoder.feed(b"update\n|turn|2\n\n")

    assert _error_class(error) is OracleFailureClass.PROTOCOL_DESYNCHRONIZATION


def test_decoder_finish_requires_end_frame() -> None:
    decoder = ShowdownProtocolDecoder()
    decoder.feed(b"update\n|start\n\n")

    with pytest.raises(OracleProtocolError) as error:
        decoder.finish()

    assert _error_class(error) is OracleFailureClass.PROTOCOL_DESYNCHRONIZATION


@pytest.mark.parametrize(
    "payload",
    [
        b"sideupdate\np3\n|request|{}\n\n",
        b"sideupdate\np5\n|request|{}\n\n",
        b"sideupdate\np1\n|not-request|{}\n\n",
        b"sideupdate\np1\n|request|{}\n|request|null\n\n",
        b"sideupdate\np1\n|error|[Invalid choice] Bad\n|request|{}\n\n",
        b"update\nturn|1\n\n",
        b"end\n{}\nextra\n\n",
    ],
)
def test_decoder_rejects_desynchronized_frame_shapes(payload: bytes) -> None:
    decoder = ShowdownProtocolDecoder()
    decoder.feed(b"update\n|start\n\n")

    with pytest.raises(OracleProtocolError) as error:
        decoder.feed(payload)

    assert _error_class(error) is OracleFailureClass.PROTOCOL_DESYNCHRONIZATION


def test_command_encoder_emits_exact_utf8_newline_delimited_bytes() -> None:
    assert encode_commands((">start {}", ">p1 move Flambirex")) == (
        b">start {}\n>p1 move Flambirex\n"
    )


@pytest.mark.parametrize(
    "command",
    [
        "",
        "not-a-command",
        ">p1 move 1\r",
        ">p1 move 1\n>p2 move 1",
        ">p1 move 1\x00",
    ],
)
def test_command_encoder_rejects_invalid_commands(command: str) -> None:
    with pytest.raises(OracleProtocolError) as error:
        encode_commands((command,))

    assert _error_class(error) is OracleFailureClass.PROTOCOL_DESYNCHRONIZATION


def test_command_encoder_rejects_oversized_command_or_total_input() -> None:
    with pytest.raises(OracleProtocolError) as command_error:
        encode_commands((">1234",), max_command_bytes=4)
    with pytest.raises(OracleProtocolError) as total_error:
        encode_commands((">12", ">34"), max_command_bytes=8, max_total_bytes=7)

    assert _error_class(command_error) is OracleFailureClass.INPUT_TOO_LARGE
    assert _error_class(total_error) is OracleFailureClass.INPUT_TOO_LARGE
