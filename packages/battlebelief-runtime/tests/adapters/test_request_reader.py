from __future__ import annotations

import json
from pathlib import Path

import pytest

from battlebelief_core.domain.actions.decision_request import RequestKind
from battlebelief_core.domain.actions.submission import ActionKind, ActionProvenance
from battlebelief_runtime.adapters.showdown_protocol.request_reader import read_request
from battlebelief_runtime.errors.protocol import MalformedProtocolMessage

_REPO_ROOT = Path(__file__).resolve().parents[4]
_REQUESTS_DIR = _REPO_ROOT / "tests" / "fixtures" / "requests"
_ROOM = "battle-gen9ou-1"


def _load(name: str) -> str:
    return (_REQUESTS_DIR / name).read_text(encoding="utf-8")


class TestWait:
    def test_wait_is_empty(self) -> None:
        dr = read_request(_ROOM, _load("wait.json"))
        assert dr.kind == RequestKind.WAIT
        assert dr.safe_submissions.submissions == ()
        assert dr.active_identity is None


class TestTeamPreview:
    def test_team_preview_has_720_permutations_plus_default(self) -> None:
        dr = read_request(_ROOM, _load("team-preview.json"))
        assert dr.kind == RequestKind.TEAM_PREVIEW
        subs = dr.safe_submissions.submissions
        assert len(subs) == 721  # 6! + default
        assert subs[-1].kind == ActionKind.DEFAULT
        team_subs = [s for s in subs if s.kind == ActionKind.TEAM]
        assert len(team_subs) == 720
        assert len({s.team_order for s in team_subs}) == 720  # all unique

    def test_natural_order_permutation_is_first(self) -> None:
        dr = read_request(_ROOM, _load("team-preview.json"))
        first = dr.safe_submissions.submissions[0]
        assert first.kind == ActionKind.TEAM
        assert first.team_order == (1, 2, 3, 4, 5, 6)

    def test_team_preview_active_identity_is_none(self) -> None:
        dr = read_request(_ROOM, _load("team-preview.json"))
        assert dr.active_identity is None


class TestForcedSwitch:
    def test_forced_switch_offers_alive_inactive_slots_and_default(self) -> None:
        dr = read_request(_ROOM, _load("forced-switch.json"))
        assert dr.kind == RequestKind.FORCED_SWITCH
        subs = dr.safe_submissions.submissions
        switch_slots = {s.slot for s in subs if s.kind == ActionKind.SWITCH}
        assert switch_slots == {2}  # Rotom only; Togekiss is fainted
        assert subs[-1].kind == ActionKind.DEFAULT


class TestRevival:
    def test_revival_detected_from_active_reviving_flag(self) -> None:
        dr = read_request(_ROOM, _load("reviving.json"))
        assert dr.kind == RequestKind.REVIVAL

    def test_revival_offers_only_fainted_inactive_slots(self) -> None:
        dr = read_request(_ROOM, _load("reviving.json"))
        subs = dr.safe_submissions.submissions
        revive_slots = {s.slot for s in subs if s.kind == ActionKind.REVIVE}
        # Garchomp (slot 1) is fainted but active -> excluded.
        # Rotom (slot 2) is alive -> excluded.
        # Togekiss (slot 3) is fainted and inactive -> the only valid target.
        assert revive_slots == {3}
        assert subs[-1].kind == ActionKind.DEFAULT

    def test_revive_submissions_are_explicit_request(self) -> None:
        dr = read_request(_ROOM, _load("reviving.json"))
        revives = [s for s in dr.safe_submissions.submissions if s.kind == ActionKind.REVIVE]
        assert all(s.provenance == ActionProvenance.EXPLICIT_REQUEST for s in revives)


class TestNormalMove:
    def test_disabled_moves_are_excluded(self) -> None:
        dr = read_request(_ROOM, _load("move.json"))
        assert dr.kind == RequestKind.MOVE
        move_ids = {s.move_id for s in dr.safe_submissions.submissions if s.kind == ActionKind.MOVE}
        assert "stoneedge" not in move_ids
        assert "earthquake" in move_ids

    def test_move_includes_switches_and_default(self) -> None:
        dr = read_request(_ROOM, _load("move.json"))
        subs = dr.safe_submissions.submissions
        assert any(s.kind == ActionKind.SWITCH for s in subs)
        assert subs[-1].kind == ActionKind.DEFAULT

    def test_active_identity_is_nickname_of_active_pokemon(self) -> None:
        dr = read_request(_ROOM, _load("move.json"))
        assert dr.active_identity == "Garchomp"


