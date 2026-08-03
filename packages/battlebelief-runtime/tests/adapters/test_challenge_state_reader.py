from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from battlebelief_runtime.adapters.showdown_protocol.challenge_state_reader import (
    ChallengeStateReader,
    OutgoingChallengeObservation,
    OutgoingChallengeStatus,
)
from battlebelief_runtime.errors.protocol import (
    MalformedProtocolMessage,
    UnknownProtocolEvent,
)


def _reader() -> ChallengeStateReader:
    return ChallengeStateReader(
        our_user_id="+Our User",
        target_user_id="@Target User",
    )


def _state_fields(observation: OutgoingChallengeObservation) -> tuple[object, ...]:
    return (
        observation.status,
        observation.target_user_id,
        observation.format_id,
    )


def test_reader_module_exposes_the_required_public_api() -> None:
    assert OutgoingChallengeStatus.PENDING == "pending"
    assert OutgoingChallengeStatus.NOT_PENDING == "not_pending"


def test_reader_rejects_formats_outside_the_fixed_m1_scope() -> None:
    with pytest.raises(ValueError, match="gen9ou"):
        ChallengeStateReader(
            our_user_id="Our User",
            target_user_id="Target User",
            format_id="gen8ou",
        )


@pytest.mark.parametrize(
    ("our_user_id", "target_user_id", "invalid_field"),
    (
        pytest.param("!@#$", "Target User", "our_user_id", id="punctuation-only-our-id"),
        pytest.param(
            "Our User",
            "\u65e5\u672c",
            "target_user_id",
            id="non-ascii-only-target-id",
        ),
    ),
)
def test_reader_rejects_user_ids_that_normalize_to_empty(
    our_user_id: str,
    target_user_id: str,
    invalid_field: str,
) -> None:
    with pytest.raises(ValueError, match=invalid_field):
        ChallengeStateReader(
            our_user_id=our_user_id,
            target_user_id=target_user_id,
        )


def test_reader_allows_equal_normalized_user_ids() -> None:
    reader = ChallengeStateReader(
        our_user_id="+Same User",
        target_user_id="@Same User",
    )

    observation = reader.read(
        '|updatechallenges|{"challengeTo":{"to":"Same User","format":"gen9ou"}}'
    )

    assert observation == OutgoingChallengeObservation(
        status=OutgoingChallengeStatus.PENDING,
        target_user_id="sameuser",
        format_id="gen9ou",
        source_kind="updatechallenges",
    )


class TestOutgoingChallengeObservation:
    def test_observations_are_frozen_and_slotted(self) -> None:
        observation = OutgoingChallengeObservation(
            status=OutgoingChallengeStatus.PENDING,
            target_user_id="targetuser",
            format_id="gen9ou",
            source_kind="updatechallenges",
        )

        with pytest.raises(FrozenInstanceError):
            observation.status = OutgoingChallengeStatus.NOT_PENDING

        assert not hasattr(observation, "__dict__")


class TestUpdateChallengesJson:
    def test_pending_challenge_normalizes_ranked_ascii_identities(self) -> None:
        observation = _reader().read(
            '|updatechallenges|{"challengeTo":{"to":"%Target User","format":"gen9ou"}}'
        )

        assert observation == OutgoingChallengeObservation(
            status=OutgoingChallengeStatus.PENDING,
            target_user_id="targetuser",
            format_id="gen9ou",
            source_kind="updatechallenges",
        )

    def test_kelvin_sign_wire_display_matches_ascii_k_context_target(self) -> None:
        reader = ChallengeStateReader(
            our_user_id="Our User",
            target_user_id="KTarget User",
        )

        observation = reader.read(
            '|updatechallenges|{"challengeTo":{"to":"\u212aTarget User","format":"gen9ou"}}'
        )

        assert observation == OutgoingChallengeObservation(
            status=OutgoingChallengeStatus.PENDING,
            target_user_id="ktargetuser",
            format_id="gen9ou",
            source_kind="updatechallenges",
        )

    def test_mixed_kelvin_sign_normalizes_to_ascii_k(self) -> None:
        payload = '|updatechallenges|{"challengeTo":{"to":"Misty\u212a","format":"gen9ou"}}'

        accepted = ChallengeStateReader(
            our_user_id="Our User",
            target_user_id="MistyK",
        ).read(payload)

        assert accepted is not None
        assert accepted.target_user_id == "mistyk"
        with pytest.raises(UnknownProtocolEvent):
            ChallengeStateReader(
                our_user_id="Our User",
                target_user_id="Misty",
            ).read(payload)

    @pytest.mark.parametrize(
        "payload",
        (
            '|updatechallenges|{"challengeTo":null}',
            "|updatechallenges|{}",
        ),
    )
    def test_null_or_missing_challenge_to_is_not_pending(self, payload: str) -> None:
        observation = _reader().read(payload)

        assert observation == OutgoingChallengeObservation(
            status=OutgoingChallengeStatus.NOT_PENDING,
            target_user_id="targetuser",
            format_id=None,
            source_kind="updatechallenges",
        )

    @pytest.mark.parametrize(
        "payload",
        (
            "|updatechallenges|{not-json}",
            "|updatechallenges|[]",
            '|updatechallenges|{"challengeTo":[]}',
            '|updatechallenges|{"challengeTo":{"to":1,"format":"gen9ou"}}',
            '|updatechallenges|{"challengeTo":{"to":"Target User","format":null}}',
        ),
    )
    def test_malformed_json_or_field_types_are_rejected(self, payload: str) -> None:
        with pytest.raises(MalformedProtocolMessage):
            _reader().read(payload)

    @pytest.mark.parametrize(
        "payload",
        (
            '|updatechallenges|{"challengeTo":{"to":"Other User","format":"gen9ou"}}',
            '|updatechallenges|{"challengeTo":{"to":"Target User","format":"gen8ou"}}',
        ),
    )
    def test_wrong_target_or_format_is_rejected_fail_closed(self, payload: str) -> None:
        with pytest.raises(UnknownProtocolEvent):
            _reader().read(payload)


