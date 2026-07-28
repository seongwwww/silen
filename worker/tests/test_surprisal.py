import math

import pytest

from silen_worker.detection.surprisal import (
    bits_absent,
    bits_present,
    jeffreys_probability,
    surprisal_bits,
)


def test_every_active_day_seen_is_unsurprising_when_present_today():
    probability = jeffreys_probability(active_days=7, seen_days=7)

    assert probability == pytest.approx(7.5 / 8)
    assert bits_present(probability) == pytest.approx(0.0931094)
    assert surprisal_bits(
        active_days=7,
        seen_days=7,
        present_today=True,
    ) == pytest.approx(0.0931094)


def test_every_active_day_seen_is_surprising_when_absent_today():
    probability = jeffreys_probability(active_days=7, seen_days=7)

    assert bits_absent(probability) == pytest.approx(4.0)
    assert surprisal_bits(
        active_days=7,
        seen_days=7,
        present_today=False,
    ) == pytest.approx(4.0)


def test_never_seen_is_surprising_when_present_today():
    probability = jeffreys_probability(active_days=7, seen_days=0)

    assert probability == pytest.approx(0.5 / 8)
    assert bits_present(probability) == pytest.approx(4.0)


def test_smoothing_keeps_full_history_absence_finite():
    probability = jeffreys_probability(active_days=2, seen_days=2)
    result = bits_absent(probability)

    assert probability == pytest.approx(2.5 / 3)
    assert result == pytest.approx(2.5849625)
    assert math.isfinite(result)


def test_empty_history_is_neutral_and_finite():
    probability = jeffreys_probability(active_days=0, seen_days=0)

    assert probability == pytest.approx(0.5)
    assert bits_present(probability) == pytest.approx(1.0)
    assert bits_absent(probability) == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("active_days", "seen_days"),
    [(-1, 0), (1, -1), (1, 2)],
)
def test_invalid_history_counts_are_rejected(active_days: int, seen_days: int):
    with pytest.raises(ValueError):
        jeffreys_probability(active_days=active_days, seen_days=seen_days)

