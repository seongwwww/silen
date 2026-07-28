from datetime import date, timedelta

import pytest

from silen_worker.detection.emotion import detect_emotion_difference


TARGET = date(2026, 7, 28)


def _entries(history: list[float], today: list[float] | None = None):
    rows: list[tuple[date, float]] = []
    for offset, value in enumerate(history, start=1):
        rows.append((TARGET - timedelta(days=len(history) - offset + 1), value))
    rows.extend((TARGET, value) for value in (today or []))
    return rows


def test_평탄한_감정은_차이가_아니다():
    assert detect_emotion_difference(_entries([0.0] * 5, [0.0]), TARGET) is None


def test_오늘만_급락하면_높은_bits의_감정전환이다():
    result = detect_emotion_difference(_entries([0.75] * 5, [-1.0]), TARGET)

    assert result is not None
    assert result.method == "zscore"
    assert result.category == "감정전환"
    assert result.confidence == pytest.approx(8.0)
    assert result.z_score == pytest.approx(-7.0)
    assert result.description == "최근 5일 평균 0.75, 오늘 -1.00 (z=-7.0)"


def test_과거_감정_활성일이_4일이면_계산하지_않는다():
    assert (
        detect_emotion_difference(_entries([0.0] * 4, [-1.0]), TARGET)
        is None
    )


def test_표준편차가_0이어도_실제_변화를_탐지한다():
    result = detect_emotion_difference(_entries([0.5] * 5, [0.0]), TARGET)

    assert result is not None
    assert result.z_score == pytest.approx(-2.0)
    assert result.confidence == pytest.approx(4.457981, rel=1e-6)


def test_같은_날_여러_감정은_일별_평균으로_계산한다():
    result = detect_emotion_difference(
        _entries([0.5] * 5, [-1.0, 0.0]),
        TARGET,
    )

    assert result is not None
    assert result.today_mean == pytest.approx(-0.5)
    assert result.z_score == pytest.approx(-4.0)


def test_오늘_감정이_없으면_결과가_없다():
    assert detect_emotion_difference(_entries([0.0] * 5), TARGET) is None


def test_bits는_8을_넘지_않는다():
    result = detect_emotion_difference(_entries([1.0] * 5, [-1.0]), TARGET)

    assert result is not None
    assert result.confidence == 8.0


def test_같은_크기의_상승과_하락은_양측_p로_같은_bits다():
    lower = detect_emotion_difference(_entries([0.0] * 5, [-0.5]), TARGET)
    higher = detect_emotion_difference(_entries([0.0] * 5, [0.5]), TARGET)

    assert lower is not None and higher is not None
    assert lower.z_score == pytest.approx(-higher.z_score)
    assert lower.confidence == pytest.approx(higher.confidence)


def test_같은_방향의_연속_급락은_매일_신호로_만들지_않는다():
    history = [0.0] * 5 + [-1.0]

    assert (
        detect_emotion_difference(_entries(history, [-1.0]), TARGET)
        is None
    )


def test_미래_값과_입력_순서는_오늘_계산에_영향을_주지_않는다():
    rows = _entries([0.5] * 5, [0.0])
    rows.append((TARGET + timedelta(days=1), 1.0))
    rows.reverse()

    result = detect_emotion_difference(rows, TARGET)

    assert result is not None
    assert result.baseline_days == 5
    assert result.baseline_mean == pytest.approx(0.5)
