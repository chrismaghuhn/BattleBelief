from __future__ import annotations

import dataclasses

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
from battlebelief_core.domain.state.observed_state import ObservedState
from battlebelief_core.domain.state.pokemon_view import BOOST_STATS, ZERO_BOOSTS, PokemonView
from battlebelief_core.domain.state.side_view import SideView
from battlebelief_core.domain.state.values import (
    EvidenceInterval,
    HpObservation,
    HpPrecision,
    HpToken,
)
from battlebelief_core.errors import ReducerInvariantError

# Layer caps per side-condition
_LAYER_CAPS: dict[str, int] = {"spikes": 3, "toxicspikes": 2}
_DEFAULT_LAYER_CAP = 1


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------


def _token_to_observation(token: HpToken, side_id: str, our_side: str | None) -> HpObservation:
    if token.fainted:
        return HpObservation(
            current=0, maximum=max(token.maximum, 1), precision=HpPrecision.PERCENT, fainted=True
        )
    if our_side is not None and side_id == our_side:
        precision = HpPrecision.EXACT
    elif token.maximum == 100:
        precision = HpPrecision.PERCENT
    else:
        precision = HpPrecision.PIXEL
    return HpObservation(current=token.current, maximum=token.maximum, precision=precision)


def _find_pokemon(side: SideView, nickname: str) -> PokemonView | None:
    for pv in side.pokemon:
        if pv.nickname == nickname:
            return pv
    return None


def _replace_pokemon(side: SideView, updated: PokemonView) -> SideView:
    new_pokemon = tuple(updated if pv.nickname == updated.nickname else pv for pv in side.pokemon)
    return dataclasses.replace(side, pokemon=new_pokemon)


def _update_side(state: ObservedState, new_side: SideView) -> ObservedState:
    if new_side.side_id == "p1":
        return dataclasses.replace(state, p1=new_side)
    return dataclasses.replace(state, p2=new_side)


def _apply_boost_delta(boosts: tuple[int, ...], stat: str, delta: int) -> tuple[int, ...]:
    idx = BOOST_STATS.index(stat)
    clamped = max(-6, min(6, boosts[idx] + delta))
    return (*boosts[:idx], clamped, *boosts[idx + 1 :])


def _clear_boosts(boosts: tuple[int, ...], scope: str) -> tuple[int, ...]:
    if scope == "all":
        return ZERO_BOOSTS
    if scope == "positive":
        return tuple(min(b, 0) for b in boosts)
    if scope == "negative":
        return tuple(max(b, 0) for b in boosts)
    # single stat clear
    if scope in BOOST_STATS:
        idx = BOOST_STATS.index(scope)
        return (*boosts[:idx], 0, *boosts[idx + 1 :])
    return boosts


def _update_side_condition(
    conditions: tuple[tuple[str, int], ...], condition: str, action: str
) -> tuple[tuple[str, int], ...]:
    cond_dict = dict(conditions)
    if action in ("start", "upkeep"):
        cap = _LAYER_CAPS.get(condition, _DEFAULT_LAYER_CAP)
        cond_dict[condition] = min(cond_dict.get(condition, 0) + 1, cap)
    elif action == "end":
        cond_dict.pop(condition, None)
    return tuple(sorted(cond_dict.items()))


def _open_interval(
    intervals: tuple[EvidenceInterval, ...], value: str | None, event_index: int
) -> tuple[EvidenceInterval, ...]:
    # Close any currently open interval
    closed = tuple(
        dataclasses.replace(iv, valid_until=event_index) if iv.valid_until is None else iv
        for iv in intervals
    )
    new_iv = EvidenceInterval(value=value, source_event_index=event_index, valid_from=event_index)
    return (*closed, new_iv)


def _close_interval(
    intervals: tuple[EvidenceInterval, ...], event_index: int
) -> tuple[EvidenceInterval, ...]:
    return tuple(
        dataclasses.replace(iv, valid_until=event_index) if iv.valid_until is None else iv
        for iv in intervals
    )


def _activate_pokemon(side: SideView, nickname: str, details: str, hp: HpObservation) -> SideView:
    """Deactivate current active pokemon, activate (or add) the named one."""
    # Deactivate current active
    deactivated = tuple(
        dataclasses.replace(pv, active=False) if pv.active else pv for pv in side.pokemon
    )
    existing = next((pv for pv in deactivated if pv.nickname == nickname), None)
    if existing is None:
        new_pv = dataclasses.replace(
            PokemonView.new(side.side_id, nickname, details),
            active=True,
            hp=hp,
            current_details=details,
        )
        return dataclasses.replace(side, pokemon=(*deactivated, new_pv), active_slot=1)
    updated = dataclasses.replace(existing, active=True, hp=hp, current_details=details)
    new_pokemon = tuple(updated if pv.nickname == nickname else pv for pv in deactivated)
    return dataclasses.replace(side, pokemon=new_pokemon, active_slot=1)


