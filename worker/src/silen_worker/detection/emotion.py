"""감정 valence의 일별 평균이 최근 기록 범위에서 벗어났는지 계산한다.

DB·LLM을 모르는 순수 함수다. 호출자가 넘긴 창 안에서 target 이전 감정 활성일을
baseline으로 삼고, 같은 날짜의 여러 감정은 먼저 평균한다.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from math import isclose, isfinite, log2
from statistics import NormalDist, fmean, pstdev
from typing import Iterable


MIN_BASELINE_DAYS = 5
SD_FLOOR = 0.25
MAX_BITS = 8.0
P_FLOOR = 2**-8
CONTINUATION_BITS_MIN = 2.0
ZERO_ABS_TOLERANCE = 1e-12


@dataclass(frozen=True)
class EmotionDifference:
    method: str
    category: str
    description: str
    confidence: float
    z_score: float
    baseline_mean: float
    today_mean: float
    baseline_days: int
    entity_id: None = None
    dimension: str = "emotion"


@dataclass(frozen=True)
class _Score:
    mean: float
    value: float
    z: float
    bits: float
    days: int


def _score(value: float, baseline: list[float]) -> _Score | None:
    if len(baseline) < MIN_BASELINE_DAYS:
        return None

    mean = fmean(baseline)
    sd = pstdev(baseline)
    z = (value - mean) / max(sd, SD_FLOOR)
    if isclose(z, 0.0, abs_tol=ZERO_ABS_TOLERANCE):
        return None

    p = 2 * (1 - NormalDist().cdf(abs(z)))
    bits = min(MAX_BITS, -log2(max(p, P_FLOOR)))
    return _Score(mean=mean, value=value, z=z, bits=bits, days=len(baseline))


def _same_direction_continuation(
    daily: dict[date, float],
    target_date: date,
    current: _Score,
) -> bool:
    """어제 이미 같은 방향의 의미 있는 이탈이었다면 오늘 카드는 만들지 않는다.

    연속 신호 자체는 버리는 것이 아니라 주간 집계가 다룬다. 달력상 어제가 아닌
    마지막 활성일을 쓰면 기록 공백 뒤 재등장까지 연속으로 오인하므로 정확히
    target-1만 본다.
    """

    previous_date = target_date - timedelta(days=1)
    previous_value = daily.get(previous_date)
    if previous_value is None:
        return False

    previous_baseline = [
        value for local_date, value in daily.items() if local_date < previous_date
    ]
    previous = _score(previous_value, previous_baseline)
    if previous is None:
        return False

    return (
        current.bits >= CONTINUATION_BITS_MIN
        and previous.bits >= CONTINUATION_BITS_MIN
        and current.z * previous.z > 0
    )


def detect_emotion_difference(
    entries: Iterable[tuple[date, float]],
    target_date: date,
) -> EmotionDifference | None:
    """target_date의 감정 변화 1건 또는 None을 반환한다.

    confidence에는 다른 detector와 함께 정렬할 수 있도록 양측 꼬리확률을 변환한
    surprisal bits를 그대로 넣는다.
    """

    grouped: dict[date, list[float]] = defaultdict(list)
    for local_date, valence in entries:
        if local_date <= target_date and isfinite(valence):
            grouped[local_date].append(valence)

    daily = {
        local_date: fmean(values)
        for local_date, values in grouped.items()
        if values
    }
    today = daily.get(target_date)
    if today is None:
        return None

    baseline = [
        value for local_date, value in daily.items() if local_date < target_date
    ]
    score = _score(today, baseline)
    if score is None or _same_direction_continuation(daily, target_date, score):
        return None

    return EmotionDifference(
        method="zscore",
        category="감정전환",
        description=(
            f"최근 {score.days}일 평균 {score.mean:.2f}, "
            f"오늘 {score.value:.2f} (z={score.z:.1f})"
        ),
        confidence=score.bits,
        z_score=score.z,
        baseline_mean=score.mean,
        today_mean=score.value,
        baseline_days=score.days,
    )
