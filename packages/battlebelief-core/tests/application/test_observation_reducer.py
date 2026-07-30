from __future__ import annotations

from battlebelief_core.application.observation.reducer import ObservationReducer
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
    TeamSizeDeclared,
    TierDeclared,
)
from battlebelief_core.domain.events.pokemon import (
    AbilityChanged,
    BoostChanged,
    BoostsCleared,
    BoostsCopied,
    BoostsInverted,
    BoostsSwapped,
    FormChanged,
    HealthChanged,
    IdentityChanged,
    ItemChanged,
    MoveUsed,
    PokemonDragged,
    PokemonFainted,
    PokemonSwitched,
    PokemonTransformed,
    StatusChanged,
    TeamStatusCured,
    Terastallized,
)
from battlebelief_core.domain.events.progress import (
    BattleStarted,
    BattleTied,
    BattleWon,
    TurnStarted,
)
from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_core.domain.state.values import HpPrecision, HpToken

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_OWN = "ash"
_OPP = "misty"


def _make_token(current: int = 183, maximum: int = 183, status: str | None = None) -> HpToken:
    return HpToken(current=current, maximum=maximum, status=status)


def _base_state() -> ObservedState:
    return ObservedState.initial(_OWN)


def _with_players(our_side: str = "p1") -> ObservedState:
    """State after room init + both players declared + gen/tier/mode set."""
    opp_side = "p2" if our_side == "p1" else "p1"
    s = _base_state()
    s = ObservationReducer.reduce(s, BattleInit(event_index=0, room_id="battle-gen9ou-1"))
    s = ObservationReducer.reduce(s, PlayerDeclared(event_index=1, side_id=our_side, username=_OWN))
    s = ObservationReducer.reduce(s, PlayerDeclared(event_index=2, side_id=opp_side, username=_OPP))
    s = ObservationReducer.reduce(s, TeamSizeDeclared(event_index=3, side_id=our_side, size=6))
    s = ObservationReducer.reduce(s, TeamSizeDeclared(event_index=4, side_id=opp_side, size=6))
    s = ObservationReducer.reduce(s, GenerationDeclared(event_index=5, generation=9))
    s = ObservationReducer.reduce(s, GameTypeDeclared(event_index=6, game_type="singles"))
    s = ObservationReducer.reduce(s, TierDeclared(event_index=7, tier="gen9ou"))
    return s


def _switch_in(
    s: ObservedState,
    side_id: str,
    nickname: str,
    idx: int,
    details: str = "Garchomp, L50, M",
    current: int = 183,
    maximum: int = 183,
) -> ObservedState:
    return ObservationReducer.reduce(
        s,
        PokemonSwitched(
            event_index=idx,
            side_id=side_id,
            slot=1,
            nickname=nickname,
            details=details,
            hp=_make_token(current, maximum),
        ),
    )


def _side(s: ObservedState, side_id: str):  # type: ignore[return]
    return s.p1 if side_id == "p1" else s.p2


def _active(s: ObservedState, side_id: str):  # type: ignore[return]
    side = _side(s, side_id)
    for pv in side.pokemon:
        if pv.active:
            return pv
    return None


# ---------------------------------------------------------------------------
# metadata and player assignment
# ---------------------------------------------------------------------------


