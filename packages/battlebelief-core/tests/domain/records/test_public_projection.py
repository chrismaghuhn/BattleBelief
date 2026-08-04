from __future__ import annotations

from dataclasses import replace

from battlebelief_core.domain.actions.submission import (
    ActionKind,
    ActionProvenance,
    BattleSubmission,
    RequestIdentity,
    SafeSubmissionSet,
)
from battlebelief_core.domain.events.evidence import VisibleEvidence
from battlebelief_core.domain.records.public_projection import (
    battle_submission_digest,
    canonical_public_bytes,
    observed_state_digest,
    project_observed_state,
    project_request_identity,
    project_safe_submission_set,
    request_identity_digest,
    safe_submission_set_digest,
)
from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_core.domain.state.pokemon_view import PokemonView

_DIGEST = "sha256:" + "a" * 64


def _identity(room_id: str = "battle-secret-room") -> RequestIdentity:
    return RequestIdentity(room_id=room_id, rqid=7, request_digest=_DIGEST)


def _move(slot: int) -> BattleSubmission:
    return BattleSubmission(
        kind=ActionKind.MOVE,
        provenance=ActionProvenance.EXPLICIT_REQUEST,
        slot=slot,
        move_id=f"move-{slot}",
    )


def test_request_projection_omits_raw_room_id_and_is_immutable() -> None:
    projection = project_request_identity(_identity())

    assert dict(projection) == {"rqid": 7, "request_digest": _DIGEST}
    assert "battle-secret-room" not in canonical_public_bytes(projection).decode()

    try:
        projection["rqid"] = 8  # type: ignore[index]
    except TypeError:
        pass
    else:
        raise AssertionError("public projections must be immutable")


def test_state_projection_removes_account_and_private_identity_fields() -> None:
    initial = ObservedState.initial("ash")
    state = replace(
        initial,
        p1=replace(
            initial.p1,
            user_id="ash",
            display_name="Ash",
        ),
        p2=replace(
            initial.p2,
            user_id="misty",
            display_name="Misty",
        ),
        our_side="p1",
        winner="misty",
        visible_evidence=(
            VisibleEvidence(
                event_index=4,
                kind="message",
                side_id="p2",
                slot=None,
                nickname="secret-opponent-nickname",
                effect=None,
                annotations=(),
            ),
        ),
    )

    projection = project_observed_state(state)
    encoded = canonical_public_bytes(projection)
    text = encoded.decode("utf-8")

    assert projection["winner"] == "opponent_side"
    assert projection["our_side"] == "p1"
    for forbidden in (
        "ash",
        "Ash",
        "misty",
        "Misty",
        "secret-opponent-nickname",
    ):
        assert forbidden not in text


def test_state_projection_redacts_transform_targets_and_raw_annotations() -> None:
    initial = ObservedState.initial("mrmime")
    transformed = PokemonView.new("p1", "Ditto", "Ditto, L50")
    transformed = replace(transformed, active=True, transform_target="SecretNickname")
    state = replace(
        initial,
        p1=replace(initial.p1, pokemon=(transformed,)),
        visible_evidence=(
            VisibleEvidence(
                event_index=1,
                kind="transform",
                side_id="p2",
                slot=1,
                nickname="SecretNickname",
                effect="SecretNickname",
                annotations=("[of] p2a: SecretNickname",),
            ),
        ),
    )

    encoded = canonical_public_bytes(project_observed_state(state)).decode("utf-8")

    assert "SecretNickname" not in encoded
    assert "transform_target" not in encoded
    assert '"annotations":[{"side_id":"p2","slot":1,"type":"of"}]' in encoded
    assert '"transformed":true' in encoded


def test_public_evidence_preserves_safe_hit_count_values() -> None:
    initial = ObservedState.initial("ash")
    two_hits = replace(
        initial,
        visible_evidence=(VisibleEvidence(1, "hitcount", "p2", 1, None, "2", ()),),
    )
    five_hits = replace(
        initial,
        visible_evidence=(VisibleEvidence(1, "hitcount", "p2", 1, None, "5", ()),),
    )

    assert observed_state_digest(two_hits) != observed_state_digest(five_hits)
    assert project_observed_state(two_hits)["visible_evidence"][0]["hit_count"] == 2


