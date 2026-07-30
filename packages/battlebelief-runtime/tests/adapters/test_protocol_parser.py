from __future__ import annotations

import pytest

from battlebelief_core.domain.events.evidence import VisibleEvidence
from battlebelief_core.domain.events.field import SideConditionChanged, WeatherChanged
from battlebelief_core.domain.events.ignored import IgnoredDisplayEvent
from battlebelief_core.domain.events.metadata import (
    BattleRated,
    GameTypeDeclared,
    GenerationDeclared,
    PlayerDeclared,
    PreviewPokemonDeclared,
    RuleDeclared,
    TeamSizeDeclared,
    TierDeclared,
)
from battlebelief_core.domain.events.pokemon import (
    AbilityChanged,
    BoostChanged,
    ItemChanged,
    PokemonSwitched,
    Terastallized,
    VolatileChanged,
)
from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_runtime.adapters.showdown_protocol.parser import (
    parse_battle_line,
    parse_inactive_line,
)
from battlebelief_runtime.errors.protocol import MalformedProtocolMessage, UnknownProtocolEvent


class TestNoOps:
    """player, teamsize, poke, tera, item, ability, boost, volatile, field,
    and side condition must not be treated as no-ops."""

    def test_player_is_not_a_noop(self) -> None:
        ev = parse_battle_line("|player|p1|ash|1|", 0)
        assert isinstance(ev, PlayerDeclared)
        assert ev.side_id == "p1"

    def test_teamsize_is_not_a_noop(self) -> None:
        ev = parse_battle_line("|teamsize|p1|6", 0)
        assert isinstance(ev, TeamSizeDeclared)
        assert ev.size == 6

    def test_poke_is_not_a_noop(self) -> None:
        ev = parse_battle_line("|poke|p1|Garchomp, L50, M|item", 0)
        assert isinstance(ev, PreviewPokemonDeclared)
        assert ev.has_item is True

    def test_terastallize_is_not_a_noop(self) -> None:
        ev = parse_battle_line("|-terastallize|p1a: Garchomp|Ground", 0)
        assert isinstance(ev, Terastallized)
        assert ev.tera_type == "Ground"

    def test_item_is_not_a_noop(self) -> None:
        ev = parse_battle_line("|-item|p1a: Garchomp|Rocky Helmet", 0)
        assert isinstance(ev, ItemChanged)
        assert ev.action == "set"

    def test_ability_is_not_a_noop(self) -> None:
        ev = parse_battle_line("|-ability|p1a: Garchomp|Rough Skin", 0)
        assert isinstance(ev, AbilityChanged)
        assert ev.action == "set"

    def test_boost_is_not_a_noop(self) -> None:
        ev = parse_battle_line("|-boost|p1a: Garchomp|atk|1", 0)
        assert isinstance(ev, BoostChanged)
        assert ev.amount == 1

    def test_volatile_is_not_a_noop(self) -> None:
        ev = parse_battle_line("|-start|p1a: Garchomp|confusion", 0)
        assert isinstance(ev, VolatileChanged)
        assert ev.action == "start"

    def test_field_is_not_a_noop(self) -> None:
        ev = parse_battle_line("|-weather|SunnyDay", 0)
        assert isinstance(ev, WeatherChanged)
        assert ev.weather == "SunnyDay"

    def test_side_condition_is_not_a_noop(self) -> None:
        ev = parse_battle_line("|-sidestart|p1|Stealth Rock", 0)
        assert isinstance(ev, SideConditionChanged)
        assert ev.side_id == "p1"


class TestSwitchAndReduce:
    def test_switch_carries_full_details_and_reduces(self) -> None:
        ev = parse_battle_line("|switch|p1a: Garchomp|Garchomp, L50, M|183/183", 0)
        assert isinstance(ev, PokemonSwitched)
        assert ev.side_id == "p1"
        assert ev.slot == 1
        assert ev.nickname == "Garchomp"
        assert ev.details == "Garchomp, L50, M"
        assert ev.hp.current == 183
        assert ev.hp.maximum == 183