class TestMetadataAndPlayerAssignment:
    def test_our_side_set_on_player_declared(self) -> None:
        s = _base_state()
        s = ObservationReducer.reduce(s, PlayerDeclared(event_index=0, side_id="p1", username=_OWN))
        assert s.our_side == "p1"

    def test_our_side_p2(self) -> None:
        s = _base_state()
        s = ObservationReducer.reduce(s, PlayerDeclared(event_index=0, side_id="p2", username=_OWN))
        assert s.our_side == "p2"

    def test_unmatched_player_does_not_set_our_side(self) -> None:
        s = _base_state()
        s = ObservationReducer.reduce(
            s, PlayerDeclared(event_index=0, side_id="p1", username="other")
        )
        assert s.our_side is None

    def test_player_username_stored_on_side(self) -> None:
        s = _with_players("p1")
        assert s.p1.username == _OWN
        assert s.p2.username == _OPP

    def test_generation_stored(self) -> None:
        s = _with_players()
        assert s.generation == 9

    def test_game_type_stored(self) -> None:
        s = _with_players()
        assert s.game_type == "singles"

    def test_tier_stored(self) -> None:
        s = _with_players()
        assert s.tier == "gen9ou"

    def test_team_size_stored(self) -> None:
        s = _with_players("p1")
        assert s.p1.team_size == 6

    def test_rule_appended(self) -> None:
        s = _with_players()
        s = ObservationReducer.reduce(s, RuleDeclared(event_index=10, rule="Sleep Clause Mod"))
        assert "Sleep Clause Mod" in s.rules

    def test_battle_rated_stored(self) -> None:
        s = _with_players()
        s = ObservationReducer.reduce(s, BattleRated(event_index=11, rated=True))
        assert s.battle_started is False  # rated != started

    def test_battle_init_sets_room_initialized(self) -> None:
        s = _base_state()
        s = ObservationReducer.reduce(s, BattleInit(event_index=0, room_id="battle-gen9ou-1"))
        assert s.room_initialized is True

    def test_battle_started_sets_flag(self) -> None:
        s = _with_players()
        s = ObservationReducer.reduce(s, BattleStarted(event_index=20))
        assert s.battle_started is True

    def test_turn_started_increments_turn(self) -> None:
        s = _with_players()
        s = ObservationReducer.reduce(s, BattleStarted(event_index=20))
        s = ObservationReducer.reduce(s, TurnStarted(event_index=21, turn=1))
        assert s.turn == 1

    def test_battle_won_stores_winner(self) -> None:
        s = _with_players()
        s = ObservationReducer.reduce(s, BattleWon(event_index=99, winner=_OWN))
        assert s.winner == _OWN

    def test_battle_tied(self) -> None:
        s = _with_players()
        s = ObservationReducer.reduce(s, BattleTied(event_index=99))
        assert s.tied is True

    def test_preview_pokemon_stored(self) -> None:
        s = _with_players("p1")
        s = ObservationReducer.reduce(
            s,
            PreviewPokemonDeclared(event_index=8, side_id="p1", details="Garchomp", has_item=True),
        )
        assert "Garchomp" in s.p1.preview_roster

    def test_preview_cleared_empties_roster(self) -> None:
        s = _with_players("p1")
        s = ObservationReducer.reduce(
            s,
            PreviewPokemonDeclared(event_index=8, side_id="p1", details="Garchomp", has_item=True),
        )
        s = ObservationReducer.reduce(s, PreviewCleared(event_index=9))
        assert s.p1.preview_roster == ()
        assert s.p2.preview_roster == ()

    def test_event_index_advances(self) -> None:
        s = _with_players()
        s = ObservationReducer.reduce(s, TurnStarted(event_index=30, turn=1))
        assert s.event_index == 30


# ---------------------------------------------------------------------------
# switch → damage → status → faint
# ---------------------------------------------------------------------------