# ---------------------------------------------------------------------------
# reducer
# ---------------------------------------------------------------------------


class ObservationReducer:
    @staticmethod
    def reduce(state: ObservedState, event: BattleEvent) -> ObservedState:
        ei = event.event_index
        state = dataclasses.replace(state, event_index=ei)

        # ── metadata ──────────────────────────────────────────────────────
        if isinstance(event, BattleInit):
            return dataclasses.replace(state, room_initialized=True)

        if isinstance(event, PlayerDeclared):
            new_our_side = state.our_side
            if event.username == state.our_user_id and new_our_side is None:
                new_our_side = event.side_id
            side = state.side(event.side_id)
            new_side = dataclasses.replace(side, username=event.username)
            return _update_side(dataclasses.replace(state, our_side=new_our_side), new_side)

        if isinstance(event, TeamSizeDeclared):
            side = state.side(event.side_id)
            return _update_side(state, dataclasses.replace(side, team_size=event.size))

        if isinstance(event, GenerationDeclared):
            return dataclasses.replace(state, generation=event.generation)

        if isinstance(event, GameTypeDeclared):
            return dataclasses.replace(state, game_type=event.game_type)

        if isinstance(event, TierDeclared):
            return dataclasses.replace(state, tier=event.tier)

        if isinstance(event, BattleRated):
            return state  # rated flag not tracked separately; no-op

        if isinstance(event, RuleDeclared):
            return dataclasses.replace(state, rules=(*state.rules, event.rule))

        if isinstance(event, PreviewPokemonDeclared):
            side = state.side(event.side_id)
            return _update_side(
                state,
                dataclasses.replace(side, preview_roster=(*side.preview_roster, event.details)),
            )

        if isinstance(event, PreviewCleared):
            p1 = dataclasses.replace(state.p1, preview_roster=())
            p2 = dataclasses.replace(state.p2, preview_roster=())
            return dataclasses.replace(state, p1=p1, p2=p2)

        if isinstance(event, TeamPreviewStarted):
            return state

        # ── progress ─────────────────────────────────────────────────────
        if isinstance(event, BattleStarted):
            return dataclasses.replace(state, battle_started=True)

        if isinstance(event, TurnStarted):
            return dataclasses.replace(state, turn=event.turn)

        if isinstance(event, BattleWon):
            return dataclasses.replace(state, winner=event.winner)

        if isinstance(event, BattleTied):
            return dataclasses.replace(state, tied=True)

        # ── pokemon events ────────────────────────────────────────────────
        if isinstance(event, (PokemonSwitched, PokemonDragged)):
            hp_obs = _token_to_observation(event.hp, event.side_id, state.our_side)
            side = state.side(event.side_id)
            new_side = _activate_pokemon(side, event.nickname, event.details, hp_obs)
            return _update_side(state, new_side)

        if isinstance(event, PokemonFainted):
            side = state.side(event.side_id)
            pv = _find_pokemon(side, event.nickname)
            if pv is None:
                raise ReducerInvariantError(f"faint: unknown pokemon {event.nickname}")
            updated = dataclasses.replace(pv, fainted=True, active=False, hp=None)
            return _update_side(state, _replace_pokemon(side, updated))

        if isinstance(event, MoveUsed):
            side = state.side(event.side_id)
            pv = _find_pokemon(side, event.nickname)
            if pv is None:
                raise ReducerInvariantError(f"move: unknown pokemon {event.nickname}")
            if event.move_id not in pv.revealed_moves:
                updated = dataclasses.replace(
                    pv, revealed_moves=(*pv.revealed_moves, event.move_id)
                )
                return _update_side(state, _replace_pokemon(side, updated))
            return state

        if isinstance(event, MovePrevented):
            return state  # no state change; just observable evidence

        if isinstance(event, HealthChanged):
            side = state.side(event.side_id)
            pv = _find_pokemon(side, event.nickname)
            if pv is None:
                raise ReducerInvariantError(f"health: unknown pokemon {event.nickname}")
            hp_obs = _token_to_observation(event.hp, event.side_id, state.our_side)
            updated = dataclasses.replace(pv, hp=hp_obs)
            return _update_side(state, _replace_pokemon(side, updated))

        if isinstance(event, StatusChanged):
            side = state.side(event.side_id)
            pv = _find_pokemon(side, event.nickname)
            if pv is None:
                raise ReducerInvariantError(f"status: unknown pokemon {event.nickname}")
            updated = dataclasses.replace(pv, status=event.status)
            return _update_side(state, _replace_pokemon(side, updated))

        if isinstance(event, TeamStatusCured):
            side = state.side(event.side_id)
            cured = tuple(dataclasses.replace(pv, status=None) for pv in side.pokemon)
            return _update_side(state, dataclasses.replace(side, pokemon=cured))

        if isinstance(event, BoostChanged):
            side = state.side(event.side_id)
            pv = _find_pokemon(side, event.nickname)
            if pv is None:
                raise ReducerInvariantError(f"boost: unknown pokemon {event.nickname}")
            new_boosts = _apply_boost_delta(pv.boosts, event.stat, event.delta)
            return _update_side(
                state, _replace_pokemon(side, dataclasses.replace(pv, boosts=new_boosts))
            )

        if isinstance(event, BoostsSwapped):
            src_side = state.side(event.side_id)
            tgt_side = state.side(event.target_side_id)
            src_pv = _find_pokemon(src_side, event.nickname)
            tgt_pv = _find_pokemon(tgt_side, event.target_nickname)
            if src_pv is None or tgt_pv is None:
                raise ReducerInvariantError("swap_boost: unknown pokemon")
            src_boosts = list(src_pv.boosts)
            tgt_boosts = list(tgt_pv.boosts)
            for stat in event.stats:
                idx = BOOST_STATS.index(stat)
                src_boosts[idx], tgt_boosts[idx] = tgt_boosts[idx], src_boosts[idx]
            new_src = dataclasses.replace(src_pv, boosts=tuple(src_boosts))
            new_tgt = dataclasses.replace(tgt_pv, boosts=tuple(tgt_boosts))
            # Update both sides (may be the same side)
            new_src_side = _replace_pokemon(src_side, new_src)
            if event.side_id == event.target_side_id:
                new_tgt_side = _replace_pokemon(new_src_side, new_tgt)
                return _update_side(state, new_tgt_side)
            state = _update_side(state, new_src_side)
            new_tgt_side = _replace_pokemon(state.side(event.target_side_id), new_tgt)
            return _update_side(state, new_tgt_side)

        if isinstance(event, BoostsCopied):
            src_side = state.side(event.source_side_id)
            tgt_side = state.side(event.side_id)
            src_pv = _find_pokemon(src_side, event.source_nickname)
            tgt_pv = _find_pokemon(tgt_side, event.nickname)
            if src_pv is None or tgt_pv is None:
                raise ReducerInvariantError("copy_boost: unknown pokemon")
            tgt_boosts = list(tgt_pv.boosts)
            for stat in event.stats:
                idx = BOOST_STATS.index(stat)
                tgt_boosts[idx] = src_pv.boosts[idx]
            new_tgt = dataclasses.replace(tgt_pv, boosts=tuple(tgt_boosts))
            return _update_side(state, _replace_pokemon(tgt_side, new_tgt))

        if isinstance(event, BoostsCleared):
            side = state.side(event.side_id)
            pv = _find_pokemon(side, event.nickname)
            if pv is None:
                raise ReducerInvariantError(f"clear_boost: unknown pokemon {event.nickname}")
            new_boosts = _clear_boosts(pv.boosts, event.scope)
            return _update_side(
                state, _replace_pokemon(side, dataclasses.replace(pv, boosts=new_boosts))
            )

        if isinstance(event, BoostsInverted):
            side = state.side(event.side_id)
            pv = _find_pokemon(side, event.nickname)
            if pv is None:
                raise ReducerInvariantError(f"invert_boost: unknown pokemon {event.nickname}")
            inverted = tuple(-b for b in pv.boosts)
            return _update_side(
                state, _replace_pokemon(side, dataclasses.replace(pv, boosts=inverted))
            )

        if isinstance(event, ItemChanged):
            side = state.side(event.side_id)
            pv = _find_pokemon(side, event.nickname)
            if pv is None:
                raise ReducerInvariantError(f"item: unknown pokemon {event.nickname}")
            if event.action == "set":
                new_intervals = _open_interval(pv.item_intervals, event.item, ei)
            else:
                new_intervals = _close_interval(pv.item_intervals, ei)
            updated = dataclasses.replace(pv, item_intervals=new_intervals)
            return _update_side(state, _replace_pokemon(side, updated))

        if isinstance(event, AbilityChanged):
            side = state.side(event.side_id)
            pv = _find_pokemon(side, event.nickname)
            if pv is None:
                raise ReducerInvariantError(f"ability: unknown pokemon {event.nickname}")
            if event.action == "set":
                new_intervals = _open_interval(pv.ability_intervals, event.ability, ei)
            else:
                new_intervals = _close_interval(pv.ability_intervals, ei)
            updated = dataclasses.replace(pv, ability_intervals=new_intervals)
            return _update_side(state, _replace_pokemon(side, updated))

        if isinstance(event, IdentityChanged):
            side = state.side(event.side_id)
            # The nickname may change — find by slot (active pokemon)
            pv = next((p for p in side.pokemon if p.active), None)
            if pv is None:
                pv = _find_pokemon(side, event.nickname)
            if pv is None:
                raise ReducerInvariantError(f"identity: no active pokemon on {event.side_id}")
            new_intervals = _open_interval(pv.identity_intervals, event.details, ei)
            # Replace with new nickname
            updated = dataclasses.replace(
                pv,
                nickname=event.nickname,
                current_details=event.details,
                identity_intervals=new_intervals,
            )
            new_pokemon = tuple(updated if p.nickname == pv.nickname else p for p in side.pokemon)
            return _update_side(state, dataclasses.replace(side, pokemon=new_pokemon))

        if isinstance(event, FormChanged):
            side = state.side(event.side_id)
            pv = _find_pokemon(side, event.nickname)
            if pv is None:
                raise ReducerInvariantError(f"form: unknown pokemon {event.nickname}")
            updated = dataclasses.replace(pv, current_details=event.details)
            return _update_side(state, _replace_pokemon(side, updated))

        if isinstance(event, PokemonTransformed):
            side = state.side(event.side_id)
            pv = _find_pokemon(side, event.nickname)
            if pv is None:
                raise ReducerInvariantError(f"transform: unknown pokemon {event.nickname}")
            updated = dataclasses.replace(pv, transform_target=event.target_nickname)
            return _update_side(state, _replace_pokemon(side, updated))

        if isinstance(event, Terastallized):
            side = state.side(event.side_id)
            pv = _find_pokemon(side, event.nickname)
            if pv is None:
                raise ReducerInvariantError(f"tera: unknown pokemon {event.nickname}")
            updated = dataclasses.replace(pv, tera_type=event.tera_type)
            return _update_side(state, _replace_pokemon(side, updated))

        if isinstance(event, VolatileChanged):
            side = state.side(event.side_id)
            pv = _find_pokemon(side, event.nickname)
            if pv is None:
                raise ReducerInvariantError(f"volatile: unknown pokemon {event.nickname}")
            if event.action == "start":
                if event.volatile not in pv.volatiles:
                    new_v = tuple(sorted((*pv.volatiles, event.volatile)))
                    updated = dataclasses.replace(pv, volatiles=new_v)
                    return _update_side(state, _replace_pokemon(side, updated))
            elif event.action == "end":
                new_v = tuple(v for v in pv.volatiles if v != event.volatile)
                updated = dataclasses.replace(pv, volatiles=new_v)
                return _update_side(state, _replace_pokemon(side, updated))
            return state

        if isinstance(event, RechargeChanged):
            side = state.side(event.side_id)
            pv = _find_pokemon(side, event.nickname)
            if pv is None:
                raise ReducerInvariantError(f"recharge: unknown pokemon {event.nickname}")
            updated = dataclasses.replace(pv, recharging=event.recharging)
            return _update_side(state, _replace_pokemon(side, updated))

        if isinstance(event, TransientEffectObserved):
            ev = VisibleEvidence(
                event_index=ei,
                kind=event.effect_id,
                side_id=event.side_id,
                slot=event.slot,
                nickname=event.nickname,
                effect=None,
                annotations=event.annotations,
            )
            return dataclasses.replace(state, visible_evidence=(*state.visible_evidence, ev))

        # ── field events ──────────────────────────────────────────────────
        if isinstance(event, WeatherChanged):
            if event.action == "end":
                return dataclasses.replace(state, weather=None)
            return dataclasses.replace(state, weather=event.weather)

        if isinstance(event, FieldConditionChanged):
            if event.action == "start":
                if event.condition not in state.field_conditions:
                    return dataclasses.replace(
                        state, field_conditions=(*state.field_conditions, event.condition)
                    )
            elif event.action == "end":
                return dataclasses.replace(
                    state,
                    field_conditions=tuple(
                        c for c in state.field_conditions if c != event.condition
                    ),
                )
            return state

        if isinstance(event, SideConditionChanged):
            side = state.side(event.side_id)
            new_conditions = _update_side_condition(
                side.side_conditions, event.condition, event.action
            )
            return _update_side(state, dataclasses.replace(side, side_conditions=new_conditions))

        if isinstance(event, SideConditionsSwapped):
            new_p1 = dataclasses.replace(state.p1, side_conditions=state.p2.side_conditions)
            new_p2 = dataclasses.replace(state.p2, side_conditions=state.p1.side_conditions)
            return dataclasses.replace(state, p1=new_p1, p2=new_p2)

        # ── evidence and ignored ──────────────────────────────────────────
        if isinstance(event, VisibleEvidence):
            return dataclasses.replace(state, visible_evidence=(*state.visible_evidence, event))

        if isinstance(event, IgnoredDisplayEvent):
            return dataclasses.replace(state, ignored_display_count=state.ignored_display_count + 1)

        raise ReducerInvariantError(f"unhandled event type: {type(event).__name__}")
