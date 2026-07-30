from __future__ import annotations

import dataclasses

import pytest

from battlebelief_core.domain.state.values import (
    EffectCounter,
    EvidenceInterval,
    HpObservation,
    HpPrecision,
    HpToken,
)


class TestHpObservation:
    def test_valid_exact(self) -> None:
        obs = HpObservation(current=183, maximum=183, precision=HpPrecision.EXACT)
        assert obs.current == 183
        assert obs.fainted is False

    def test_valid_percent(self) -> None:
        obs = HpObservation(current=75, maximum=100, precision=HpPrecision.PERCENT)
        assert obs.precision == HpPrecision.PERCENT

    def test_valid_pixel(self) -> None:
        obs = HpObservation(current=48, maximum=48, precision=HpPrecision.PIXEL)
        assert obs.precision == HpPrecision.PIXEL

    def test_valid_fainted(self) -> None:
        obs = HpObservation(current=0, maximum=100, precision=HpPrecision.PERCENT, fainted=True)
        assert obs.fainted is True

    def test_exact_and_percent_are_distinct(self) -> None:
        exact = HpObservation(current=100, maximum=100, precision=HpPrecision.EXACT)
        pct = HpObservation(current=100, maximum=100, precision=HpPrecision.PERCENT)
        assert exact != pct

    def test_invalid_maximum_zero(self) -> None:
        with pytest.raises(ValueError):
            HpObservation(current=0, maximum=0, precision=HpPrecision.EXACT)

    def test_invalid_maximum_negative(self) -> None:
        with pytest.raises(ValueError):
            HpObservation(current=0, maximum=-1, precision=HpPrecision.EXACT)

    def test_invalid_current_negative(self) -> None:
        with pytest.raises(ValueError):
            HpObservation(current=-1, maximum=100, precision=HpPrecision.PERCENT)

    def test_invalid_current_exceeds_maximum(self) -> None:
        with pytest.raises(ValueError):
            HpObservation(current=101, maximum=100, precision=HpPrecision.PERCENT)

    def test_invalid_fainted_nonzero_current(self) -> None:
        with pytest.raises(ValueError):
            HpObservation(current=1, maximum=100, precision=HpPrecision.PERCENT, fainted=True)

    def test_is_frozen(self) -> None:
        obs = HpObservation(current=50, maximum=100, precision=HpPrecision.PERCENT)
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            obs.current = 99  # type: ignore[misc]


class TestHpToken:
    def test_valid_no_status(self) -> None:
        token = HpToken(current=183, maximum=183, status=None)
        assert token.fainted is False

    def test_valid_with_status(self) -> None:
        token = HpToken(current=75, maximum=183, status="brn")
        assert token.status == "brn"

    def test_valid_fainted(self) -> None:
        token = HpToken(current=0, maximum=183, status=None, fainted=True)
        assert token.fainted is True

    def test_is_frozen(self) -> None:
        token = HpToken(current=100, maximum=100, status=None)
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            token.current = 0  # type: ignore[misc]


class TestEvidenceInterval:
    def test_valid_open(self) -> None:
        iv = EvidenceInterval(value="leftovers", source_event_index=3, valid_from=3)
        assert iv.valid_until is None

    def test_valid_closed(self) -> None:
        iv = EvidenceInterval(value="leftovers", source_event_index=3, valid_from=3, valid_until=7)
        assert iv.valid_until == 7

    def test_is_frozen(self) -> None:
        iv = EvidenceInterval(value=None, source_event_index=0, valid_from=0)
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            iv.value = "x"  # type: ignore[misc]


class TestEffectCounter:
    def test_valid(self) -> None:
        ec = EffectCounter(effect_id="spikes", count=2)
        assert ec.count == 2

    def test_is_frozen(self) -> None:
        ec = EffectCounter(effect_id="spikes", count=1)
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            ec.count = 3  # type: ignore[misc]