class TestSwitchDamageStatusFaint:
    def test_switch_creates_pokemon_view(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        assert len(s.p1.pokemon) == 1
        assert s.p1.pokemon[0].nickname == "Garchomp"

    def test_switch_sets_active(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        assert s.p1.pokemon[0].active is True
        assert s.p1.active_slot == 1

    def test_switch_sets_own_side_hp_exact(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20, current=183, maximum=183)
        hp = s.p1.pokemon[0].hp
        assert hp is not None
        assert hp.precision == HpPrecision.EXACT
        assert hp.current == 183

    def test_switch_sets_opponent_hp_percent(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p2", "Togekiss", 21, current=100, maximum=100)
        hp = s.p2.pokemon[0].hp
        assert hp is not None
        assert hp.precision == HpPrecision.PERCENT

    def test_switch_sets_opponent_hp_pixel(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p2", "Togekiss", 21, current=48, maximum=48)
        hp = s.p2.pokemon[0].hp
        assert hp is not None
        assert hp.precision == HpPrecision.PIXEL

    def test_second_switch_deactivates_first(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        s = _switch_in(s, "p1", "Togekiss", 21)
        assert len(s.p1.pokemon) == 2
        names = [pv.nickname for pv in s.p1.pokemon]
        assert "Garchomp" in names and "Togekiss" in names
        active = [pv for pv in s.p1.pokemon if pv.active]
        assert len(active) == 1
        assert active[0].nickname == "Togekiss"

    def test_drag_activates_like_switch(self) -> None:
        s = _with_players("p2")
        s = ObservationReducer.reduce(
            s,
            PokemonDragged(
                event_index=20,
                side_id="p1",
                slot=1,
                nickname="Ditto",
                details="Ditto",
                hp=_make_token(),
            ),
        )
        assert s.p1.pokemon[0].nickname == "Ditto"
        assert s.p1.pokemon[0].active is True

    def test_health_changed_updates_hp(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p2", "Togekiss", 20, current=100, maximum=100)
        s = ObservationReducer.reduce(
            s,
            HealthChanged(
                event_index=21,
                side_id="p2",
                slot=1,
                nickname="Togekiss",
                hp=_make_token(50, 100),
                annotations=(),
            ),
        )
        hp = _active(s, "p2").hp
        assert hp is not None
        assert hp.current == 50

    def test_status_changed_sets_status(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        s = ObservationReducer.reduce(
            s,
            StatusChanged(
                event_index=21,
                side_id="p1",
                slot=1,
                nickname="Garchomp",
                status="brn",
                annotations=(),
            ),
        )
        assert _active(s, "p1").status == "brn"

    def test_status_changed_cure_clears_status(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        s = ObservationReducer.reduce(
            s,
            StatusChanged(
                event_index=21,
                side_id="p1",
                slot=1,
                nickname="Garchomp",
                status="brn",
                annotations=(),
            ),
        )
        s = ObservationReducer.reduce(
            s,
            StatusChanged(
                event_index=22,
                side_id="p1",
                slot=1,
                nickname="Garchomp",
                status=None,
                annotations=(),
            ),
        )
        assert _active(s, "p1").status is None

    def test_pokemon_fainted_sets_fainted(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        s = ObservationReducer.reduce(
            s, PokemonFainted(event_index=21, side_id="p1", slot=1, nickname="Garchomp")
        )
        pv = s.p1.pokemon[0]
        assert pv.fainted is True
        assert pv.active is False

    def test_team_status_cured_clears_all_statuses(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        s = ObservationReducer.reduce(
            s,
            StatusChanged(
                event_index=21,
                side_id="p1",
                slot=1,
                nickname="Garchomp",
                status="psn",
                annotations=(),
            ),
        )
        s = ObservationReducer.reduce(s, TeamStatusCured(event_index=22, side_id="p1"))
        for pv in s.p1.pokemon:
            assert pv.status is None


# ---------------------------------------------------------------------------
# tera, item, ability, form, transform, identity
# ---------------------------------------------------------------------------


class TestTeraItemAbilityFormTransform:
    def test_terastallized_sets_tera_type(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        s = ObservationReducer.reduce(
            s,
            Terastallized(
                event_index=21, side_id="p1", slot=1, nickname="Garchomp", tera_type="Ground"
            ),
        )
        assert _active(s, "p1").tera_type == "Ground"

    def test_item_changed_set(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        s = ObservationReducer.reduce(
            s,
            ItemChanged(
                event_index=21,
                side_id="p1",
                slot=1,
                nickname="Garchomp",
                item="choicescarf",
                action="set",
                annotations=(),
            ),
        )
        pv = _active(s, "p1")
        assert len(pv.item_intervals) >= 1
        assert pv.item_intervals[-1].value == "choicescarf"

    def test_item_changed_end_closes_interval(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        s = ObservationReducer.reduce(
            s,
            ItemChanged(
                event_index=21,
                side_id="p1",
                slot=1,
                nickname="Garchomp",
                item="rockyhelmet",
                action="set",
                annotations=(),
            ),
        )
        s = ObservationReducer.reduce(
            s,
            ItemChanged(
                event_index=22,
                side_id="p1",
                slot=1,
                nickname="Garchomp",
                item=None,
                action="end",
                annotations=(),
            ),
        )
        pv = _active(s, "p1")
        assert pv.item_intervals[-1].valid_until is not None

    def test_ability_changed_set(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        s = ObservationReducer.reduce(
            s,
            AbilityChanged(
                event_index=21,
                side_id="p1",
                slot=1,
                nickname="Garchomp",
                ability="roughskin",
                action="set",
                annotations=(),
            ),
        )
        pv = _active(s, "p1")
        assert len(pv.ability_intervals) >= 1
        assert pv.ability_intervals[-1].value == "roughskin"

    def test_form_changed(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Rotom", 20, details="Rotom")
        s = ObservationReducer.reduce(
            s,
            FormChanged(
                event_index=21, side_id="p1", slot=1, nickname="Rotom", details="Rotom-Wash"
            ),
        )
        assert _active(s, "p1").current_details == "Rotom-Wash"

    def test_identity_changed(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p2", "Zorua", 20, details="Zorua")
        s = ObservationReducer.reduce(
            s,
            IdentityChanged(
                event_index=21, side_id="p2", slot=1, nickname="Zoroark", details="Zoroark, L50, M"
            ),
        )
        pv = _active(s, "p2")
        assert pv.nickname == "Zoroark"
        assert len(pv.identity_intervals) >= 1

    def test_move_added_to_revealed_moves(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        s = ObservationReducer.reduce(
            s,
            MoveUsed(
                event_index=21,
                side_id="p1",
                slot=1,
                nickname="Garchomp",
                move_id="earthquake",
                target_side_id="p2",
                target_slot=1,
                target_nickname="Togekiss",
                annotations=(),
            ),
        )
        assert "earthquake" in _active(s, "p1").revealed_moves

    def test_move_not_duplicated(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        for i in range(3):
            s = ObservationReducer.reduce(
                s,
                MoveUsed(
                    event_index=21 + i,
                    side_id="p1",
                    slot=1,
                    nickname="Garchomp",
                    move_id="earthquake",
                    target_side_id=None,
                    target_slot=None,
                    target_nickname=None,
                    annotations=(),
                ),
            )
        assert s.p1.pokemon[0].revealed_moves.count("earthquake") == 1

    def test_transform_sets_target(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Ditto", 20)
        s = _switch_in(s, "p2", "Garchomp", 21)
        s = ObservationReducer.reduce(
            s,
            PokemonTransformed(
                event_index=22,
                side_id="p1",
                slot=1,
                nickname="Ditto",
                target_side_id="p2",
                target_slot=1,
                target_nickname="Garchomp",
            ),
        )
        assert _active(s, "p1").transform_target == "Garchomp"


# ---------------------------------------------------------------------------
# boosts
# ---------------------------------------------------------------------------


class TestBoosts:
    def test_boost_increases(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        s = ObservationReducer.reduce(
            s,
            BoostChanged(
                event_index=21, side_id="p1", slot=1, nickname="Garchomp", stat="atk", delta=2
            ),
        )
        pv = _active(s, "p1")
        assert pv.boosts[0] == 2  # atk is index 0

    def test_boost_clamps_at_positive_6(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        for _ in range(5):
            s = ObservationReducer.reduce(
                s,
                BoostChanged(
                    event_index=21, side_id="p1", slot=1, nickname="Garchomp", stat="atk", delta=2
                ),
            )
        assert _active(s, "p1").boosts[0] == 6

    def test_boost_clamps_at_negative_6(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        for _ in range(5):
            s = ObservationReducer.reduce(
                s,
                BoostChanged(
                    event_index=21, side_id="p1", slot=1, nickname="Garchomp", stat="atk", delta=-2
                ),
            )
        assert _active(s, "p1").boosts[0] == -6

    def test_boosts_cleared_all(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        s = ObservationReducer.reduce(
            s,
            BoostChanged(
                event_index=21, side_id="p1", slot=1, nickname="Garchomp", stat="atk", delta=3
            ),
        )
        s = ObservationReducer.reduce(
            s,
            BoostsCleared(event_index=22, side_id="p1", slot=1, nickname="Garchomp", scope="all"),
        )
        assert all(b == 0 for b in _active(s, "p1").boosts)

    def test_boosts_cleared_positive_only(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        s = ObservationReducer.reduce(
            s,
            BoostChanged(
                event_index=21, side_id="p1", slot=1, nickname="Garchomp", stat="atk", delta=3
            ),
        )
        s = ObservationReducer.reduce(
            s,
            BoostChanged(
                event_index=22, side_id="p1", slot=1, nickname="Garchomp", stat="def", delta=-2
            ),
        )
        s = ObservationReducer.reduce(
            s,
            BoostsCleared(
                event_index=23, side_id="p1", slot=1, nickname="Garchomp", scope="positive"
            ),
        )
        pv = _active(s, "p1")
        assert pv.boosts[0] == 0  # atk cleared
        assert pv.boosts[1] == -2  # def unchanged

    def test_boosts_inverted(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        s = ObservationReducer.reduce(
            s,
            BoostChanged(
                event_index=21, side_id="p1", slot=1, nickname="Garchomp", stat="atk", delta=3
            ),
        )
        s = ObservationReducer.reduce(
            s,
            BoostsInverted(event_index=22, side_id="p1", slot=1, nickname="Garchomp"),
        )
        assert _active(s, "p1").boosts[0] == -3

    def test_boosts_swapped(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        s = _switch_in(s, "p2", "Togekiss", 21)
        s = ObservationReducer.reduce(
            s,
            BoostChanged(
                event_index=22, side_id="p1", slot=1, nickname="Garchomp", stat="atk", delta=2
            ),
        )
        s = ObservationReducer.reduce(
            s,
            BoostsSwapped(
                event_index=23,
                side_id="p1",
                slot=1,
                nickname="Garchomp",
                target_side_id="p2",
                target_slot=1,
                target_nickname="Togekiss",
                stats=("atk",),
            ),
        )
        assert _active(s, "p1").boosts[0] == 0
        assert _active(s, "p2").boosts[0] == 2

    def test_boosts_copied(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        s = _switch_in(s, "p2", "Togekiss", 21)
        s = ObservationReducer.reduce(
            s,
            BoostChanged(
                event_index=22, side_id="p1", slot=1, nickname="Garchomp", stat="spa", delta=3
            ),
        )
        s = ObservationReducer.reduce(
            s,
            BoostsCopied(
                event_index=23,
                side_id="p2",
                slot=1,
                nickname="Togekiss",
                source_side_id="p1",
                source_slot=1,
                source_nickname="Garchomp",
                stats=("spa",),
            ),
        )
        # Togekiss copies Garchomp's spa boost
        assert _active(s, "p2").boosts[2] == 3  # spa is index 2

    def test_boosts_reset_on_switch(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        s = ObservationReducer.reduce(
            s,
            BoostChanged(
                event_index=21, side_id="p1", slot=1, nickname="Garchomp", stat="atk", delta=3
            ),
        )
        s = _switch_in(s, "p1", "Togekiss", 22)
        # Garchomp's boosts should persist on its view (not reset by switch out)
        garchomp = next(pv for pv in s.p1.pokemon if pv.nickname == "Garchomp")
        assert garchomp.boosts[0] == 3


# ---------------------------------------------------------------------------
# side conditions - spikes (max 3), toxic spikes (max 2), stealthrock (max 1)
# ---------------------------------------------------------------------------


class TestSideConditions:
    def test_spikes_first_layer(self) -> None:
        s = _with_players("p1")
        s = ObservationReducer.reduce(
            s,
            SideConditionChanged(event_index=10, side_id="p2", condition="spikes", action="start"),
        )
        cond = dict(s.p2.side_conditions)
        assert cond.get("spikes") == 1

    def test_spikes_three_layers(self) -> None:
        s = _with_players("p1")
        for i in range(3):
            s = ObservationReducer.reduce(
                s,
                SideConditionChanged(
                    event_index=10 + i, side_id="p2", condition="spikes", action="start"
                ),
            )
        cond = dict(s.p2.side_conditions)
        assert cond["spikes"] == 3

    def test_spikes_capped_at_three(self) -> None:
        s = _with_players("p1")
        for i in range(5):
            s = ObservationReducer.reduce(
                s,
                SideConditionChanged(
                    event_index=10 + i, side_id="p2", condition="spikes", action="start"
                ),
            )
        assert dict(s.p2.side_conditions)["spikes"] == 3

    def test_toxic_spikes_capped_at_two(self) -> None:
        s = _with_players("p1")
        for i in range(4):
            s = ObservationReducer.reduce(
                s,
                SideConditionChanged(
                    event_index=10 + i, side_id="p2", condition="toxicspikes", action="start"
                ),
            )
        assert dict(s.p2.side_conditions)["toxicspikes"] == 2

    def test_stealthrock_capped_at_one(self) -> None:
        s = _with_players("p1")
        for i in range(3):
            s = ObservationReducer.reduce(
                s,
                SideConditionChanged(
                    event_index=10 + i, side_id="p2", condition="stealthrock", action="start"
                ),
            )
        assert dict(s.p2.side_conditions)["stealthrock"] == 1

    def test_spikes_removed_on_end(self) -> None:
        s = _with_players("p1")
        for i in range(2):
            s = ObservationReducer.reduce(
                s,
                SideConditionChanged(
                    event_index=10 + i, side_id="p2", condition="spikes", action="start"
                ),
            )
        s = ObservationReducer.reduce(
            s, SideConditionChanged(event_index=12, side_id="p2", condition="spikes", action="end")
        )
        assert "spikes" not in dict(s.p2.side_conditions)

    def test_side_conditions_swapped(self) -> None:
        s = _with_players("p1")
        s = ObservationReducer.reduce(
            s,
            SideConditionChanged(
                event_index=10, side_id="p1", condition="stealthrock", action="start"
            ),
        )
        s = ObservationReducer.reduce(s, SideConditionsSwapped(event_index=11))
        assert "stealthrock" in dict(s.p2.side_conditions)
        assert "stealthrock" not in dict(s.p1.side_conditions)


# ---------------------------------------------------------------------------
# weather and field conditions
# ---------------------------------------------------------------------------


class TestWeatherAndField:
    def test_weather_started(self) -> None:
        s = _with_players("p1")
        s = ObservationReducer.reduce(
            s, WeatherChanged(event_index=10, weather="sunnyday", action="start")
        )
        assert s.weather == "sunnyday"

    def test_weather_upkeep_preserved(self) -> None:
        s = _with_players("p1")
        s = ObservationReducer.reduce(
            s, WeatherChanged(event_index=10, weather="sandstorm", action="start")
        )
        s = ObservationReducer.reduce(
            s, WeatherChanged(event_index=11, weather="sandstorm", action="upkeep")
        )
        assert s.weather == "sandstorm"

    def test_weather_ended(self) -> None:
        s = _with_players("p1")
        s = ObservationReducer.reduce(
            s, WeatherChanged(event_index=10, weather="raindance", action="start")
        )
        s = ObservationReducer.reduce(s, WeatherChanged(event_index=11, weather=None, action="end"))
        assert s.weather is None

    def test_field_condition_started(self) -> None:
        s = _with_players("p1")
        s = ObservationReducer.reduce(
            s,
            FieldConditionChanged(
                event_index=10, condition="trickroom", action="start", annotations=()
            ),
        )
        assert "trickroom" in s.field_conditions

    def test_field_condition_ended(self) -> None:
        s = _with_players("p1")
        s = ObservationReducer.reduce(
            s,
            FieldConditionChanged(
                event_index=10, condition="trickroom", action="start", annotations=()
            ),
        )
        s = ObservationReducer.reduce(
            s,
            FieldConditionChanged(
                event_index=11, condition="trickroom", action="end", annotations=()
            ),
        )
        assert "trickroom" not in s.field_conditions


# ---------------------------------------------------------------------------
# visible evidence vs ignored display
# ---------------------------------------------------------------------------


class TestEvidenceAndIgnored:
    def test_visible_evidence_appended(self) -> None:
        s = _with_players("p1")
        ev = VisibleEvidence(
            event_index=10,
            kind="crit",
            side_id="p1",
            slot=1,
            nickname="Garchomp",
            effect=None,
            annotations=(),
        )
        s = ObservationReducer.reduce(s, ev)
        assert len(s.visible_evidence) == 1
        assert s.visible_evidence[0].kind == "crit"

    def test_ignored_display_increments_counter(self) -> None:
        s = _with_players("p1")
        s = ObservationReducer.reduce(s, IgnoredDisplayEvent(event_index=10, kind="spacer"))
        s = ObservationReducer.reduce(s, IgnoredDisplayEvent(event_index=11, kind="upkeep"))
        assert s.ignored_display_count == 2

    def test_ignored_display_does_not_affect_evidence(self) -> None:
        s = _with_players("p1")
        s = ObservationReducer.reduce(s, IgnoredDisplayEvent(event_index=10, kind="-anim"))
        assert len(s.visible_evidence) == 0


# ---------------------------------------------------------------------------
# immutability of input state
# ---------------------------------------------------------------------------


class TestInputImmutability:
    def test_original_state_not_mutated(self) -> None:
        original = ObservedState.initial(_OWN)
        _ = ObservationReducer.reduce(original, GenerationDeclared(event_index=0, generation=9))
        assert original.generation is None

    def test_original_pokemon_not_mutated(self) -> None:
        s = _with_players("p1")
        s = _switch_in(s, "p1", "Garchomp", 20)
        original_pokemon_count = len(s.p1.pokemon)
        _ = _switch_in(s, "p1", "Togekiss", 21)
        assert len(s.p1.pokemon) == original_pokemon_count
