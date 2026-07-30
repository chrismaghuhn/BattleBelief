from __future__ import annotations

import dataclasses

import pytest

from battlebelief_core.domain.events.base import BattleEvent
from battlebelief_core.domain.events.evidence import VisibleEvidence
from battlebelief_core.domain.events.field import (
    FieldConditionChanged,
    SideConditionChanged,
    SideConditionsSwapped,
    WeatherChanged,
)
from battlebelief_core.domain.events.ignored import IgnoredDisplayEvent
from battlebelief_core.domain.events.metadata import (
    BattleInit,
    BattleRated,
    GameTypeDeclared,
    GenerationDeclared,
    PlayerDeclared,
    PreviewCleared,
    PreviewPokemonDeclared,
    RuleDeclared,
    TeamPreviewStarted,
    TeamSizeDeclared,
    TierDeclared,
)
from battlebelief_core.domain.events.pokemon import (
    AbilityChanged,
    BoostChanged,
    BoostChangeMode,
    BoostsCleared,
    BoostsCopied,
    BoostsInverted,
    BoostsSwapped,
    FormChanged,
    HealthChanged,
    IdentityChanged,
    ItemChanged,
    MovePrevented,
    MoveUsed,
    PokemonDragged,
    PokemonFainted,
    PokemonSwitched,
    PokemonTransformed,
    RechargeChanged,
    StatusChanged,
    TeamStatusCured,
    Terastallized,
    TransientEffectObserved,
    VolatileChanged,
)
from battlebelief_core.domain.events.progress import (
    BattleStarted,
    BattleTied,
    BattleWon,
    TurnStarted,
)
from battlebelief_core.domain.state.values import HpObservation, HpPrecision, HpToken


class TestBattleEventBase:
    def test_metadata_events_are_battle_events(self) -> None:
        assert issubclass(BattleInit, BattleEvent)
        assert issubclass(PlayerDeclared, BattleEvent)

    def test_progress_events_are_battle_events(self) -> None:
        assert issubclass(BattleStarted, BattleEvent)
        assert issubclass(BattleWon, BattleEvent)

    def test_pokemon_events_are_battle_events(self) -> None:
        assert issubclass(PokemonSwitched, BattleEvent)
        assert issubclass(HealthChanged, BattleEvent)

    def test_field_events_are_battle_events(self) -> None:
        assert issubclass(WeatherChanged, BattleEvent)

    def test_evidence_is_battle_event(self) -> None:
        assert issubclass(VisibleEvidence, BattleEvent)

    def test_ignored_is_battle_event(self) -> None:
        assert issubclass(IgnoredDisplayEvent, BattleEvent)


class TestMetadataEvents:
    def test_battle_init(self) -> None:
        ev = BattleInit(event_index=0, room_id="battle-gen9ou-12345")
        assert ev.event_index == 0
        assert ev.room_id == "battle-gen9ou-12345"

    def test_player_declared(self) -> None:
        ev = PlayerDeclared(event_index=1, side_id="p1", user_id="ash", display_name="Ash")
        assert ev.side_id == "p1"
        assert ev.user_id == "ash"
        assert ev.display_name == "Ash"

    def test_team_size_declared(self) -> None:
        ev = TeamSizeDeclared(event_index=2, side_id="p1", size=6)
        assert ev.size == 6

    def test_game_type_declared(self) -> None:
        ev = GameTypeDeclared(event_index=3, game_type="singles")
        assert ev.game_type == "singles"

    def test_generation_declared(self) -> None:
        ev = GenerationDeclared(event_index=4, generation=9)
        assert ev.generation == 9

    def test_tier_declared(self) -> None:
        ev = TierDeclared(event_index=5, tier="gen9ou")
        assert ev.tier == "gen9ou"

    def test_battle_rated(self) -> None:
        ev = BattleRated(event_index=6, rated=True)
        assert ev.rated is True

    def test_rule_declared(self) -> None:
        ev = RuleDeclared(event_index=7, rule="Sleep Clause Mod")
        assert ev.rule == "Sleep Clause Mod"

    def test_preview_pokemon_declared(self) -> None:
        ev = PreviewPokemonDeclared(event_index=8, side_id="p1", details="Garchomp", has_item=True)
        assert ev.details == "Garchomp"

    def test_preview_cleared(self) -> None:
        ev = PreviewCleared(event_index=9)
        assert ev.event_index == 9

    def test_team_preview_started(self) -> None:
        ev = TeamPreviewStarted(event_index=10)
        assert ev.event_index == 10

    def test_metadata_events_are_frozen(self) -> None:
        ev = PlayerDeclared(event_index=1, side_id="p1", user_id="ash", display_name="Ash")
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            ev.side_id = "p2"  # type: ignore[misc]


