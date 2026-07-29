from datetime import date, timedelta

import pytest

from silen_worker.detection.service import (
    DetectedDifference,
    EntityWindow,
    detect_differences,
    rank_differences,
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
        "기록을 남긴 2일 중 2일에 있었음, 오늘 기록에는 없음, 마지막은 1일 전"
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
    assert out[0].description == "9일 만에 재등장(기록을 남긴 14일 중 1일에 있었음)"
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


def _candidate(
    confidence: float,
    *,
    eid: str = "e1",
    method: str = "freq_shift",
) -> DetectedDifference:
    return DetectedDifference(eid, "thing", method, "통계 근거", confidence)


def test_랭킹은_놀라움_상위_3개만_남긴다():
    candidates = [
        _candidate(2.1, eid="e1"),
        _candidate(4.0, eid="e2"),
        _candidate(3.0, eid="e3"),
        _candidate(2.5, eid="e4"),
    ]

    out = rank_differences(candidates, {}, active_history_days=2)

    assert [item.entity_id for item in out] == ["e2", "e3", "e4"]


def test_랭킹은_2_bits_미만을_버린다():
    out = rank_differences(
        [_candidate(1.9, eid="low"), _candidate(2.1, eid="high")],
        {},
        active_history_days=2,
    )

    assert [item.entity_id for item in out] == ["high"]


def test_기각_2회는_점수를_3분의_1로_낮춘다():
    out = rank_differences(
        [_candidate(4.0, eid="plain"), _candidate(6.0, eid="dismissed")],
        {("dismissed", "thing", "freq_shift"): 2},
        active_history_days=2,
    )

    assert [item.entity_id for item in out] == ["plain", "dismissed"]


def test_기각_3회면_후보에서_제외한다():
    out = rank_differences(
        [_candidate(5.0, eid="hidden")],
        {("hidden", "thing", "freq_shift"): 3},
        active_history_days=2,
    )

    assert out == []


def test_과거_활성일이_한_날이면_카드를_열지_않는다():
    assert rank_differences(
        [_candidate(5.0)],
        {},
        active_history_days=1,
    ) == []


def test_first_occurrence는_랭킹에_들어가지_않는다():
    out = rank_differences(
        [_candidate(8.0, method="first_occurrence")],
        {},
        active_history_days=10,
    )

    assert out == []