class TestEvidence:
    def test_crit_is_visible_evidence(self) -> None:
        ev = parse_battle_line("|-crit|p2a: Togekiss", 0)
        assert isinstance(ev, VisibleEvidence)
        assert ev.kind == "crit"
        assert ev.side_id == "p2"

    def test_anim_is_ignored_display_noop(self) -> None:
        ev = parse_battle_line("|-anim|p1a: Garchomp|Earthquake|p2a: Togekiss", 0)
        assert isinstance(ev, IgnoredDisplayEvent)
        assert ev.kind == "-anim"

    def test_bare_spacer_is_ignored_display_with_spacer_kind(self) -> None:
        ev = parse_battle_line("|", 0)
        assert isinstance(ev, IgnoredDisplayEvent)
        assert ev.kind == "spacer"


class TestMalformedAndUnknown:
    def test_malformed_hp_raises(self) -> None:
        with pytest.raises(MalformedProtocolMessage):
            parse_battle_line("|switch|p1a: Garchomp|Garchomp, L50, M|not-a-number", 0)

    def test_missing_field_raises(self) -> None:
        with pytest.raises(MalformedProtocolMessage):
            parse_battle_line("|switch|p1a: Garchomp", 0)

    def test_unknown_state_bearing_type_raises(self) -> None:
        with pytest.raises(UnknownProtocolEvent):
            parse_battle_line("|-notarealwiretype|p1a: Garchomp", 0)

    def test_request_is_rejected_by_parser(self) -> None:
        with pytest.raises(UnknownProtocolEvent):
            parse_battle_line('|request|{"active":[]}', 0)

    def test_error_is_rejected_by_parser(self) -> None:
        with pytest.raises(UnknownProtocolEvent):
            parse_battle_line("|error|[Invalid choice]", 0)


class TestInactiveLine:
    def test_inactiveoff_yields_timer_warning_cleared(self) -> None:
        ev = parse_inactive_line("|inactiveoff|Timer is now off.", 0)
        assert isinstance(ev, VisibleEvidence)
        assert ev.kind == "timer_warning_cleared"

    def test_nonterminal_inactive_yields_timer_warning(self) -> None:
        ev = parse_inactive_line("|inactive|Time left: 150 sec.", 0)
        assert isinstance(ev, VisibleEvidence)
        assert ev.kind == "timer_warning"


class TestPainSplitDeterminism:
    def test_two_sethp_lines_produce_two_events_stable_order(self) -> None:
        ev1 = parse_battle_line("|-sethp|p1a: Garchomp|91/183", 0)
        ev2 = parse_battle_line("|-sethp|p2a: Togekiss|50/100", 1)
        assert ev1.event_index == 0
        assert ev2.event_index == 1
        assert ev1.nickname == "Garchomp"
        assert ev2.nickname == "Togekiss"

    def test_same_two_line_input_yields_value_equal_events(self) -> None:
        a1 = parse_battle_line("|-sethp|p1a: Garchomp|91/183", 5)
        a2 = parse_battle_line("|-sethp|p1a: Garchomp|91/183", 5)
        assert a1 == a2


class TestGameTypeGenerationTierRated:
    def test_gametype(self) -> None:
        ev = parse_battle_line("|gametype|singles", 0)
        assert isinstance(ev, GameTypeDeclared)
        assert ev.game_type == "singles"

    def test_generation(self) -> None:
        ev = parse_battle_line("|gen|9", 0)
        assert isinstance(ev, GenerationDeclared)
        assert ev.generation == 9

    def test_tier(self) -> None:
        ev = parse_battle_line("|tier|[Gen 9] OU", 0)
        assert isinstance(ev, TierDeclared)
        assert ev.tier == "[Gen 9] OU"

    def test_rated_present_means_true(self) -> None:
        ev = parse_battle_line("|rated|", 0)
        assert isinstance(ev, BattleRated)
        assert ev.rated is True

    def test_rule(self) -> None:
        ev = parse_battle_line("|rule|Sleep Clause Mod: Limit one foe put to sleep", 0)
        assert isinstance(ev, RuleDeclared)
        assert "Sleep Clause Mod" in ev.rule


class TestInitializationSequenceIntegration:
    def test_spacer_directly_before_start_parses_and_reduces(self) -> None:
        from battlebelief_core.application.observation.reducer import ObservationReducer

        s = ObservedState.initial("ash")
        events = [
            parse_battle_line("|", 0),
            parse_battle_line("|start", 1),
        ]
        for ev in events:
            s = ObservationReducer.reduce(s, ev)
        assert s.battle_started is True
        assert s.ignored_display_count == 1