class TestProgressEvents:
    def test_battle_started(self) -> None:
        ev = BattleStarted(event_index=11)
        assert isinstance(ev, BattleEvent)

    def test_turn_started(self) -> None:
        ev = TurnStarted(event_index=12, turn=1)
        assert ev.turn == 1

    def test_battle_won(self) -> None:
        ev = BattleWon(event_index=99, winner="ash")
        assert ev.winner == "ash"

    def test_battle_tied(self) -> None:
        ev = BattleTied(event_index=100)
        assert isinstance(ev, BattleEvent)

    def test_progress_events_are_frozen(self) -> None:
        ev = TurnStarted(event_index=1, turn=1)
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            ev.turn = 2  # type: ignore[misc]


class TestPokemonEvents:
    _hp_token = HpToken(current=183, maximum=183, status=None)
    _hp_obs = HpObservation(current=50, maximum=100, precision=HpPrecision.PERCENT)

    def test_pokemon_switched(self) -> None:
        ev = PokemonSwitched(
            event_index=13,
            side_id="p1",
            slot=1,
            nickname="Garchomp",
            details="Garchomp, L50, M",
            hp=self._hp_token,
        )
        assert ev.nickname == "Garchomp"

    def test_pokemon_dragged(self) -> None:
        ev = PokemonDragged(
            event_index=14,
            side_id="p2",
            slot=1,
            nickname="Togekiss",
            details="Togekiss, L50, F",
            hp=self._hp_token,
        )
        assert ev.slot == 1

    def test_pokemon_fainted(self) -> None:
        ev = PokemonFainted(event_index=15, side_id="p1", slot=1, nickname="Garchomp")
        assert ev.side_id == "p1"

    def test_move_used(self) -> None:
        ev = MoveUsed(
            event_index=16,
            side_id="p1",
            slot=1,
            nickname="Garchomp",
            move_id="earthquake",
            target_side_id="p2",
            target_slot=1,
            target_nickname="Togekiss",
            annotations=(),
        )
        assert ev.move_id == "earthquake"

    def test_move_used_no_target(self) -> None:
        ev = MoveUsed(
            event_index=16,
            side_id="p1",
            slot=1,
            nickname="Garchomp",
            move_id="swordsdance",
            target_side_id=None,
            target_slot=None,
            target_nickname=None,
            annotations=("[from] lockedmove",),
        )
        assert ev.target_side_id is None

    def test_move_prevented(self) -> None:
        ev = MovePrevented(
            event_index=17,
            side_id="p1",
            slot=1,
            nickname="Garchomp",
            reason="flinch",
            move_id=None,
        )
        assert ev.reason == "flinch"

    def test_health_changed(self) -> None:
        ev = HealthChanged(
            event_index=18,
            side_id="p2",
            slot=1,
            nickname="Togekiss",
            hp=self._hp_token,
            annotations=(),
        )
        assert ev.hp is self._hp_token

    def test_status_changed(self) -> None:
        ev = StatusChanged(
            event_index=19,
            side_id="p2",
            slot=1,
            nickname="Togekiss",
            status="brn",
            annotations=(),
        )
        assert ev.status == "brn"

    def test_team_status_cured(self) -> None:
        ev = TeamStatusCured(event_index=20, side_id="p1")
        assert ev.side_id == "p1"

    def test_boost_changed(self) -> None:
        ev = BoostChanged(
            event_index=21,
            side_id="p1",
            slot=1,
            nickname="Garchomp",
            stat="atk",
            mode=BoostChangeMode.DELTA,
            amount=2,
        )
        assert ev.amount == 2
        assert ev.mode == BoostChangeMode.DELTA

    def test_boost_changed_set_mode(self) -> None:
        ev = BoostChanged(
            event_index=21,
            side_id="p1",
            slot=1,
            nickname="Garchomp",
            stat="atk",
            mode=BoostChangeMode.SET,
            amount=-2,
        )
        assert ev.mode == BoostChangeMode.SET
        assert ev.amount == -2

    def test_boosts_swapped(self) -> None:
        ev = BoostsSwapped(
            event_index=22,
            side_id="p1",
            slot=1,
            nickname="Garchomp",
            target_side_id="p2",
            target_slot=1,
            target_nickname="Togekiss",
            stats=("atk", "def"),
        )
        assert "atk" in ev.stats

    def test_boosts_copied(self) -> None:
        ev = BoostsCopied(
            event_index=23,
            side_id="p1",
            slot=1,
            nickname="Garchomp",
            source_side_id="p2",
            source_slot=1,
            source_nickname="Togekiss",
            stats=("spa",),
        )
        assert ev.source_side_id == "p2"

    def test_boosts_cleared(self) -> None:
        ev = BoostsCleared(
            event_index=24,
            side_id="p1",
            slot=1,
            nickname="Garchomp",
            scope="all",
        )
        assert ev.scope == "all"

    def test_boosts_cleared_global(self) -> None:
        ev = BoostsCleared(event_index=24, side_id=None, slot=None, nickname=None, scope="all")
        assert ev.side_id is None

    def test_boosts_cleared_partial_target_raises(self) -> None:
        with pytest.raises(ValueError):
            BoostsCleared(event_index=24, side_id="p1", slot=None, nickname="Garchomp", scope="all")

    def test_boosts_inverted(self) -> None:
        ev = BoostsInverted(event_index=25, side_id="p1", slot=1, nickname="Garchomp")
        assert isinstance(ev, BattleEvent)

    def test_item_changed(self) -> None:
        ev = ItemChanged(
            event_index=26,
            side_id="p1",
            slot=1,
            nickname="Garchomp",
            item="rockyhelmet",
            action="set",
            annotations=(),
        )
        assert ev.action == "set"

    def test_ability_changed(self) -> None:
        ev = AbilityChanged(
            event_index=27,
            side_id="p2",
            slot=1,
            nickname="Togekiss",
            ability="serenegrace",
            action="set",
            annotations=(),
        )
        assert ev.ability == "serenegrace"

    def test_identity_changed(self) -> None:
        ev = IdentityChanged(
            event_index=28,
            side_id="p1",
            slot=1,
            nickname="Zoroark",
            details="Zoroark, L50, M",
            hp=self._hp_token,
        )
        assert ev.details == "Zoroark, L50, M"
        assert ev.hp is self._hp_token

    def test_form_changed(self) -> None:
        ev = FormChanged(
            event_index=29,
            side_id="p1",
            slot=1,
            nickname="Rotom",
            details="Rotom-Wash",
            hp=self._hp_token,
        )
        assert ev.details == "Rotom-Wash"
        assert ev.hp is self._hp_token

    def test_pokemon_transformed(self) -> None:
        ev = PokemonTransformed(
            event_index=30,
            side_id="p1",
            slot=1,
            nickname="Ditto",
            target_side_id="p2",
            target_slot=1,
            target_nickname="Garchomp",
        )
        assert ev.target_nickname == "Garchomp"

    def test_terastallized(self) -> None:
        ev = Terastallized(
            event_index=31,
            side_id="p1",
            slot=1,
            nickname="Garchomp",
            tera_type="Ground",
        )
        assert ev.tera_type == "Ground"

    def test_volatile_changed(self) -> None:
        ev = VolatileChanged(
            event_index=32,
            side_id="p1",
            slot=1,
            nickname="Garchomp",
            volatile="aquaring",
            action="start",
            annotations=(),
        )
        assert ev.action == "start"

    def test_transient_effect_observed(self) -> None:
        ev = TransientEffectObserved(
            event_index=33,
            side_id="p1",
            slot=1,
            nickname="Garchomp",
            effect_id="lifeorb",
            annotations=(),
        )
        assert ev.effect_id == "lifeorb"

    def test_recharge_changed(self) -> None:
        ev = RechargeChanged(
            event_index=34,
            side_id="p1",
            slot=1,
            nickname="Garchomp",
            recharging=True,
        )
        assert ev.recharging is True

    def test_pokemon_events_are_frozen(self) -> None:
        ev = PokemonFainted(event_index=1, side_id="p1", slot=1, nickname="Garchomp")
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            ev.nickname = "Togekiss"  # type: ignore[misc]


