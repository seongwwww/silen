from datetime import date, timedelta

import pytest

from silen_worker.detection.service import (
    EntityWindow,
    detect_differences,
)

TARGET = date(2026, 7, 23)


def _win(dates, occurred_before, etype="thing", eid="e1"):
    return EntityWindow(eid, etype, frozenset(dates), occurred_before)


def _by_id(diffs):
    return {d.entity_id: d for d in diffs}


def test_이력_없는_엔티티는_first_occurrence():
    out = detect_differences(TARGET, [_win({TARGET}, occurred_before=False)])
    assert len(out) == 1
    assert out[0].method == "first_occurrence"
    assert out[0].description == "이 thing 첫 등장"
    assert out[0].confidence == 1.0


def test_오늘만_등장하고_이력_있으면_차이없음():
    # 아주 오래전(창 밖) 등장 이력만 있고 최근 창엔 오늘뿐 → 산발, 차이 없음.
    out = detect_differences(TARGET, [_win({TARGET}, occurred_before=True)])
    assert out == []


def test_이틀_연속은_streak():
    dates = {TARGET, TARGET - timedelta(days=1)}
    out = detect_differences(TARGET, [_win(dates, occurred_before=True)])
    assert len(out) == 1
    assert out[0].method == "freq_shift"
    assert out[0].description == "최근 2일 연속 등장"
    assert out[0].confidence == pytest.approx(1 / 6)


def test_사흘_연속_streak_길이가_반영된다():
    dates = {TARGET, TARGET - timedelta(days=1), TARGET - timedelta(days=2)}
    out = detect_differences(TARGET, [_win(dates, occurred_before=True)])
    assert out[0].description == "최근 3일 연속 등장"


def test_7일_이상_공백_후_재등장():
    dates = {TARGET, TARGET - timedelta(days=9)}  # 9일 공백
    out = detect_differences(TARGET, [_win(dates, occurred_before=True)])
    assert len(out) == 1
    assert out[0].method == "freq_shift"
    assert out[0].description == "9일 만에 재등장(최근 28일 내)"
    assert out[0].confidence == pytest.approx(9 / 28)


def test_6일_공백은_재등장_아님_산발():
    dates = {TARGET, TARGET - timedelta(days=6)}  # 6일 공백, 연속 아님
    out = detect_differences(TARGET, [_win(dates, occurred_before=True)])
    assert out == []


def test_빈_입력은_0건():
    assert detect_differences(TARGET, []) == []


def test_오늘_등장하지_않는_엔티티는_분류하지_않는다():
    dates = {TARGET - timedelta(days=1)}  # 어제만
    out = detect_differences(TARGET, [_win(dates, occurred_before=True)])
    assert out == []


def test_first와_freq는_상호배타():
    # occurred_before=False면 창에 오늘만 있어도 freq_shift로 뜨지 않는다.
    out = detect_differences(TARGET, [_win({TARGET}, occurred_before=False)])
    assert [d.method for d in out] == ["first_occurrence"]


def test_streak가_재등장보다_우선():
    # 연속이면서 공백도 있는 경우 streak로 분류(연속 우선).
    dates = {TARGET, TARGET - timedelta(days=1), TARGET - timedelta(days=10)}
    out = detect_differences(TARGET, [_win(dates, occurred_before=True)])
    assert out[0].description == "최근 2일 연속 등장"