class TestTeraField:
    def test_can_terastallize_is_a_string_not_bool(self) -> None:
        raw = json.loads(_load("move-tera.json"))
        assert isinstance(raw["active"][0]["canTerastallize"], str)

    def test_tera_variant_generated_per_move(self) -> None:
        dr = read_request(_ROOM, _load("move-tera.json"))
        tera_subs = [s for s in dr.safe_submissions.submissions if s.terastallize]
        normal_subs = [
            s
            for s in dr.safe_submissions.submissions
            if s.kind == ActionKind.MOVE and not s.terastallize
        ]
        assert len(tera_subs) == 1
        assert len(normal_subs) == 1
        assert tera_subs[0].move_id == normal_subs[0].move_id == "earthquake"

    def test_empty_can_terastallize_generates_no_tera_variant(self) -> None:
        dr = read_request(_ROOM, _load("move.json"))
        assert not any(s.terastallize for s in dr.safe_submissions.submissions)


class TestMaybeTrappedAndMaybeDisabled:
    def test_maybe_trapped_removes_switches(self) -> None:
        dr = read_request(_ROOM, _load("maybe-trapped.json"))
        assert not any(s.kind == ActionKind.SWITCH for s in dr.safe_submissions.submissions)
        assert any(s.kind == ActionKind.MOVE for s in dr.safe_submissions.submissions)

    def test_maybe_disabled_yields_only_default(self) -> None:
        raw = json.loads(_load("move.json"))
        raw["active"][0]["maybeDisabled"] = True
        dr = read_request(_ROOM, json.dumps(raw))
        assert len(dr.safe_submissions.submissions) == 1
        assert dr.safe_submissions.submissions[0].kind == ActionKind.DEFAULT

    def test_maybe_locked_yields_only_default(self) -> None:
        raw = json.loads(_load("move.json"))
        raw["active"][0]["maybeLocked"] = True
        dr = read_request(_ROOM, json.dumps(raw))
        assert len(dr.safe_submissions.submissions) == 1
        assert dr.safe_submissions.submissions[0].kind == ActionKind.DEFAULT


class TestRqidValidation:
    def test_missing_rqid_is_rejected(self) -> None:
        raw = json.loads(_load("wait.json"))
        del raw["rqid"]
        with pytest.raises(MalformedProtocolMessage):
            read_request(_ROOM, json.dumps(raw))

    def test_negative_rqid_is_rejected(self) -> None:
        raw = json.loads(_load("wait.json"))
        raw["rqid"] = -1
        with pytest.raises(MalformedProtocolMessage):
            read_request(_ROOM, json.dumps(raw))

    def test_string_rqid_is_rejected(self) -> None:
        raw = json.loads(_load("wait.json"))
        raw["rqid"] = "5"
        with pytest.raises(MalformedProtocolMessage):
            read_request(_ROOM, json.dumps(raw))


class TestDigestStability:
    def test_same_payload_yields_same_digest(self) -> None:
        dr1 = read_request(_ROOM, _load("move.json"))
        dr2 = read_request(_ROOM, _load("move.json"))
        assert dr1.identity.request_digest == dr2.identity.request_digest

    def test_different_payload_yields_different_digest(self) -> None:
        dr1 = read_request(_ROOM, _load("move.json"))
        dr2 = read_request(_ROOM, _load("wait.json"))
        assert dr1.identity.request_digest != dr2.identity.request_digest


class TestMalformedJson:
    def test_invalid_json_is_rejected(self) -> None:
        with pytest.raises(MalformedProtocolMessage):
            read_request(_ROOM, "{not valid json")

    def test_non_object_json_is_rejected(self) -> None:
        with pytest.raises(MalformedProtocolMessage):
            read_request(_ROOM, "[1, 2, 3]")