class TestChallengePrivateMessages:
    def test_outgoing_pending_pm_has_exact_expected_fields(self) -> None:
        observation = _reader().read(
            "|pm|+Our User|@Target User|/challenge gen9ou|gen9ou|Challenge message|accept|reject"
        )

        assert observation == OutgoingChallengeObservation(
            status=OutgoingChallengeStatus.PENDING,
            target_user_id="targetuser",
            format_id="gen9ou",
            source_kind="pm",
        )

    def test_incoming_pending_challenge_is_not_an_outgoing_state(self) -> None:
        assert (
            _reader().read(
                "|pm|@Target User|+Our User|/challenge gen9ou|gen9ou|Challenge message|accept|reject"
            )
            is None
        )

    @pytest.mark.parametrize(
        "payload",
        (
            "|pm|Brock|+Our User|/challenge gen9ou|gen9ou|Challenge message|accept|reject",
            "|pm|+Our User|Brock|/challenge gen9ou|gen9ou|Challenge message|accept|reject",
            "|pm|Brock|+Our User|/challenge",
            "|pm|+Our User|Brock|/challenge",
            "|pm|Brock|+Our User|/challenge malformed",
        ),
    )
    def test_foreign_challenge_state_pms_are_ignored(self, payload: str) -> None:
        assert _reader().read(payload) is None

    @pytest.mark.parametrize(
        "payload",
        (
            "|pm|+Our User|@Target User|/challenge",
            "|pm|@Target User|+Our User|/challenge",
        ),
    )
    def test_not_pending_pm_accepts_both_participant_orientations(self, payload: str) -> None:
        observation = _reader().read(payload)

        assert observation == OutgoingChallengeObservation(
            status=OutgoingChallengeStatus.NOT_PENDING,
            target_user_id="targetuser",
            format_id=None,
            source_kind="pm",
        )

    def test_ordinary_pm_chat_containing_challenge_is_ignored(self) -> None:
        assert (
            _reader().read("|pm|@Target User|+Our User|I saw /challenge gen9ou in another room")
            is None
        )

    @pytest.mark.parametrize(
        "payload",
        ("|pm|+Our User|@Target User|/challenge gen8ou|gen8ou|Challenge message|accept|reject",),
    )
    def test_wrong_pending_pm_target_or_format_is_rejected_fail_closed(self, payload: str) -> None:
        with pytest.raises(UnknownProtocolEvent):
            _reader().read(payload)

    @pytest.mark.parametrize(
        "payload",
        (
            "|pm|+Our User|@Target User|/challenge gen9ou",
            "|pm|+Our User|@Target User|/challenge gen9ou|gen9ou|Challenge message|accept",
            "|pm|+Our User|@Target User|/challenge gen9ou|gen9ou|Challenge message|accept|reject|extra",
            "|pm|+Our User|@Target User|/challenge|extra",
        ),
    )
    def test_insufficient_or_extra_challenge_state_fields_are_rejected(self, payload: str) -> None:
        with pytest.raises(MalformedProtocolMessage):
            _reader().read(payload)


class TestEquivalentStateSemantics:
    def test_json_and_pm_pending_have_equivalent_state_fields(self) -> None:
        reader = _reader()
        json_observation = reader.read(
            '|updatechallenges|{"challengeTo":{"to":"Target User","format":"gen9ou"}}'
        )
        pm_observation = reader.read(
            "|pm|+Our User|@Target User|/challenge gen9ou|gen9ou|Challenge message|accept|reject"
        )

        assert _state_fields(json_observation) == _state_fields(pm_observation)
        assert json_observation.source_kind == "updatechallenges"
        assert pm_observation.source_kind == "pm"

    def test_json_and_pm_not_pending_have_equivalent_state_fields(self) -> None:
        reader = _reader()
        json_observation = reader.read('|updatechallenges|{"challengeTo":null}')
        pm_observation = reader.read("|pm|@Target User|+Our User|/challenge")

        assert _state_fields(json_observation) == _state_fields(pm_observation)
        assert json_observation.source_kind == "updatechallenges"
        assert pm_observation.source_kind == "pm"


def test_unrelated_known_global_payloads_are_ignored() -> None:
    reader = _reader()

    assert reader.read("|updateuser|Our User|1|0") is None
    assert reader.read("|challstr|1|challenge") is None