def test_submission_order_is_semantic_but_mapping_order_is_not() -> None:
    first = SafeSubmissionSet(request_identity=_identity(), submissions=(_move(1), _move(2)))
    second = SafeSubmissionSet(request_identity=_identity(), submissions=(_move(2), _move(1)))

    assert (
        project_safe_submission_set(first)["submissions"]
        != project_safe_submission_set(second)["submissions"]
    )
    assert safe_submission_set_digest(first) != safe_submission_set_digest(second)
    assert canonical_public_bytes({"b": 1, "a": 2}) == canonical_public_bytes({"a": 2, "b": 1})


def test_action_and_identity_digests_change_when_public_fields_change() -> None:
    identity = _identity()
    changed_identity = RequestIdentity(
        room_id=identity.room_id,
        rqid=identity.rqid + 1,
        request_digest=identity.request_digest,
    )
    assert request_identity_digest(identity) != request_identity_digest(changed_identity)
    assert battle_submission_digest(_move(1)) != battle_submission_digest(_move(2))


def test_same_priority_heuristic_choice_follows_submission_order() -> None:
    from battlebelief_core.application.decision.heuristic_policy import HeuristicPolicy
    from battlebelief_core.domain.actions.decision_request import DecisionRequest, RequestKind

    first, second = _move(1), _move(2)
    first_request = DecisionRequest(
        identity=_identity(),
        kind=RequestKind.MOVE,
        side_id="p1",
        team_member_count=6,
        active_identity="active",
        safe_submissions=SafeSubmissionSet(_identity(), (first, second)),
        is_update=False,
    )
    second_request = replace(
        first_request,
        safe_submissions=SafeSubmissionSet(_identity(), (second, first)),
    )

    assert HeuristicPolicy.select(first_request) == first
    assert HeuristicPolicy.select(second_request) == second


def test_each_observed_state_projection_dimension_is_digestable() -> None:
    from battlebelief_core.domain.records.public_projection import observed_state_digest

    initial = ObservedState.initial("ash")
    variants = [
        replace(initial, event_index=0),
        replace(initial, room_initialized=True),
        replace(initial, generation=9),
        replace(initial, game_type="singles"),
        replace(initial, tier="[Gen 9] OU"),
        replace(initial, rated=True),
        replace(initial, rules=("Sleep Clause Mod",)),
        replace(initial, turn=1),
        replace(initial, battle_started=True),
        replace(initial, team_preview_started=True),
        replace(initial, winner="ash"),
        replace(initial, tied=True),
        replace(initial, our_side="p1"),
        replace(initial, p1=replace(initial.p1, team_size=6)),
        replace(initial, p2=replace(initial.p2, active_slot=1)),
        replace(initial, weather="RainDance"),
        replace(initial, field_conditions=("electricterrain",)),
        replace(
            initial,
            visible_evidence=(VisibleEvidence(0, "message", "p1", None, None, "effect", ("a",)),),
        ),
        replace(initial, ignored_display_count=1),
    ]

    digests = {observed_state_digest(value) for value in variants}
    assert len(digests) == len(variants)


def test_winner_projection_uses_showdown_identifier_normalization() -> None:
    initial = ObservedState.initial("mrmime")
    state = replace(
        initial,
        p1=replace(initial.p1, user_id="mrmime"),
        p2=replace(initial.p2, user_id="mistywaterflower"),
        winner="Mr. Mime",
    )

    assert project_observed_state(state)["winner"] == "our_side"

    opponent_state = replace(state, winner="Misty Waterflower")
    assert project_observed_state(opponent_state)["winner"] == "opponent_side"

    assert project_observed_state(replace(state, winner="unknown winner"))["winner"] is None