class TestFieldEvents:
    def test_weather_changed(self) -> None:
        ev = WeatherChanged(event_index=35, weather="sunnyday", action="start")
        assert ev.weather == "sunnyday"

    def test_weather_changed_end(self) -> None:
        ev = WeatherChanged(event_index=36, weather=None, action="end")
        assert ev.weather is None

    def test_field_condition_changed(self) -> None:
        ev = FieldConditionChanged(
            event_index=37,
            condition="trickroom",
            action="start",
            annotations=(),
        )
        assert ev.condition == "trickroom"

    def test_side_condition_changed(self) -> None:
        ev = SideConditionChanged(
            event_index=38,
            side_id="p1",
            condition="stealthrock",
            action="start",
        )
        assert ev.condition == "stealthrock"

    def test_side_conditions_swapped(self) -> None:
        ev = SideConditionsSwapped(event_index=39)
        assert isinstance(ev, BattleEvent)

    def test_field_events_are_frozen(self) -> None:
        ev = WeatherChanged(event_index=1, weather="sandstorm", action="upkeep")
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            ev.weather = "raindance"  # type: ignore[misc]


class TestEvidenceAndIgnored:
    def test_visible_evidence(self) -> None:
        ev = VisibleEvidence(
            event_index=40,
            kind="crit",
            side_id="p1",
            slot=1,
            nickname="Garchomp",
            effect=None,
            annotations=(),
        )
        assert ev.kind == "crit"

    def test_visible_evidence_no_pokemon(self) -> None:
        ev = VisibleEvidence(
            event_index=41,
            kind="fieldactivate",
            side_id=None,
            slot=None,
            nickname=None,
            effect="trickroom",
            annotations=(),
        )
        assert ev.side_id is None

    def test_ignored_display_event(self) -> None:
        ev = IgnoredDisplayEvent(event_index=42, kind="spacer")
        assert ev.kind == "spacer"

    def test_evidence_is_frozen(self) -> None:
        ev = VisibleEvidence(
            event_index=1,
            kind="miss",
            side_id="p2",
            slot=1,
            nickname="Togekiss",
            effect=None,
            annotations=(),
        )
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            ev.kind = "crit"  # type: ignore[misc]
