from datetime import date, timedelta

import pytest

from silen_worker.detection.service import (
    EntityWindow,
    detect_differences,
)

TARGET = date(2026, 7, 23)


def _history(days: int) -> frozenset[date]:
    return frozenset(TARGET - timedelta(days=offset) for offset in range(1, days + 1))


def _win(
    dates,
    occurred_before,
    etype="thing",
    eid="e1",
    last_prior_date=None,
):
    return EntityWindow(
        eid,
        etype,
        frozenset(dates),
        occurred_before,
        last_prior_date,
    )


def test_이력_없는_엔티티는_first_occurrence로_저장_후보가_된다():
    out = detect_differences(
        TARGET,
        [_win({TARGET}, occurred_before=False)],
        active_history_dates=frozenset(),
        today_is_active=True,
    )

    assert len(out) == 1
    assert out[0].method == "first_occurrence"
    assert out[0].description == "처음 등장"
    assert out[0].confidence == pytest.approx(1.0)


def test_자주_기록된_엔티티가_오늘_기록에_없으면_부재_차이다():
    history = _history(2)
    out = detect_differences(
        TARGET,
        [_win(history, occurred_before=True)],
        active_history_dates=history,
        today_is_active=True,
    )

    assert len(out) == 1
    assert out[0].method == "freq_shift"
    assert out[0].description == (
        "과거 활성일 2일 중 2일 기록됨, 오늘 기록에는 언급 없음, 마지막 1일 전"
    )
    assert out[0].confidence == pytest.approx(2.5849625)


def test_창_안_한_번만_등장한_엔티티의_부재는_추정하지_않는다():
    history = _history(4)
    out = detect_differences(
        TARGET,
        [_win({TARGET - timedelta(days=2)}, occurred_before=True)],
        active_history_dates=history,
        today_is_active=True,
    )

    assert out == []


def test_오늘_활성_메모가_없으면_부재를_만들지_않는다():
    history = _history(3)
    out = detect_differences(
        TARGET,
        [_win(history, occurred_before=True)],
        active_history_dates=history,
        today_is_active=False,
    )

    assert out == []


def test_오랜만의_재등장은_등장_놀라움으로_계산한다():
    history = _history(14)
    prior = TARGET - timedelta(days=9)
    out = detect_differences(
        TARGET,
        [
            _win(
                {prior, TARGET},
                occurred_before=True,
                last_prior_date=prior,
            )
        ],
        active_history_dates=history,
        today_is_active=True,
    )

    assert len(out) == 1
    assert out[0].description == "9일 만에 재등장(과거 활성일 14일 중 1일 기록됨)"
    assert out[0].confidence == pytest.approx(3.3219281)


def test_연속_등장은_매일_차이에서_제외한다():
    history = _history(3)
    out = detect_differences(
        TARGET,
        [_win({TARGET - timedelta(days=1), TARGET}, occurred_before=True)],
        active_history_dates=history,
        today_is_active=True,
    )

    assert out == []
